from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_endpoints():
    assert client.get("/api/health").json()["status"] == "ok"
    comps = client.get("/api/companies").json()
    assert {c["company_id"] for c in comps} == {"fashion", "startup", "electronics", "food"}
    ov = client.get("/api/overview", params={"company_id": "fashion"}).json()
    assert ov["kpis"]["revenue"] > 0 and ov["anomaly_count"] > 0
    assert client.get("/api/diagnosis", params={"company_id": "food"}).json()["anomalies"]
    assert client.get("/api/plan", params={"company_id": "startup"}).json()["allocation"]
    assert client.get("/api/policy-compare", params={"company_id": "fashion"}).json()["policies"]
    assert client.get("/api/campaign-series", params={"company_id": "fashion", "campaign_id": "fashion-c01"}).json()["series"]
    assert client.get("/api/overview", params={"company_id": "nope"}).status_code == 404


def test_whatif_decide_and_demo():
    body = {"company_id": "fashion", "scenario": {"sku_overrides": {"fashion-scarf": {"on_hand": 200}}}}
    assert client.post("/api/whatif", json=body).json()["changed"]
    dm = client.get("/api/demo").json()
    out = client.post("/api/recommendations/decide", json={"recommendation": dm["step3_decision"], "approve": True}).json()
    assert out["status"] == "approved" and "actual_profit" in out
    hist = client.get("/api/history", params={"company_id": "fashion"}).json()
    assert hist["summary"]["decisions"] >= 7
