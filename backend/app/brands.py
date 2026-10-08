"""Brand / company data layer.

Single place that turns (public catalog data) + (demo assumptions) into the tables the generator writes.
Nothing here is first-party brand data. Every field is tagged with its provenance class:

  PUBLIC       product name, category, INR price, popularity signal  <- data/processed/catalog_<brand>.csv
  ASSUMPTION   policy weights/guardrails, unit-cost ratios, inventory cover, lead times, scripted events
  SIMULATED    campaign spend/impressions/clicks/orders, derived from PUBLIC popularity + ASSUMPTION parameters
"""
from __future__ import annotations

import json

import pandas as pd

from .config import DATA_DIR

PROCESSED = DATA_DIR / "processed"

SIM_LABEL = "Simulated marketing performance derived from public product/sales signals"

# --- per-brand demo definition ------------------------------------------------------------------------
BRANDS: dict[str, dict] = {
    "nike": dict(
        name="Nike", vertical="Athletic footwear", ticker="NK",
        description="Growth-minded footwear brand. Scales profitable product lines hard; accepts moderate CAC for repeat buyers.",
        policy_summary="Growth + profitable product scaling",
        policy=dict(w_profitability=0.24, w_growth=0.24, w_revenue=0.16, w_inventory=0.08, w_cac=0.13, w_risk=0.15,
                    min_margin=0.35, max_cac=2800, min_roas=3.0, inventory_target_days=45,
                    ltv_per_customer=6000, price_elasticity=1.2, risk_label="Medium risk tolerance"),
        policy_rationale="Demo assumption: growth weight is raised to reward new-customer acquisition, margin floor stays at 35%.",
        cost_ratio=0.56, cost_spread=0.06, budget_scale=1.0, roas_scale=1.0, cpm_scale=1.0, organic=6.0,
        cover=[60, 45, 52, 40, 70, 38], lead=[25, 25, 25, 25, 28, 25],
        events=dict(campaign={0: dict(start=54, ramp=3, ctr=0.46, cpm=1.06, cvr=1.0, freq=2.4),
                              4: dict(start=52, ramp=3, ctr=1.0, cpm=1.0, cvr=0.70, freq=1.0),
                              6: dict(start=55, ramp=2, ctr=1.0, cpm=1.45, cvr=1.0, freq=1.0)},
                    sku={4: dict(cost_mult=1.12, cost_start=51), 2: dict(comp_mult=0.85, comp_start=52)},
                    age={0: 49}),
    ),
    "samsung": dict(
        name="Samsung", vertical="Consumer electronics", ticker="SS",
        description="Thin-margin devices across a lifecycle ladder. Inventory age and margin discipline dominate.",
        policy_summary="Margin + inventory + product lifecycle",
        policy=dict(w_profitability=0.27, w_growth=0.08, w_revenue=0.15, w_inventory=0.22, w_cac=0.13, w_risk=0.15,
                    min_margin=0.18, max_cac=3200, min_roas=4.5, inventory_target_days=35,
                    ltv_per_customer=5000, price_elasticity=1.8, risk_label="Medium risk tolerance"),
        policy_rationale="Demo assumption: inventory weight is high because older models lose value as new generations launch.",
        cost_ratio=0.74, cost_spread=0.05, budget_scale=1.5, roas_scale=1.25, cpm_scale=1.0, organic=8.0,
        cover=[40, 70, 45, 95, 50, 35], lead=[30, 30, 32, 32, 35, 35],
        events=dict(campaign={2: dict(start=55, ramp=2, ctr=1.0, cpm=1.55, cvr=1.0, freq=1.0),
                              0: dict(start=53, ramp=2, ctr=1.0, cpm=1.0, cvr=0.58, freq=1.0),
                              10: dict(start=53, ramp=3, ctr=0.62, cpm=1.04, cvr=1.0, freq=2.0)},
                    sku={1: dict(cost_mult=1.10, cost_start=50)}, age={10: 41}),
    ),
    "lenovo": dict(
        name="Lenovo", vertical="PCs & laptops", ticker="LN",
        description="Very thin hardware margins. Every rupee must clear a strict ROAS bar; product mix matters more than volume.",
        policy_summary="Profitability + enterprise/product mix",
        policy=dict(w_profitability=0.34, w_growth=0.06, w_revenue=0.14, w_inventory=0.12, w_cac=0.20, w_risk=0.14,
                    min_margin=0.12, max_cac=3500, min_roas=6.0, inventory_target_days=40,
                    ltv_per_customer=7000, price_elasticity=1.9, risk_label="Medium risk tolerance"),
        policy_rationale="Demo assumption: profitability and CAC discipline dominate because hardware margin is thin.",
        cost_ratio=0.83, cost_spread=0.035, budget_scale=1.4, roas_scale=1.7, cpm_scale=1.0, organic=4.0,
        cover=[55, 42, 48, 38, 80, 44], lead=[35, 35, 35, 38, 38, 40],
        events=dict(campaign={9: dict(start=55, ramp=2, ctr=1.0, cpm=1.5, cvr=1.0, freq=1.0),
                              3: dict(start=53, ramp=2, ctr=1.0, cpm=1.0, cvr=0.55, freq=1.0),
                              0: dict(start=54, ramp=3, ctr=0.5, cpm=1.05, cvr=1.0, freq=2.3)},
                    sku={0: dict(cost_mult=1.05, cost_start=52)}, age={0: 47}),
    ),
    "lv": dict(
        name="Louis Vuitton", vertical="Luxury goods", ticker="LV",
        description="Protects margin and brand positioning; low risk tolerance; will not chase volume with discounting or low-quality reach.",
        policy_summary="Margin + premium positioning + risk control",
        policy=dict(w_profitability=0.30, w_growth=0.04, w_revenue=0.10, w_inventory=0.10, w_cac=0.10, w_risk=0.36,
                    min_margin=0.55, max_cac=45000, min_roas=3.0, inventory_target_days=60,
                    ltv_per_customer=120000, price_elasticity=0.6, risk_label="Low risk tolerance"),
        policy_rationale="Demo assumption: risk weight is highest — brand dilution costs more than a missed sale.",
        cost_ratio=0.32, cost_spread=0.05, budget_scale=6.0, roas_scale=0.95, cpm_scale=1.3, organic=0.9,
        cover=[70, 80, 65, 90, 60, 75], lead=[40, 45, 35, 40, 30, 28],
        events=dict(campaign={0: dict(start=54, ramp=3, ctr=0.46, cpm=1.06, cvr=1.0, freq=2.4),
                              6: dict(start=55, ramp=2, ctr=1.0, cpm=1.45, cvr=1.0, freq=1.0),
                              4: dict(start=52, ramp=3, ctr=1.0, cpm=1.0, cvr=0.72, freq=1.0)},
                    sku={3: dict(cost_mult=1.14, cost_start=51)}, age={0: 49}),
    ),
    "supreme": dict(
        name="Supreme", vertical="Streetwear", ticker="SP",
        description="Scarcity-driven drops. Stock is short by design; premium margin and controlled growth beat volume.",
        policy_summary="Inventory scarcity + premium margin + controlled growth",
        policy=dict(w_profitability=0.24, w_growth=0.14, w_revenue=0.10, w_inventory=0.22, w_cac=0.10, w_risk=0.20,
                    min_margin=0.45, max_cac=3500, min_roas=3.0, inventory_target_days=14,
                    ltv_per_customer=5000, price_elasticity=0.7, risk_label="Medium-low risk tolerance"),
        policy_rationale="Demo assumption: inventory weight is high and cover short; selling out is the product strategy.",
        cost_ratio=0.40, cost_spread=0.06, budget_scale=0.7, roas_scale=1.1, cpm_scale=1.0, organic=3.0,
        cover=[75, 56, 82, 54, 64, 46], lead=[40, 38, 35, 38, 35, 40],
        events=dict(campaign={2: dict(start=53, ramp=2, ctr=1.0, cpm=1.0, cvr=0.55, freq=1.0),
                              10: dict(start=53, ramp=3, ctr=0.6, cpm=1.04, cvr=1.0, freq=2.1),
                              7: dict(start=55, ramp=2, ctr=1.0, cpm=1.4, cvr=1.0, freq=1.0)},
                    sku={0: dict(cost_mult=1.10, cost_start=51)}, age={10: 42}),
    ),
}
DEFAULT_BRAND = "nike"
ORDER = ["nike", "samsung", "lenovo", "lv", "supreme"]

# Campaign template shared by all brands: (slot, platform, audience, daily_budget, ctr, platform_roas, cpm)
TEMPLATE = [
    (0, "meta", "lal", 40000, 0.016, 5.3, 270), (0, "google", "rt", 14000, 0.030, 6.7, 700),
    (1, "google", "int", 22000, 0.026, 6.5, 358), (1, "instagram", "lal", 12000, 0.019, 4.4, 280),
    (2, "meta", "broad", 26000, 0.013, 4.4, 250), (2, "google", "rt", 9000, 0.030, 5.5, 650),
    (3, "instagram", "lal", 24000, 0.014, 5.0, 290), (3, "youtube", "broad", 10000, 0.006, 3.6, 110),
    (4, "meta", "rt", 12000, 0.028, 5.7, 520), (4, "google", "int", 18000, 0.020, 4.8, 420),
    (5, "meta", "broad", 16000, 0.015, 4.0, 240), (5, "instagram", "lal", 10000, 0.015, 3.3, 270),
]


def _u(*parts) -> float:
    import hashlib
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def catalog(brand: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / f"catalog_{brand}.csv")


def sources() -> dict:
    return json.loads((PROCESSED / "sources.json").read_text(encoding="utf-8"))


def build_tables(brand_ids: list[str] | None = None):
    """Return (COMPANIES, SKUS, CAMPAIGNS, CAMPAIGN_EVENTS, SKU_EVENTS, CREATIVE_AGE_DAYS) in datagen's formats."""
    companies, skus, campaigns, cev, sev, ages = {}, {}, {}, {}, {}, {}
    for bid in brand_ids or ORDER:
        b = BRANDS[bid]
        cat = catalog(bid)
        companies[bid] = dict(name=b["name"], vertical=b["vertical"], description=b["description"], profile=dict(b["policy"]))
        keys, pops, rows = [], [], []
        for i, r in cat.iterrows():
            pop = float(r.popularity)
            cost = round(float(r.price_inr) * (b["cost_ratio"] + b["cost_spread"] * (_u(bid, i, "cost") - 0.5) * 2), 0)
            organic = round(b["organic"] * (0.4 + pop), 2)
            lead = b["lead"][i]
            rows.append((r.sku_key, r["name"], r.category, float(r.price_inr), cost, 9999, None, lead, organic))
            keys.append(r.sku_key)
            pops.append(pop)
        camps, est = [], {k: 0.0 for k in keys}
        for ti, (slot, plat, aud, bud, ctr, roas, cpm) in enumerate(TEMPLATE):
            pop = pops[slot]
            q = 0.8 + 0.4 * pop                      # public popularity -> simulated conversion quality
            camp = (keys[slot], plat, aud, round(bud * b["budget_scale"], -2), ctr,
                    round(roas * b["roas_scale"] * q, 2), round(cpm * b["cpm_scale"], 0))
            camps.append(camp)
            est[keys[slot]] += camp[3] * camp[5] / rows[slot][3] / 1.2
        skus[bid] = []
        for i, (k, n, c, p, cost, shelf, _, lead, org) in enumerate(rows):
            on_hand = int(round(b["cover"][i] * (est[k] + org)))
            skus[bid].append((k, n, c, p, cost, shelf, max(on_hand, 10), lead, org))
        campaigns[bid] = camps
        for ti, ev in b["events"]["campaign"].items():
            slot, plat, aud = TEMPLATE[ti][:3]
            cev[(bid, keys[slot], plat, aud)] = ev
        for slot, ev in b["events"]["sku"].items():
            sev[(bid, keys[slot])] = ev
        for ti, age in b["events"]["age"].items():
            slot, plat, aud = TEMPLATE[ti][:3]
            ages[(bid, keys[slot], plat, aud)] = age
    return companies, skus, campaigns, cev, sev, ages


def public_meta() -> dict:
    """Brand metadata for the API / UI, including per-field provenance classes."""
    src = sources()
    out = {}
    for bid in ORDER:
        b = BRANDS[bid]
        s = src[bid]
        out[bid] = dict(
            company_id=bid, ticker=b["ticker"], policy_summary=b["policy_summary"], policy_rationale=b["policy_rationale"],
            assumptions=dict(unit_cost_ratio=b["cost_ratio"], budget_scale=b["budget_scale"],
                             inventory_cover_days=b["cover"], lead_time_days=b["lead"]),
            public_source=dict(name=s["name"], url=s["url"], license=s["license"], rows=s["source_rows"]),
            provenance=dict(
                public=["product names", "categories", "INR list prices", "popularity signal"],
                assumption=["policy weights & guardrails", "unit-cost ratio", "inventory cover & lead time", "scripted anomalies"],
                simulated=["spend", "impressions", "clicks", "orders", "ROAS", "CAC"]),
            sim_label=SIM_LABEL)
    return out
