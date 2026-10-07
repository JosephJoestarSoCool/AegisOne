import math

import pytest

from app import feedback as fb
from app import service as svc
from app.demo import DEMO_CAMPAIGN, DEMO_COMPANY, demo
from app.metrics import build_state, load_company

COMPANIES = ["fashion", "startup", "electronics", "food"]
REQUIRED_TABLES = ["companies", "company_profiles", "campaigns", "products", "platforms", "audiences", "creatives",
                   "ad_metrics", "sales", "inventory", "pricing", "competitor_prices", "recommendations", "feedback"]


def test_schema_and_relationships(con):
    for t in REQUIRED_TABLES:
        assert con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] > 0, t
    # every campaign resolves company -> sku -> platform/audience/creative -> daily metrics
    orphans = con.execute(
        "SELECT COUNT(*) FROM campaigns c LEFT JOIN products p USING(sku_id) LEFT JOIN platforms pl USING(platform_id) "
        "LEFT JOIN audiences a USING(audience_id) LEFT JOIN creatives cr USING(creative_id) "
        "WHERE p.sku_id IS NULL OR pl.platform_id IS NULL OR a.audience_id IS NULL OR cr.creative_id IS NULL").fetchone()[0]
    assert orphans == 0
    assert con.execute("SELECT COUNT(*) FROM campaigns c LEFT JOIN ad_metrics m USING(campaign_id) "
                       "WHERE m.campaign_id IS NULL").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(DISTINCT company_id) FROM company_profiles").fetchone()[0] == 4


@pytest.mark.parametrize("cid", COMPANIES)
def test_policy_weights_sum_to_one(con, cid):
    d = svc.get_data(con, cid)
    assert math.isclose(sum(d.policy.weights.values()), 1.0, abs_tol=1e-6)


@pytest.mark.parametrize("cid", COMPANIES)
def test_reconciliation_and_metrics(con, cid):
    d = load_company(con, cid)
    assert ((d.recon.recon_factor >= 0.55) & (d.recon.recon_factor <= 1.0)).all()
    for s in build_state(d):
        for k in ("roas", "cac", "ctr", "cpc", "cvr", "profit", "margin", "inventory_days", "stockout_risk"):
            assert k in s and math.isfinite(s[k])
        assert 0 <= s["stockout_risk"] <= 1
        assert 0.4 <= s["elasticity"] <= 0.96


@pytest.mark.parametrize("cid", COMPANIES)
def test_every_anomaly_is_explained(con, cid):
    plan = svc.build_plan(con, cid)
    assert plan["anomalies"], "scripted anomalies should be found"
    for a in plan["anomalies"]:
        assert a["what_happened"] and a["probable_cause"] and a["recommended_action"]
        assert 0 < a["confidence"] <= 1


def test_demo_diagnosis_is_creative_fatigue(con):
    plan = svc.build_plan(con, DEMO_COMPANY)
    a = next(x for x in plan["anomalies"] if x.get("campaign_id") == DEMO_CAMPAIGN)
    assert a["kind"] == "creative_fatigue" and a["confidence"] >= 0.85
    assert a["raw"]["roas_now"] < 0.6 * a["raw"]["roas_base"]


@pytest.mark.parametrize("cid", COMPANIES)
def test_optimizer_conserves_budget_and_explains(con, cid):
    plan = svc.build_plan(con, cid)
    t = plan["totals"]
    assert math.isclose(t["budget_before"], t["budget_after"], rel_tol=1e-9)
    assert t["incremental_profit"] >= 0
    for r in plan["recommendations"]:
        assert r["why"], "every recommendation must explain why"
        if r["rec_type"] == "move_budget":
            assert all(g["ok"] for g in r["guardrails"] if "ROAS" in g["label"] or "Margin" in g["label"])


def test_demo_headline_move_is_12000(con):
    dm = demo(con)
    r = dm["step3_decision"]
    assert r["rec_type"] == "move_budget" and r["amount"] == 12000
    assert r["source_campaign_id"] == DEMO_CAMPAIGN
    assert "Silk Scarf" in r["target_name"]


def test_demo_inventory_change_flips_recommendation(con):
    w = demo(con)["step4_whatif"]
    assert w["changed"]
    assert w["top_before"]["target_id"] != w["top_after"]["target_id"] or w["top_before"]["amount"] != w["top_after"]["amount"]
    assert w["target_cover_after"] < 5 < w["target_cover_before"]


def test_whatif_unchanged_when_nothing_changes(con):
    res = svc.whatif(con, "fashion", {})
    assert not res["changed"] and abs(res["profit_delta"]) < 1e-6


def test_whatif_extra_budget_adds_increase(con):
    res = svc.whatif(con, "fashion", {"total_budget_delta": 10000})
    assert any(r["rec_type"] == "increase_budget" for r in res["scenario"]["recommendations"])
    assert res["scenario"]["totals"]["budget_after"] > res["baseline"]["totals"]["budget_after"]


def test_whatif_margin_override_blocks_scaling(con):
    res = svc.whatif(con, "fashion", {"sku_overrides": {"fashion-scarf": {"unit_cost": 2900}}})
    scarf = [a for a in res["scenario"]["allocation"] if a["sku_id"] == "fashion-scarf"]
    assert all(a["recommended"] <= a["current"] for a in scarf)   # margin below policy floor blocks scaling


def test_same_data_different_policy_different_decision(con):
    cmp_ = svc.compare_policies(con, "fashion")
    vectors = {pid: tuple(m["by_policy"][pid] for m in cmp_["matrix"]) for pid in ("fashion", "startup", "electronics", "food")}
    assert len(set(vectors.values())) >= 3
    den = next(m for m in cmp_["matrix"] if "Denim · Meta" in m["name"])
    assert den["by_policy"]["electronics"] < den["by_policy"]["fashion"]   # strict ROAS bar cuts harder


def test_feedback_loop(con):
    plan = svc.build_plan(con, DEMO_COMPANY)
    rec = plan["recommendations"][0]
    out = fb.record_decision(con, rec, True)
    assert out["predicted_profit"] == rec["expected_profit"]
    assert math.isclose(out["error"], out["actual_profit"] - out["predicted_profit"], abs_tol=1.0)
    h = fb.history(con, DEMO_COMPANY)
    assert any(i["rec_id"] == rec["rec_id"] and i["actual_profit"] is not None for i in h["items"])
    fb.record_decision(con, rec, True)          # idempotent
    again = svc.build_plan(con, DEMO_COMPANY)
    assert next(r for r in again["recommendations"] if r["rec_id"] == rec["rec_id"])["status"] == "approved"
