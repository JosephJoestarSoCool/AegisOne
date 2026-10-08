"""Projected Impact: real history -> approval point -> projection built from the optimizer's own recommendation."""
import numpy as np
import pytest

from app import feedback as fb
from app import service as svc
from app.config import AS_OF
from app.metrics import daily_series

BRANDS = ["nike", "samsung", "lenovo", "lv", "supreme"]


def _first_rec(con, company, rec_type=None):
    recs = svc.build_plan(con, company)["recommendations"]
    return next(r for r in recs if rec_type is None or r["rec_type"] == rec_type)


@pytest.mark.parametrize("b", BRANDS)
def test_history_is_the_real_reconciled_daily_series(con, b):
    rec = _first_rec(con, b)
    out = svc.projected_impact(con, b, rec["rec_id"])
    real = daily_series(svc.get_data(con, b)).tail(svc.HISTORY_POINTS)
    assert [h["date"] for h in out["history"]] == list(real["date"])
    for key in ("spend", "revenue", "profit"):
        assert np.allclose([h[key] for h in out["history"]], real[key].to_numpy())      # nothing invented, nothing smoothed
    assert out["history"][-1]["date"] == AS_OF.isoformat() == out["as_of"]              # history stops at the approval point
    assert out["projection"][0]["date"] > out["as_of"] and len(out["projection"]) == out["horizon_days"] == 30


@pytest.mark.parametrize("b", BRANDS)
def test_projection_is_the_recommendations_own_engine_output(con, b):
    rec = _first_rec(con, b)
    out = svc.projected_impact(con, b, rec["rec_id"])
    assert out["rec"]["expected_profit"] == rec["expected_profit"] and out["rec"]["confidence"] == rec["confidence"]
    assert out["increment"]["profit"] == rec["expected_profit"]
    for r in out["projection"]:                                   # approved − no-action = the engine's increment, on the history's weekday shape
        assert (r["profit"] - r["base_profit"]) == pytest.approx(rec["expected_profit"] * r["profit_shape"])


def test_projection_is_not_a_straight_line_and_follows_the_measured_weekday_shape(con):
    out = svc.projected_impact(con, "nike", _first_rec(con, "nike")["rec_id"])
    prof = np.array([r["profit"] for r in out["projection"]])
    assert np.abs(np.diff(prof, 2)).max() > 1e-6                   # weekday pattern, not a ramp to a target
    shapes = {r["date"]: r["profit_shape"] for r in out["projection"]}
    assert max(shapes.values()) > min(shapes.values())
    assert np.mean(list(shapes.values())) == pytest.approx(1.0, abs=0.08)


def test_spend_follows_the_recommendation_type_and_revenue_is_derived(con):
    mv = svc.projected_impact(con, "nike", _first_rec(con, "nike", "move_budget")["rec_id"])
    assert mv["increment"]["spend"] == 0                           # moving budget keeps total spend
    assert all(r["spend"] == pytest.approx(r["base_spend"]) for r in mv["projection"])
    assert next(m for m in mv["metrics"] if m["key"] == "revenue")["derived"] and next(m for m in mv["metrics"] if m["key"] == "roas")["derived"]
    assert not next(m for m in mv["metrics"] if m["key"] == "profit")["derived"]
    tail = mv["history"][-7:]
    margin = sum(h["profit"] + h["spend"] for h in tail) / sum(h["revenue"] for h in tail)
    assert mv["increment"]["revenue"] == pytest.approx((mv["increment"]["profit"] + mv["increment"]["spend"]) / margin)


@pytest.mark.parametrize("b", BRANDS)
def test_brand_isolation(con, b):
    mine = _first_rec(con, b)["rec_id"]
    other = next(o for o in BRANDS if o != b)
    assert svc.projected_impact(con, other, mine) is None          # another brand's recommendation is never projected here
    out = svc.projected_impact(con, b, mine)
    assert out["company_id"] == b
    a = svc.projected_impact(con, other, _first_rec(con, other)["rec_id"])
    assert [h["profit"] for h in out["history"]] != [h["profit"] for h in a["history"]]


def test_feedback_can_compare_projected_with_observed(con):
    rec = _first_rec(con, "nike")
    proj = svc.projected_impact(con, "nike", rec["rec_id"])
    res = fb.record_decision(con, rec, True)
    assert res["predicted_profit"] == proj["increment"]["profit"]            # the projection IS what the feedback loop scores
    assert res["error"] == pytest.approx(res["actual_profit"] - res["predicted_profit"], abs=1.0)
    again = svc.projected_impact(con, "nike", rec["rec_id"])
    assert again["rec"]["expected_profit"] == proj["rec"]["expected_profit"]
    item = next(i for i in fb.history(con, "nike")["items"] if i["rec_id"] == rec["rec_id"])
    assert item["expected_profit"] == proj["increment"]["profit"] and item["actual_profit"] == res["actual_profit"]


def test_api_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    rid = c.get("/api/plan", params={"company_id": "lv"}).json()["recommendations"][0]["rec_id"]
    ok = c.get("/api/projected-impact", params={"company_id": "lv", "rec_id": rid})
    assert ok.status_code == 200 and ok.json()["company_id"] == "lv"
    assert c.get("/api/projected-impact", params={"company_id": "nike", "rec_id": rid}).status_code == 404
    assert c.get("/api/projected-impact", params={"company_id": "nope", "rec_id": rid}).status_code == 404
