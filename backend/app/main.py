"""FastAPI app for the Autonomous Marketing CFO."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import feedback as fb
from . import service as svc
from .db import connect, ensure_db, read
from .demo import demo as run_demo


# Public, non-secret configuration (see backend/.env.example).
DEV_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [o.strip() for o in os.environ.get("AEGIS_CORS_ORIGINS", DEV_ORIGINS).split(",") if o.strip()]
CORS_REGEX = os.environ.get("AEGIS_CORS_ORIGIN_REGEX") or None     # optional, e.g. Vercel preview URLs of this project
ENABLE_RESET = os.environ.get("AEGIS_ENABLE_RESET", "1") != "0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db()          # builds the deterministic demo DB if it is missing (a baked image already has it)
    from . import ml
    ml.load()            # load (or, if the artifact is unusable, retrain) the model at startup, not on the first request
    yield


app = FastAPI(title="AegisOne — Autonomous Marketing CFO", version="1.0.0", lifespan=lifespan)
# Explicit origins only (no wildcard). No cookies or credentials are used, so none are allowed.
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_origin_regex=CORS_REGEX, allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["Content-Type"], allow_credentials=False)


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


@app.get("/api/brands")
def brands():
    """Per-brand provenance & policy metadata (public data vs demo assumptions vs simulation)."""
    from .brands import BRANDS, ORDER, public_meta
    meta = public_meta()
    return [dict(meta[b], name=BRANDS[b]["name"], vertical=BRANDS[b]["vertical"]) for b in ORDER]


@app.get("/api/data-sources")
def data_sources():
    from .brands import sources
    return list(sources().values())


@app.get("/api/ml/card")
def ml_card():
    from . import ml
    return ml.card()


@app.get("/api/ml/trace")
def ml_trace(company_id: str, campaign_id: str | None = None):
    con = connect()
    try:
        _company(con, company_id)
        return svc.ml_trace(con, company_id, campaign_id)
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
    """Regenerate the synthetic database and clear caches (also clears learned feedback). Disable with AEGIS_ENABLE_RESET=0."""
    if not ENABLE_RESET:
        raise HTTPException(403, "reset is disabled on this deployment")
    from .datagen import build_database
    build_database(write_csv=False)
    svc.clear_cache()
    return {"status": "reset"}
