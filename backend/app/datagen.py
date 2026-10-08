"""Deterministic synthetic data generator for AegisOne.

Run:  python -m app.datagen            (from backend/)

Writes backend/data/aegis.db (SQLite) and backend/data/csv/*.csv.
Five brands, 12 campaigns each, 60 days of daily metrics, with scripted
anomalies injected into the last ~8 days so the diagnosis engine has real
signals to find. The generator knows the ground truth; the engine never reads it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import timedelta

import numpy as np
import pandas as pd

from .brands import build_tables
from .config import AS_OF, CSV_DIR, DB_PATH, HISTORY_DAYS, SCHEMA_PATH, SEED

# --------------------------------------------------------------------------- #
# Static reference data
# --------------------------------------------------------------------------- #

PLATFORMS = {
    # id: (name, spend->revenue elasticity prior, cpm-vs-spend exponent used by generator, order over-count)
    "meta": ("Meta Ads", 0.72, 0.28, 1.30),
    "google": ("Google Ads", 0.78, 0.22, 1.12),
    "instagram": ("Instagram Ads", 0.68, 0.32, 1.28),
    "youtube": ("YouTube Ads", 0.62, 0.38, 1.35),
}

AUDIENCES = {
    "lal": ("Lookalike 1%", "prospecting", 0.85),
    "broad": ("Broad", "prospecting", 0.90),
    "int": ("Interest-based", "prospecting", 0.80),
    "rt": ("Retargeting 30d", "retargeting", 0.12),
}

FORMATS = {"meta": "Carousel", "instagram": "Reel", "google": "Responsive Search", "youtube": "Video 15s"}

# Brands, SKUs (public catalog data + demo cost/inventory assumptions), campaigns and scripted events
# come from the brand data layer (brands.py). All ad-performance numbers below are SIMULATED.
COMPANIES, SKUS, CAMPAIGNS, CAMPAIGN_EVENTS, SKU_EVENTS, CREATIVE_AGE_DAYS = build_tables()


def _mult(ev: dict | None, key: str, d: int) -> float:
    if not ev:
        return 1.0
    m = ev.get(key, 1.0)
    if d < ev["start"]:
        return 1.0
    frac = min(1.0, (d - ev["start"] + 1) / max(1, ev["ramp"]))
    return 1.0 + (m - 1.0) * frac


def _stable_u(*parts: str) -> float:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

def generate() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    dates = [AS_OF - timedelta(days=HISTORY_DAYS - 1 - d) for d in range(HISTORY_DAYS)]
    date_str = [d.isoformat() for d in dates]
    weekday_demand = np.array([1.0, 0.97, 0.98, 1.0, 1.04, 1.14, 1.12])  # Mon..Sun

    t: dict[str, list] = {k: [] for k in [
        "companies", "company_profiles", "platforms", "audiences", "products", "pricing",
        "competitor_prices", "inventory", "sales", "creatives", "campaigns", "ad_metrics"]}

    for pid, (name, prior, _, _) in PLATFORMS.items():
        t["platforms"].append(dict(platform_id=pid, name=name, elasticity_prior=prior))
    for aid, (name, atype, share) in AUDIENCES.items():
        t["audiences"].append(dict(audience_id=aid, name=name, audience_type=atype, new_customer_share=share))

    for cid, comp in COMPANIES.items():
        t["companies"].append(dict(company_id=cid, name=comp["name"], vertical=comp["vertical"],
                                   description=comp["description"]))
        t["company_profiles"].append(dict(company_id=cid, **comp["profile"]))

        sku_meta = {}
        # SKUs, pricing, competitor prices, inventory
        for key, sname, cat, price, cost, shelf, on_hand, lead, org in SKUS[cid]:
            sku_id = f"{cid}-{key}"
            sku_meta[key] = dict(sku_id=sku_id, price=price, cost=cost, org=org)
            t["products"].append(dict(sku_id=sku_id, company_id=cid, name=sname, category=cat,
                                      shelf_life_days=shelf, organic_units_per_day=org))
            t["inventory"].append(dict(sku_id=sku_id, on_hand_units=on_hand, lead_time_days=lead,
                                       as_of=AS_OF.isoformat()))
            sev = SKU_EVENTS.get((cid, key), {})
            comp_ratio = 0.96 + 0.12 * _stable_u(cid, key, "comp")
            for d in range(HISTORY_DAYS):
                cost_d = cost * (sev.get("cost_mult", 1.0) if d >= sev.get("cost_start", 999) else 1.0)
                cost_d *= 1 + rng.normal(0, 0.004)
                comp_d = price * comp_ratio * (sev.get("comp_mult", 1.0) if d >= sev.get("comp_start", 999) else 1.0)
                comp_d *= 1 + rng.normal(0, 0.012)
                t["pricing"].append(dict(sku_id=sku_id, date=date_str[d], list_price=price,
                                         discount_pct=0.0, unit_cost=round(cost_d, 2)))
                t["competitor_prices"].append(dict(sku_id=sku_id, date=date_str[d],
                                                   competitor_price=round(comp_d, 2)))

        # campaigns & daily metrics
        sku_orders_true: dict[str, np.ndarray] = {k: np.zeros(HISTORY_DAYS) for k in sku_meta}
        for i, (skey, plat, aud, budget, ctr0, roas0, cpm0) in enumerate(CAMPAIGNS[cid], start=1):
            sm = sku_meta[skey]
            camp_id = f"{cid}-c{i:02d}"
            cre_id = f"{camp_id}-cr"
            age = CREATIVE_AGE_DAYS.get((cid, skey, plat, aud), 10 + int(_stable_u(camp_id, "age") * 20))
            sku_name = next(s[1] for s in SKUS[cid] if s[0] == skey)
            t["creatives"].append(dict(creative_id=cre_id, sku_id=sm["sku_id"],
                                       name=f"{sku_name} — {FORMATS[plat]} v{1 + int(_stable_u(camp_id, 'v') * 3)}",
                                       format=FORMATS[plat], launch_date=(AS_OF - timedelta(days=age)).isoformat()))
            t["campaigns"].append(dict(
                campaign_id=camp_id, company_id=cid, sku_id=sm["sku_id"], platform_id=plat, audience_id=aud,
                creative_id=cre_id, name=f"{sku_name} · {PLATFORMS[plat][0].split()[0]} · {AUDIENCES[aud][0]}",
                daily_budget=budget, status="active"))

            alpha = PLATFORMS[plat][2]
            overcount = PLATFORMS[plat][3]
            price = sm["price"]
            cvr0 = roas0 * cpm0 / (1000.0 * ctr0 * price)
            ev = CAMPAIGN_EVENTS.get((cid, skey, plat, aud))
            for d in range(HISTORY_DAYS):
                wk = weekday_demand[dates[d].weekday()]
                spend = budget * float(np.exp(rng.normal(0, 0.18))) * (0.97 + 0.03 * wk)
                ratio = spend / budget
                cpm = cpm0 * ratio ** alpha * float(np.exp(rng.normal(0, 0.05))) * _mult(ev, "cpm", d)
                ctr = ctr0 * float(np.exp(rng.normal(0, 0.04))) * _mult(ev, "ctr", d)
                cvr = cvr0 * float(np.exp(rng.normal(0, 0.05))) * _mult(ev, "cvr", d) * wk
                sev = SKU_EVENTS.get((cid, skey), {})
                imps = int(spend / cpm * 1000)
                clicks = int(rng.poisson(imps * ctr))
                mu = clicks * cvr
                orders = int(max(0, round(mu + rng.normal(0, 0.55 * np.sqrt(max(mu, 1.0))))))  # under-dispersed: keeps demo signals legible
                freq = (1.35 + 0.012 * d) * _mult(ev, "freq", d) * float(np.exp(rng.normal(0, 0.03)))
                reach = int(imps / freq)
                p_orders = int(round(orders * overcount * float(np.exp(rng.normal(0, 0.03)))))
                sku_orders_true[skey][d] += orders
                t["ad_metrics"].append(dict(
                    campaign_id=camp_id, date=date_str[d], impressions=imps, reach=reach, clicks=clicks,
                    spend=round(spend, 2), platform_orders=p_orders, platform_revenue=round(p_orders * price, 2)))

        # sales per SKU = organic + true ad orders
        pr_rows = [r for r in t["pricing"] if r["sku_id"].startswith(f"{cid}-")]
        cost_by = {(r["sku_id"], r["date"]): r["unit_cost"] for r in pr_rows}
        for skey, sm in sku_meta.items():
            for d in range(HISTORY_DAYS):
                wk = weekday_demand[dates[d].weekday()]
                organic = int(rng.poisson(sm["org"] * wk))
                units = organic + int(sku_orders_true[skey][d])
                t["sales"].append(dict(sku_id=sm["sku_id"], date=date_str[d], units=units,
                                       revenue=round(units * sm["price"], 2),
                                       cogs=round(units * cost_by[(sm["sku_id"], date_str[d])], 2)))

    frames = {k: pd.DataFrame(v) for k, v in t.items()}
    frames["recommendations"], frames["feedback"], frames["calibration"] = _past_decisions(frames, rng)
    return frames


def _past_decisions(frames: dict[str, pd.DataFrame], rng: np.random.Generator):
    """Seed a believable decision history so the loop has memory from day one."""
    recs, fbs, calib = [], [], {}
    camps = frames["campaigns"]
    types = ["move_budget", "replace_creative", "pause_campaign", "move_budget", "increase_budget", "move_budget"]
    for cid in COMPANIES:
        cc = camps[camps.company_id == cid].reset_index(drop=True)
        for j in range(6):
            src = cc.iloc[(j * 3) % len(cc)]
            dst = cc.iloc[(j * 3 + 5) % len(cc)]
            rtype = types[j]
            amount = float(rng.choice([4000, 6000, 8000, 10000]))
            predicted = float(round(amount * rng.uniform(0.9, 2.4), 0))
            actual = float(round(predicted * rng.uniform(0.72, 1.12), 0))
            days_ago = 52 - j * 7
            created = (AS_OF - timedelta(days=days_ago)).isoformat() + "T09:30:00"
            rid = f"hist-{cid}-{j + 1}"
            conf_b = float(round(rng.uniform(0.62, 0.86), 2))
            err = actual - predicted
            err_pct = err / predicted if predicted else 0.0
            acc = max(0.0, 1 - abs(err_pct))
            conf_a = float(round(conf_b + 0.3 * (acc - conf_b), 2))
            title = {
                "move_budget": f"Move ₹{int(amount):,}/day from {src['name']} to {dst['name']}",
                "replace_creative": f"Replace creative on {src['name']}",
                "pause_campaign": f"Pause {src['name']}",
                "increase_budget": f"Increase {dst['name']} by ₹{int(amount):,}/day",
            }[rtype]
            payload = dict(rec_id=rid, rec_type=rtype, title=title, historical=True)
            recs.append(dict(rec_id=rid, company_id=cid, policy_id=cid, created_at=created, rec_type=rtype,
                             title=title, source_campaign_id=src["campaign_id"], target_campaign_id=dst["campaign_id"],
                             amount=amount, expected_profit=predicted, confidence=conf_b,
                             why="Historical decision (seeded).", payload=json.dumps(payload), status="approved"))
            fbs.append(dict(rec_id=rid, company_id=cid, predicted_profit=predicted, action=title,
                            actual_profit=actual, error=round(err, 2), error_pct=round(err_pct, 4),
                            confidence_before=conf_b, confidence_after=conf_a,
                            recorded_at=(AS_OF - timedelta(days=days_ago - 7)).isoformat() + "T09:30:00"))
            key = (cid, rtype)
            prev = calib.get(key, (0.8, 0))
            calib[key] = (0.7 * prev[0] + 0.3 * acc if prev[1] else acc, prev[1] + 1)
    cal = pd.DataFrame([dict(company_id=k[0], rec_type=k[1], accuracy=round(v[0], 4), n=v[1])
                        for k, v in calib.items()])
    return pd.DataFrame(recs), pd.DataFrame(fbs), cal


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def build_database(db_path=DB_PATH, write_csv: bool = True) -> dict[str, pd.DataFrame]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    frames = generate()
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    order = ["companies", "company_profiles", "platforms", "audiences", "products", "pricing",
             "competitor_prices", "inventory", "sales", "creatives", "campaigns", "ad_metrics",
             "recommendations", "feedback", "calibration"]
    for name in order:
        frames[name].to_sql(name, con, if_exists="append", index=False)
    con.commit()
    con.close()
    if write_csv:
        CSV_DIR.mkdir(parents=True, exist_ok=True)
        for name, df in frames.items():
            df.to_csv(CSV_DIR / f"{name}.csv", index=False)
    return frames


if __name__ == "__main__":
    fr = build_database()
    print(f"Wrote {DB_PATH}")
    for k, v in fr.items():
        print(f"  {k:18s} {len(v):6d} rows")
