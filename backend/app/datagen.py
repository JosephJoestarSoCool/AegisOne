"""Deterministic synthetic data generator for AegisOne.

Run:  python -m app.datagen            (from backend/)

Writes data/aegis.db (SQLite) and data/csv/*.csv.
Four companies, ~12 campaigns each, 60 days of daily metrics, with scripted
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

from .config import AS_OF, CSV_DIR, DATA_DIR, DB_PATH, HISTORY_DAYS, SCHEMA_PATH, SEED

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

# company: (name, vertical, description, profile dict)
COMPANIES = {
    "fashion": dict(
        name="Premium Fashion", vertical="Fashion",
        description="Luxury-leaning apparel & accessories. Protects margin and brand; tolerates high CAC.",
        profile=dict(w_profitability=0.28, w_growth=0.10, w_revenue=0.12, w_inventory=0.10, w_cac=0.15,
                     w_risk=0.25, min_margin=0.45, max_cac=2200, min_roas=3.0, inventory_target_days=30,
                     ltv_per_customer=3200, price_elasticity=0.8, risk_label="Low risk tolerance"),
    ),
    "startup": dict(
        name="D2C Startup", vertical="Beauty / Skincare",
        description="Venture-backed skincare brand. Buys growth and new customers, accepts thinner ROAS.",
        profile=dict(w_profitability=0.12, w_growth=0.32, w_revenue=0.20, w_inventory=0.06, w_cac=0.18,
                     w_risk=0.12, min_margin=0.30, max_cac=450, min_roas=1.8, inventory_target_days=45,
                     ltv_per_customer=1500, price_elasticity=1.4, risk_label="High risk tolerance"),
    ),
    "electronics": dict(
        name="Consumer Electronics", vertical="Electronics",
        description="Thin-margin gadgets. Every rupee of ad spend must clear a strict ROAS bar.",
        profile=dict(w_profitability=0.30, w_growth=0.08, w_revenue=0.20, w_inventory=0.15, w_cac=0.12,
                     w_risk=0.15, min_margin=0.12, max_cac=1200, min_roas=5.0, inventory_target_days=40,
                     ltv_per_customer=1800, price_elasticity=2.0, risk_label="Medium risk tolerance"),
    ),
    "food": dict(
        name="Food / Perishable", vertical="Food & Beverage",
        description="Short shelf-life goods. Inventory expiry dominates; ads must clear stock before it spoils.",
        profile=dict(w_profitability=0.18, w_growth=0.12, w_revenue=0.12, w_inventory=0.30, w_cac=0.13,
                     w_risk=0.15, min_margin=0.30, max_cac=160, min_roas=3.0, inventory_target_days=10,
                     ltv_per_customer=600, price_elasticity=1.6, risk_label="Medium risk tolerance"),
    ),
}

# SKU: (key, name, category, list_price, unit_cost, shelf_life_days, on_hand, lead_time_days, organic_units_per_day)
SKUS = {
    "fashion": [
        ("blazer", "Linen Blazer", "Outerwear", 7800, 3100, 9999, 1500, 21, 4),
        ("scarf", "Silk Scarf", "Accessories", 3200, 1050, 9999, 2300, 18, 5),
        ("denim", "Selvedge Denim", "Bottoms", 5400, 2300, 9999, 1300, 25, 3),
        ("dress", "Evening Dress", "Dresses", 9200, 3900, 9999, 600, 28, 2),
        ("bag", "Leather Tote", "Bags", 8800, 3800, 9999, 1000, 30, 2.5),
        ("sneaker", "Court Sneaker", "Footwear", 6400, 3200, 9999, 1400, 20, 3),
    ],
    "startup": [
        ("serum", "Vitamin C Serum", "Serums", 1199, 470, 540, 6000, 20, 25),
        ("moist", "Hydra Moisturizer", "Moisturizers", 899, 410, 540, 4500, 20, 18),
        ("sun", "Sunscreen SPF50", "Sun care", 649, 290, 540, 2500, 25, 30),
        ("night", "Retinol Night Cream", "Moisturizers", 1499, 640, 540, 3200, 22, 10),
        ("cleanser", "Gentle Cleanser", "Cleansers", 449, 210, 540, 9000, 15, 22),
        ("hair", "Rosemary Hair Oil", "Hair care", 599, 270, 540, 3500, 18, 15),
    ],
    "electronics": [
        ("earbuds", "Aero Earbuds", "Audio", 3499, 2650, 9999, 6500, 30, 12),
        ("watch", "Pulse Smartwatch", "Wearables", 7999, 6400, 9999, 2300, 35, 4),
        ("speaker", "Boom Speaker", "Audio", 4999, 3900, 9999, 2600, 28, 6),
        ("monitor", "27in 4K Monitor", "Displays", 24999, 21500, 9999, 220, 40, 1.5),
        ("charger", "GaN Charger", "Accessories", 1999, 1250, 9999, 5000, 20, 20),
        ("keyboard", "Mech Keyboard", "Accessories", 5499, 4100, 9999, 1500, 30, 3),
    ],
    "food": [
        ("juice", "Cold-Pressed Juice", "Beverages", 180, 95, 5, 900, 1, 30),
        ("cheese", "Artisan Cheese", "Dairy", 650, 390, 45, 90, 6, 6),
        ("granola", "Crunch Granola", "Pantry", 380, 240, 150, 4000, 10, 25),
        ("pasta", "Fresh Pasta Kit", "Chilled", 320, 210, 12, 3400, 3, 20),
        ("bar", "Protein Bars", "Snacks", 520, 330, 200, 5000, 14, 18),
        ("kombucha", "Kombucha", "Beverages", 240, 140, 60, 1800, 7, 12),
    ],
}

# Campaign: (sku_key, platform, audience, daily_budget, ctr, platform_reported_roas, cpm)
CAMPAIGNS = {
    "fashion": [
        ("blazer", "meta", "lal", 40000, 0.016, 5.3, 270),       # DEMO: creative fatigue
        ("blazer", "google", "rt", 14000, 0.030, 6.7, 700),
        ("scarf", "google", "int", 22000, 0.026, 6.5, 358),      # DEMO: best opportunity
        ("scarf", "instagram", "lal", 12000, 0.019, 4.4, 280),
        ("denim", "meta", "broad", 26000, 0.013, 4.4, 250),      # competitor price pressure
        ("denim", "google", "rt", 9000, 0.030, 5.5, 650),
        ("dress", "instagram", "lal", 24000, 0.014, 5.0, 290),   # CPC spike
        ("dress", "youtube", "broad", 10000, 0.006, 3.6, 110),
        ("bag", "meta", "rt", 12000, 0.028, 5.7, 520),           # margin squeeze
        ("bag", "google", "int", 18000, 0.020, 4.8, 420),
        ("sneaker", "meta", "broad", 16000, 0.015, 4.0, 240),
        ("sneaker", "instagram", "lal", 10000, 0.015, 3.3, 270),
    ],
    "startup": [
        ("serum", "meta", "lal", 16000, 0.018, 3.4, 210),
        ("serum", "instagram", "lal", 14000, 0.020, 3.0, 230),   # conversion drop
        ("sun", "google", "int", 12000, 0.030, 4.6, 380),
        ("sun", "meta", "broad", 14000, 0.016, 3.2, 190),
        ("night", "instagram", "lal", 10000, 0.017, 2.8, 240),
        ("night", "google", "rt", 6000, 0.035, 5.5, 600),
        ("cleanser", "meta", "broad", 9000, 0.014, 2.4, 170),    # CPC spike
        ("cleanser", "meta", "rt", 4000, 0.030, 4.8, 420),
        ("hair", "youtube", "broad", 8000, 0.007, 2.0, 90),
        ("hair", "instagram", "lal", 10000, 0.019, 3.3, 220),
        ("moist", "meta", "lal", 12000, 0.017, 3.0, 200),
        ("moist", "google", "int", 8000, 0.028, 4.0, 340),
    ],
    "electronics": [
        ("earbuds", "meta", "broad", 20000, 0.022, 9.0, 230),    # unit cost spike -> margin squeeze
        ("earbuds", "google", "int", 16000, 0.030, 11.0, 420),
        ("watch", "instagram", "lal", 18000, 0.014, 8.5, 300),
        ("watch", "google", "rt", 8000, 0.030, 11.5, 650),
        ("speaker", "google", "int", 15000, 0.028, 10.0, 400),   # CPC spike (festive auction)
        ("speaker", "meta", "lal", 10000, 0.015, 8.0, 250),
        ("monitor", "google", "int", 14000, 0.025, 11.0, 380),
        ("monitor", "youtube", "broad", 6000, 0.007, 7.0, 100),
        ("charger", "meta", "broad", 10000, 0.020, 6.5, 200),
        ("charger", "instagram", "lal", 8000, 0.018, 6.0, 230),
        ("keyboard", "google", "int", 10000, 0.025, 9.0, 350),
        ("keyboard", "youtube", "broad", 5000, 0.007, 6.5, 110),
    ],
    "food": [
        ("juice", "meta", "lal", 9000, 0.020, 4.8, 180),
        ("juice", "instagram", "lal", 6000, 0.020, 4.2, 200),
        ("cheese", "instagram", "lal", 8000, 0.018, 5.0, 220),   # stockout risk
        ("granola", "google", "int", 9000, 0.030, 5.5, 300),
        ("granola", "meta", "broad", 8000, 0.016, 3.6, 170),     # creative fatigue
        ("pasta", "meta", "lal", 8000, 0.018, 3.9, 190),         # overstock vs shelf life
        ("pasta", "google", "int", 5000, 0.030, 4.5, 320),
        ("bar", "google", "int", 9000, 0.028, 4.9, 330),
        ("bar", "youtube", "broad", 4000, 0.007, 2.6, 80),
        ("kombucha", "instagram", "lal", 7000, 0.020, 3.8, 210),
        ("kombucha", "meta", "broad", 5000, 0.015, 3.3, 160),
    ],
}

# Scripted events. Day index d: 0..59 (59 == AS_OF).
# campaign events: (company, sku, platform, audience) -> dict(start, ramp, ctr, cpm, cvr, freq)
CAMPAIGN_EVENTS = {
    ("fashion", "blazer", "meta", "lal"): dict(start=54, ramp=3, ctr=0.46, cpm=1.06, cvr=1.0, freq=2.4),
    ("fashion", "denim", "meta", "broad"): dict(start=52, ramp=3, ctr=1.0, cpm=1.0, cvr=0.70, freq=1.0),
    ("fashion", "dress", "instagram", "lal"): dict(start=55, ramp=2, ctr=1.0, cpm=1.45, cvr=1.0, freq=1.0),
    ("startup", "serum", "instagram", "lal"): dict(start=53, ramp=2, ctr=1.0, cpm=1.0, cvr=0.52, freq=1.0),
    ("startup", "cleanser", "meta", "broad"): dict(start=55, ramp=2, ctr=0.97, cpm=1.50, cvr=1.0, freq=1.0),
    ("electronics", "speaker", "google", "int"): dict(start=55, ramp=2, ctr=1.0, cpm=1.55, cvr=1.0, freq=1.0),
    ("food", "granola", "meta", "broad"): dict(start=53, ramp=3, ctr=0.62, cpm=1.04, cvr=1.0, freq=2.0),
}
# SKU events: (company, sku) -> dict(cost_mult, cost_start, comp_mult, comp_start)
SKU_EVENTS = {
    ("fashion", "denim"): dict(comp_mult=0.80, comp_start=52),
    ("fashion", "bag"): dict(cost_mult=1.16, cost_start=51),
    ("electronics", "earbuds"): dict(cost_mult=1.17, cost_start=50),
    ("electronics", "watch"): dict(cost_mult=1.03, cost_start=52),
}

CREATIVE_AGE_DAYS = {  # creative age at AS_OF (default 12-30 random); fatigued ones are old
    ("fashion", "blazer", "meta", "lal"): 49,
    ("food", "granola", "meta", "broad"): 41,
}


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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
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
