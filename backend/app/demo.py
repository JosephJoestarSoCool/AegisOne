"""The deterministic judge demo: data -> diagnosis -> decision -> what-if -> feedback."""
from __future__ import annotations

from . import service as svc

DEMO_COMPANY = "fashion"
DEMO_CAMPAIGN = "fashion-c01"          # Linen Blazer · Meta · Lookalike 1%  (creative fatigue)
DEMO_TARGET_SKU = "fashion-scarf"      # Silk Scarf  (best opportunity)
DEMO_STOCK_UNITS = 200                 # what-if: a supplier delay leaves only 200 scarves on hand


def demo(con) -> dict:
    d = svc.get_data(con, DEMO_COMPANY)
    plan = svc.build_plan(con, DEMO_COMPANY)
    anomaly = next(a for a in plan["anomalies"] if a.get("campaign_id") == DEMO_CAMPAIGN)
    decision = next(r for r in plan["recommendations"] if r["rec_type"] == "move_budget"
                    and r["source_campaign_id"] == DEMO_CAMPAIGN)
    scenario = {"sku_overrides": {DEMO_TARGET_SKU: {"on_hand": DEMO_STOCK_UNITS}}}
    wi = svc.whatif(con, DEMO_COMPANY, scenario, base=plan)
    sku = plan["campaigns"][decision["target_campaign_id"]]
    return dict(
        company_id=DEMO_COMPANY, campaign_id=DEMO_CAMPAIGN, target_sku=DEMO_TARGET_SKU,
        scenario=scenario,
        step1_data=dict(reconciliation=svc.reconciliation(d), campaign=plan["campaigns"][DEMO_CAMPAIGN],
                        series=svc.campaign_series(con, DEMO_COMPANY, DEMO_CAMPAIGN)["series"]),
        step2_diagnosis=anomaly,
        step3_decision=decision,
        step4_whatif=dict(
            scenario=scenario, stock_units=DEMO_STOCK_UNITS, changed=wi["changed"], narrative=wi["narrative"],
            top_before=wi["top_before"], top_after=wi["top_after"], profit_delta=wi["profit_delta"],
            recommendations_after=wi["scenario"]["recommendations"][:4], allocation_diff=wi["allocation_diff"],
            target_cover_before=sku["inventory_days"],
            target_cover_after=wi["scenario"]["campaigns"][decision["target_campaign_id"]]["inventory_days"],
        ),
    )
