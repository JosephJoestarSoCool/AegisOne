"""FastAPI app for the Autonomous Marketing CFO."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import feedback as fb
from . import service as svc
from .db import connect, ensure_db, read
from .demo import demo as run_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db()
    yield


app = FastAPI(title="AegisOne — Autonomous Marketing CFO", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _company(con, company_id: str) -> None:
    if not con.execute("SELECT 1 FROM companies WHERE company_id=?", (company_id,)).fetchone():
        con.close()
        raise HTTPException(404, f"unknown company {company_id}")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/companies")
def companies():
    con = connect()
    try:
        from .metrics import all_policies
        pols = all_policies(con)
        rows = read(con, "SELECT * FROM companies")
        return [dict(**r, policy=pols[r["company_id"]].to_dict()) for r in rows.to_dict("records")]
    finally:
        con.close()


@app.get("/api/overview")
def overview(company_id: str, policy_id: str | None = None):
    con = connect()
    try:
        _company(con, company_id)
        return svc.overview(con, company_id, policy_id)
    finally:
        con.close()


@app.get("/api/plan")
def plan(company_id: str, policy_id: str | None = None):
    con = connect()
    try:
        _company(con, company_id)
        return svc.build_plan(con, company_id, policy_id)
    finally:
        con.close()


@app.get("/api/diagnosis")
def diagnosis(company_id: str, policy_id: str | None = None):
    con = connect()
    try:
        _company(con, company_id)
        p = svc.build_plan(con, company_id, policy_id)
        return dict(anomalies=p["anomalies"], campaigns=p["campaigns"], recommendations=p["recommendations"])
    finally:
        con.close()


@app.get("/api/campaign-series")
def campaign_series(company_id: str, campaign_id: str):
    con = connect()
    try:
        _company(con, company_id)
        return svc.campaign_series(con, company_id, campaign_id)
    finally:
        con.close()


@app.post("/api/whatif")
def whatif(body: dict = Body(...)):
    con = connect()
    try:
        company_id = body.get("company_id")
        _company(con, company_id)
        return svc.whatif(con, company_id, body.get("scenario") or {}, body.get("policy_id"))
    finally:
        con.close()


@app.get("/api/policy-compare")
def policy_compare(company_id: str):
    con = connect()
    try:
        _company(con, company_id)
        return svc.compare_policies(con, company_id)
    finally:
        con.close()


@app.post("/api/recommendations/decide")
def decide(body: dict = Body(...)):
    """body: {recommendation: {...}, approve: bool}"""
    rec = body.get("recommendation")
    if not rec or "rec_id" not in rec:
        raise HTTPException(400, "recommendation required")
    con = connect()
    try:
        _company(con, rec["company_id"])
        return fb.record_decision(con, rec, bool(body.get("approve", True)))
    finally:
        con.close()


@app.get("/api/history")
def history(company_id: str):
    con = connect()
    try:
        _company(con, company_id)
        return fb.history(con, company_id)
    finally:
        con.close()


@app.get("/api/demo")
def demo():
    con = connect()
    try:
        return run_demo(con)
    finally:
        con.close()


@app.post("/api/reset")
def reset():
    """Regenerate the synthetic database and clear caches (also clears learned feedback)."""
    from .datagen import build_database
    build_database()
    svc.clear_cache()
    return {"status": "reset"}
