"""Data ingestion, cross-platform reconciliation and unified business metrics.

Pipeline:  raw tables -> reconcile platform-reported orders against real sales
           -> per-campaign unified state (ROAS, CAC, CTR, CPC, CVR, profit,
              margin, inventory days, stockout risk, spend elasticity).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from .config import AS_OF, BASELINE_END, BASELINE_START, HISTORY_DAYS, RECENT_DAYS
from .db import read
from .policy import Policy, policy_from_row


@dataclass
class CompanyData:
    company_id: str
    name: str
    vertical: str
    policy: Policy
    campaigns: pd.DataFrame
    products: pd.DataFrame
    platforms: pd.DataFrame
    audiences: pd.DataFrame
    creatives: pd.DataFrame
    ad: pd.DataFrame           # daily ad metrics joined with campaign/sku, 'day' = 0..59
    sales: pd.DataFrame
    pricing: pd.DataFrame
    comp: pd.DataFrame
    inventory: pd.DataFrame
    recon: pd.DataFrame = field(default_factory=pd.DataFrame)   # per-SKU reconciliation


def all_policies(con: sqlite3.Connection) -> dict[str, Policy]:
    prof = read(con, "SELECT p.*, c.name AS cname FROM company_profiles p JOIN companies c USING(company_id)")
    return {r["company_id"]: policy_from_row(r["cname"], r) for _, r in prof.iterrows()}


def _day_index(dates: pd.Series) -> pd.Series:
    return (pd.to_datetime(dates) - pd.Timestamp(AS_OF)).dt.days + HISTORY_DAYS - 1


def load_company(con: sqlite3.Connection, company_id: str) -> CompanyData:
    comp_row = read(con, "SELECT * FROM companies WHERE company_id=?", (company_id,))
    if comp_row.empty:
        raise KeyError(company_id)
    policies = all_policies(con)
    q = (company_id,)
    campaigns = read(con, "SELECT * FROM campaigns WHERE company_id=?", q)
    products = read(con, "SELECT p.*, i.on_hand_units, i.lead_time_days FROM products p "
                         "JOIN inventory i USING(sku_id) WHERE company_id=?", q)
    platforms = read(con, "SELECT * FROM platforms")
    audiences = read(con, "SELECT * FROM audiences")
    creatives = read(con, "SELECT c.* FROM creatives c JOIN products p USING(sku_id) WHERE p.company_id=?", q)
    ad = read(con, "SELECT m.* FROM ad_metrics m JOIN campaigns c USING(campaign_id) WHERE c.company_id=?", q)
    ad["day"] = _day_index(ad["date"])
    sales = read(con, "SELECT s.* FROM sales s JOIN products p USING(sku_id) WHERE p.company_id=?", q)
    sales["day"] = _day_index(sales["date"])
    pricing = read(con, "SELECT r.* FROM pricing r JOIN products p USING(sku_id) WHERE p.company_id=?", q)
    pricing["day"] = _day_index(pricing["date"])
    comp = read(con, "SELECT r.* FROM competitor_prices r JOIN products p USING(sku_id) WHERE p.company_id=?", q)
    comp["day"] = _day_index(comp["date"])
    inventory = read(con, "SELECT i.* FROM inventory i JOIN products p USING(sku_id) WHERE p.company_id=?", q)
    d = CompanyData(
        company_id=company_id, name=comp_row.iloc[0]["name"], vertical=comp_row.iloc[0]["vertical"],
        policy=policies[company_id], campaigns=campaigns, products=products, platforms=platforms,
        audiences=audiences, creatives=creatives,
        ad=ad.merge(campaigns[["campaign_id", "sku_id", "platform_id", "audience_id"]], on="campaign_id"),
        sales=sales, pricing=pricing, comp=comp, inventory=inventory,
    )
    d.recon = reconcile(d)
    return d


# --------------------------------------------------------------------------- #
# Reconciliation: platform-reported orders over-count (view-through, multi-touch
# double counting). Regress real SKU sales on the sum of platform orders.
#   units_t = organic + coef * platform_orders_t
# coef < 1 is the haircut applied to platform numbers; intercept = organic baseline.
# --------------------------------------------------------------------------- #

def reconcile(d: CompanyData) -> pd.DataFrame:
    rows = []
    po = d.ad.groupby(["sku_id", "day"])["platform_orders"].sum().reset_index()
    for sku_id in d.products["sku_id"]:
        s = d.sales[d.sales.sku_id == sku_id].set_index("day")["units"]
        x = po[po.sku_id == sku_id].set_index("day")["platform_orders"].reindex(s.index).fillna(0)
        coef, organic, r2 = 0.8, float(s.mean()) * 0.3, 0.0
        if len(s) > 10 and x.std() > 0:
            lr = LinearRegression().fit(x.to_numpy().reshape(-1, 1), s.to_numpy())
            r2 = float(lr.score(x.to_numpy().reshape(-1, 1), s.to_numpy()))
            coef = float(np.clip(lr.coef_[0], 0.55, 1.0))
            organic = float(max(0.0, lr.intercept_))
        rows.append(dict(sku_id=sku_id, recon_factor=round(coef, 4), organic_units_per_day=round(organic, 2),
                         recon_r2=round(r2, 3), platform_orders=float(x.sum()), real_units=float(s.sum())))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Spend elasticity (log-log regression with shrinkage toward the platform prior)
# --------------------------------------------------------------------------- #

def fit_elasticity(d: CompanyData) -> dict[str, dict]:
    prior_by_plat = d.platforms.set_index("platform_id")["elasticity_prior"].to_dict()
    rf = d.recon.set_index("sku_id")["recon_factor"].to_dict()
    out = {}
    hist = d.ad[d.ad.day < HISTORY_DAYS - BASELINE_END]
    for _, c in d.campaigns.iterrows():
        h = hist[(hist.campaign_id == c.campaign_id) & (hist.spend > 0)]
        prior = prior_by_plat[c.platform_id]
        fit, r2 = prior, 0.0
        if len(h) >= 20:
            x = np.log(h["spend"].to_numpy()).reshape(-1, 1)
            y = np.log(np.maximum(h["platform_orders"].to_numpy() * rf[c.sku_id], 1.0))
            lr = LinearRegression().fit(x, y)
            fit, r2 = float(lr.coef_[0]), float(max(0.0, lr.score(x, y)))
        w = float(np.clip(r2, 0.0, 0.7))
        e = float(np.clip(w * fit + (1 - w) * prior, 0.45, 0.95))
        out[c.campaign_id] = dict(elasticity=e, fit_raw=fit, r2=r2, prior=prior, quality=float(np.clip(0.4 + r2, 0.3, 1.0)))
    return out


# --------------------------------------------------------------------------- #
# Unified campaign state
# --------------------------------------------------------------------------- #

def _latest(df: pd.DataFrame, col: str, sku_id: str, n: int = 3) -> float:
    s = df[df.sku_id == sku_id].sort_values("day").tail(n)[col]
    return float(s.mean())


def stockout_risk(days_cover: float, lead_time: float) -> float:
    return float(np.clip((1.5 * lead_time - days_cover) / max(lead_time, 1.0), 0.0, 1.0))


def build_state(d: CompanyData, overrides: dict | None = None, policy: Policy | None = None) -> list[dict]:
    """Return one dict per campaign with unified metrics. `overrides` = {sku_id: {on_hand, price, unit_cost}}."""
    overrides = overrides or {}
    policy = policy or d.policy
    recent = d.ad[d.ad.day >= HISTORY_DAYS - RECENT_DAYS]
    base = d.ad[(d.ad.day >= HISTORY_DAYS - BASELINE_START) & (d.ad.day < HISTORY_DAYS - BASELINE_END)]
    rf = d.recon.set_index("sku_id")
    el = fit_elasticity(d)
    plat = d.platforms.set_index("platform_id")["name"].to_dict()
    aud = d.audiences.set_index("audience_id")
    prod = d.products.set_index("sku_id")
    cre = d.creatives.set_index("creative_id")
    vel_sales = d.sales[d.sales.day >= HISTORY_DAYS - 7].groupby("sku_id")["units"].mean()

    sku_info = {}
    for sku_id, p in prod.iterrows():
        ov = overrides.get(sku_id, {})
        price0 = _latest(d.pricing.assign(net=d.pricing.list_price * (1 - d.pricing.discount_pct)), "net", sku_id)
        cost0 = _latest(d.pricing, "unit_cost", sku_id)
        price = float(ov.get("price", price0))
        cost = float(ov.get("unit_cost", cost0))
        margin = (price - cost) / price if price > 0 else 0.0
        on_hand = float(ov.get("on_hand", p["on_hand_units"]))
        velocity = float(max(vel_sales.get(sku_id, 1.0), 0.1))
        days_cover = on_hand / velocity
        lead = float(p["lead_time_days"])
        price_ratio = price / price0 if price0 else 1.0
        sku_info[sku_id] = dict(
            name=p["name"], price=price, price0=price0, cost=cost, margin=margin, on_hand=on_hand,
            velocity=velocity, days_cover=days_cover, lead_time=lead, shelf_life=float(p["shelf_life_days"]),
            stockout_risk=stockout_risk(days_cover, lead), organic=float(rf.loc[sku_id, "organic_units_per_day"]),
            recon_factor=float(rf.loc[sku_id, "recon_factor"]), price_ratio=price_ratio,
        )
        target = policy.inventory_target_days
        if sku_info[sku_id]["shelf_life"] < 900:
            target = min(target, 0.6 * sku_info[sku_id]["shelf_life"])
        sku_info[sku_id]["target_days"] = target
        sku_info[sku_id]["cap_units"] = max(0.0, on_hand / max(lead, 2.0) - sku_info[sku_id]["organic"])
        pr = (days_cover - target) / max(target, 1.0)
        sku_info[sku_id]["inv_pressure"] = float(np.clip(pr, -1.0, 2.0))

    states = []
    for _, c in d.campaigns.iterrows():
        si = sku_info[c.sku_id]
        r = recent[recent.campaign_id == c.campaign_id]
        n = max(len(r), 1)
        b = base[base.campaign_id == c.campaign_id]
        spend = float(r.spend.sum() / n)
        clicks = float(r.clicks.sum() / n)
        imps = float(r.impressions.sum() / n)
        orders_platform = float(r.platform_orders.sum() / n)
        orders = orders_platform * si["recon_factor"] * (si["price_ratio"] ** -policy.price_elasticity)
        revenue = orders * si["price"]
        margin_amt = revenue * si["margin"]
        # scale to the configured budget (spend ~ budget on average)
        scale = c.daily_budget / spend if spend > 0 else 1.0
        orders_at_b = orders * scale ** el[c.campaign_id]["elasticity"]
        daily = b.assign(rev=b.platform_orders * si["recon_factor"] * si["price0"], roas_d=lambda x: x.rev / x.spend)
        daily = daily.replace([np.inf, -np.inf], np.nan).dropna(subset=["roas_d"])
        roas_cv = float(np.clip(daily.roas_d.std() / daily.roas_d.mean(), 0.03, 0.6)) if len(daily) > 3 else 0.2
        cr = cre.loc[c.creative_id]
        a = aud.loc[c.audience_id]
        states.append(dict(
            campaign_id=c.campaign_id, name=c["name"], sku_id=c.sku_id, sku_name=si["name"],
            platform_id=c.platform_id, platform=plat[c.platform_id], audience_id=c.audience_id,
            audience=a["name"], audience_type=a["audience_type"], new_share=float(a["new_customer_share"]),
            creative=cr["name"], creative_age=int((pd.Timestamp(AS_OF) - pd.Timestamp(cr["launch_date"])).days),
            b0=float(c.daily_budget), spend=spend, impressions=imps, clicks=clicks,
            orders=orders, orders0=orders_at_b, revenue=revenue,
            roas=revenue / spend if spend else 0.0, cac=spend / orders if orders else 0.0,
            ctr=clicks / imps if imps else 0.0, cpc=spend / clicks if clicks else 0.0,
            cvr=orders / clicks if clicks else 0.0,
            profit=margin_amt - spend, margin=si["margin"], price=si["price"], unit_cost=si["cost"],
            on_hand=si["on_hand"], inventory_days=si["days_cover"], lead_time=si["lead_time"],
            shelf_life=si["shelf_life"], stockout_risk=si["stockout_risk"], target_days=si["target_days"],
            inv_pressure=si["inv_pressure"], cap_units=si["cap_units"], velocity=si["velocity"],
            elasticity=el[c.campaign_id]["elasticity"], fit_quality=el[c.campaign_id]["quality"],
            fit_r2=el[c.campaign_id]["r2"], roas_cv=roas_cv, status=c.status,
        ))
    return states


def daily_series(d: CompanyData, campaign_id: str | None = None) -> pd.DataFrame:
    """Daily reconciled unified series for a campaign (or whole company). Memoised on the (immutable) CompanyData."""
    memo = d.__dict__.setdefault("_series_memo", {})
    if campaign_id not in memo:
        memo[campaign_id] = _daily_series(d, campaign_id)
    return memo[campaign_id].copy()


def _daily_series(d: CompanyData, campaign_id: str | None) -> pd.DataFrame:
    ad = d.ad if campaign_id is None else d.ad[d.ad.campaign_id == campaign_id]
    rf = d.recon.set_index("sku_id")["recon_factor"]
    ad = ad.assign(orders=ad.platform_orders * ad.sku_id.map(rf))
    price = d.pricing.assign(net=d.pricing.list_price * (1 - d.pricing.discount_pct))
    pm = price.set_index(["sku_id", "day"])["net"]
    cm = price.set_index(["sku_id", "day"])["unit_cost"]
    idx = pd.MultiIndex.from_arrays([ad.sku_id, ad.day])
    ad = ad.assign(price=pm.reindex(idx).to_numpy(), cost=cm.reindex(idx).to_numpy())
    ad["revenue"] = ad.orders * ad.price
    ad["gross"] = ad.revenue - ad.orders * ad.cost
    g = ad.groupby("day").agg(spend=("spend", "sum"), revenue=("revenue", "sum"), gross=("gross", "sum"),
                              orders=("orders", "sum"), clicks=("clicks", "sum"),
                              impressions=("impressions", "sum"), reach=("reach", "sum")).reset_index()
    g["profit"] = g.gross - g.spend
    g["roas"] = g.revenue / g.spend
    g["ctr"] = g.clicks / g.impressions
    g["cpc"] = g.spend / g.clicks
    g["cvr"] = g.orders / g.clicks
    g["cac"] = g.spend / g.orders
    g["frequency"] = g.impressions / g.reach
    g["date"] = (pd.Timestamp(AS_OF) - pd.to_timedelta(HISTORY_DAYS - 1 - g.day, unit="D")).dt.strftime("%Y-%m-%d")
    return g
