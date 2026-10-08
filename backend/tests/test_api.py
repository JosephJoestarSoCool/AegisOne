from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_endpoints():
    assert client.get("/api/health").json()["status"] == "ok"
    comps = client.get("/api/companies").json()
    assert {c["company_id"] for c in comps} == {"nike", "samsung", "lenovo", "lv", "supreme"}
    ov = client.get("/api/overview", params={"company_id": "nike"}).json()
    assert ov["kpis"]["revenue"] > 0 and ov["anomaly_count"] > 0
    assert client.get("/api/diagnosis", params={"company_id": "supreme"}).json()["anomalies"]
    assert client.get("/api/plan", params={"company_id": "samsung"}).json()["allocation"]
    assert client.get("/api/policy-compare", params={"company_id": "nike"}).json()["policies"]
    assert client.get("/api/campaign-series", params={"company_id": "nike", "campaign_id": "nike-c01"}).json()["series"]
    assert client.get("/api/overview", params={"company_id": "nope"}).status_code == 404


def test_whatif_decide_and_demo():
    dm = client.get("/api/demo").json()
    body = {"company_id": "nike", "scenario": dm["scenario"]}
    assert client.post("/api/whatif", json=body).json()["changed"]
    out = client.post("/api/recommendations/decide", json={"recommendation": dm["step3_decision"], "approve": True}).json()
    assert out["status"] == "approved" and "actual_profit" in out
    hist = client.get("/api/history", params={"company_id": "nike"}).json()
    assert hist["summary"]["decisions"] >= 7
