"""The deterministic judge demo: data -> diagnosis -> decision -> what-if -> feedback."""
from __future__ import annotations

from . import service as svc

DEMO_COMPANY = "nike"
DEMO_STOCK_FRACTION = 0.5   # what-if: a supplier delay leaves the winning product with only enough stock for organic demand


def _pick(con):
    """Choose the demo actors from the live engine: no hard-coded winner."""
    plan = svc.build_plan(con, DEMO_COMPANY)
    anomaly = next(a for a in plan["anomalies"] if a["kind"] == "creative_fatigue" and a.get("campaign_id"))
    decision = next(r for r in plan["recommendations"] if r["rec_type"] == "move_budget"
                    and r["source_campaign_id"] == anomaly["campaign_id"])
    return plan, anomaly, decision


def demo(con) -> dict:
    d = svc.get_data(con, DEMO_COMPANY)
    plan, anomaly, decision = _pick(con)
    DEMO_CAMPAIGN = anomaly["campaign_id"]
    DEMO_TARGET_SKU = plan["next_rupee"]["sku_id"]
    prod = d.products.set_index("sku_id").loc[DEMO_TARGET_SKU]
    lead = float(d.inventory.set_index("sku_id").loc[DEMO_TARGET_SKU, "lead_time_days"])
    DEMO_STOCK_UNITS = int(round(lead * float(prod["organic_units_per_day"]) * DEMO_STOCK_FRACTION)) or 1
    scenario = {"sku_overrides": {DEMO_TARGET_SKU: {"on_hand": DEMO_STOCK_UNITS}}}
    wi = svc.whatif(con, DEMO_COMPANY, scenario, base=plan)
    sku = plan["campaigns"][decision["target_campaign_id"]]
    return dict(
        company_id=DEMO_COMPANY, campaign_id=DEMO_CAMPAIGN, target_sku=DEMO_TARGET_SKU,
        scenario=scenario,
        step1_data=dict(reconciliation=svc.reconciliation(d), campaign=plan["campaigns"][DEMO_CAMPAIGN],
                        series=svc.campaign_series(con, DEMO_COMPANY, DEMO_CAMPAIGN)["series"]),
        step2_diagnosis=anomaly,
        step_compare=dict(next_rupee=plan["next_rupee"], roas_trap=plan["roas_trap"], candidates=plan["candidates"]),
        step3_decision=decision,
        step4_whatif=dict(
            scenario=scenario, stock_units=DEMO_STOCK_UNITS, changed=wi["changed"], next_rupee=wi["next_rupee"], narrative=wi["narrative"],
            top_before=wi["top_before"], top_after=wi["top_after"], profit_delta=wi["profit_delta"],
            recommendations_after=wi["scenario"]["recommendations"][:4], allocation_diff=wi["allocation_diff"],
            target_cover_before=sku["inventory_days"],
            target_cover_after=wi["scenario"]["campaigns"][decision["target_campaign_id"]]["inventory_days"],
        ),
    )
