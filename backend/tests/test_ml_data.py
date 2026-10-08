"""Data provenance, ML model, and the ML -> decision-engine connection. No hard-coded result numbers."""
import json

import numpy as np
import pandas as pd
import pytest

from app import ingest, ml
from app import service as svc
from app.brands import BRANDS, ORDER, TEMPLATE, catalog, public_meta, sources
from app.metrics import build_state
from app.service import get_data

REQ_SOURCE_KEYS = ["name", "url", "license", "type", "contains", "does_not_contain", "used_for", "limitations",
                   "ingested", "source_rows", "date_range", "processed_file", "scope", "publisher"]


@pytest.fixture(scope="module")
def card():
    return ml.train()


# ---------------------------------------------------------------- data / provenance
@pytest.mark.parametrize("b", ORDER)
def test_catalog_schema(b):
    c = catalog(b)
    assert {"name", "category", "price_inr", "popularity", "sku_key"} <= set(c.columns)
    assert len(c) == len({s for s in c.sku_key}) == max(t[0] for t in TEMPLATE) + 1
    assert (c.price_inr > 0).all() and c.popularity.between(0, 1).all()


def test_ad_dataset_schema_and_validation(tmp_path):
    df = pd.read_csv(ml.PROCESSED / "ad_conversions.csv")
    assert {"Impressions", "Clicks", "Spent", "Approved_Conversion"} <= set(df.columns)
    assert (df.Clicks <= df.Impressions).all() and (df[["Impressions", "Clicks", "Spent"]] >= 0).all().all()
    raw = pd.read_csv(ingest.RAW / ingest.SOURCES["marketing"]["file"])
    bad = tmp_path / "bad.csv"
    raw.assign(Clicks=raw.Impressions + 1).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="clicks > impressions"):
        ingest.marketing(bad)


def test_ingest_rejects_changed_schema():
    with pytest.raises(ValueError, match="schema changed"):
        ingest._need(pd.DataFrame({"a": [1]}), ["a", "b"], "x")


def test_every_source_documents_provenance():
    src = sources()
    assert set(src) == set(ORDER) | {"marketing"}
    for sid, s in src.items():
        for k in REQ_SOURCE_KEYS:
            assert s.get(k) not in (None, ""), (sid, k)
        assert s["url"].startswith("https://")
        assert "ad" in s["does_not_contain"].lower() or "Any brand" in s["does_not_contain"]
        assert (ingest.PROCESSED / s["processed_file"]).exists()


def test_brand_meta_separates_public_assumption_simulated():
    for b, m in public_meta().items():
        assert set(m["provenance"]) == {"public", "assumption", "simulated"}
        assert "spend" in m["provenance"]["simulated"] and "spend" not in m["provenance"]["public"]
        assert "Simulated" in m["sim_label"]


# ---------------------------------------------------------------- brand switching
def test_brand_switch_changes_decision_context(con):
    plans = {b: svc.build_plan(con, b) for b in ORDER}
    assert len({p["next_rupee"]["sku_id"] for p in plans.values()}) == len(ORDER)
    assert len({tuple(p["policy"]["weights"].values()) for p in plans.values()}) == len(ORDER)
    assert len({round(p["policy"]["min_roas"], 2) for p in plans.values()}) >= 3
    for b, p in plans.items():
        names = set(catalog(b).name)
        assert {c["sku_name"] for c in p["campaigns"].values()} <= names     # product names come from the public catalog


# ---------------------------------------------------------------- model
def test_model_trains_and_beats_baseline(card):
    assert card["n_features"] == len(ml.FEATURES) == len(card["features"])
    assert {f["feature"] for f in card["features"]} == set(ml.FEATURES)
    v = card["validation"]
    assert v["cv_deviance"] < v["baseline_deviance"]                  # real skill over the constant-rate baseline
    assert 0.9 < v["calibration_ratio"] < 1.1
    assert abs(sum(f["importance"] for f in card["features"]) - 1) < 0.01
    assert card["model_type"] in card["candidates"]
    assert card["candidates"][card["model_type"]]["cv_deviance"] == min(c["cv_deviance"] for c in card["candidates"].values())
    n = pd.read_csv(ml.PROCESSED / "ad_conversions.csv").query("Clicks > 0").shape[0]
    assert card["n_records"] == n


def test_quartile_lift_is_ordered(card):
    actual = [q["actual"] for q in sorted(card["quartile_lift"], key=lambda q: q["quartile"])]
    assert actual[-1] > actual[0]


def test_prediction_output(con):
    d = get_data(con, "nike")
    states = build_state(d)
    assert all(s["ml"] and set(s["ml"]["features"]) == set(ml.FEATURES) for s in states)
    assert all(0 < s["ml"]["conv_rate_per_click"] < 1 for s in states)
    lo, hi = ml.ML_CLIP
    assert all(lo - 1e-9 <= s["ml"]["lift"] <= hi + 1e-9 for s in states)


# ---------------------------------------------------------------- ML -> optimizer -> next rupee
@pytest.mark.parametrize("b", ORDER)
def test_ml_feeds_optimizer_but_is_bounded(con, b):
    d = get_data(con, b)
    on, off = build_state(d, ml=True), build_state(d, ml=False)
    for a, z in zip(on, off):
        assert a["orders0"] == pytest.approx(z["orders0"] * a["ml"]["lift"])
        assert a["b0"] == z["b0"] and a["margin"] == z["margin"]       # ML never touches business inputs
    assert any(abs(a["ml"]["lift"] - 1) > 1e-6 for a in on)


@pytest.mark.parametrize("b", ORDER)
def test_trace_matches_engine(con, b):
    t = svc.ml_trace(con, b)
    plan = svc.build_plan(con, b)
    nr = plan["next_rupee"]
    assert t["campaign_id"] == nr["campaign_id"] and t["is_winner"]
    assert t["decision"]["winner_campaign_id"] == nr["campaign_id"]
    m = t["model"]
    assert m["orders_after_ml"] == pytest.approx(m["orders_before_ml"] * m["multiplier"])
    assert t["cfo"]["profit_per_rupee"] == pytest.approx(nr["profit_per_rupee"])
    assert t["cfo"]["policy_value_per_rupee"] == pytest.approx(nr["policy_value_per_rupee"])
    assert m["incremental_revenue_per_step"] > 0
    # policy layer is deterministic and still gates: an ineligible campaign can never be the winner
    assert t["cfo"]["eligible"]


def test_ml_cannot_override_guardrails(con):
    """Gated campaigns stay gated with ML on: the CFO layer, not the model, decides."""
    on = svc.build_plan(con, "supreme")
    off = svc.build_plan(con, "supreme", scenario={"ml": False})
    gated_on = {c["campaign_id"] for c in on["candidates"] if not c["eligible"] and "margin" in (c["gate_reason"] or "")}
    gated_off = {c["campaign_id"] for c in off["candidates"] if not c["eligible"] and "margin" in (c["gate_reason"] or "")}
    assert gated_on == gated_off


def test_scope_and_unknown_license_are_stated_honestly():
    src = sources()
    for b in ORDER:
        assert "not first-party" in src[b]["scope"] and src[b]["scope"].startswith("Brand-specific")
    assert src["marketing"]["scope"].startswith("Generic marketing data")
    assert src["lv"]["license"] == "Unknown"          # never invent licensing information
    assert all(s["license"] for s in src.values())
