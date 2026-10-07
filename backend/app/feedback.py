"""Closed loop: approve -> simulate outcome -> store prediction/action/actual/error -> update confidence."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime

import numpy as np

from .config import AS_OF


def simulated_outcome(rec_id: str, rec_type: str, predicted: float) -> float:
    """Deterministic 'world response': the model is mildly optimistic on average (≈0.93x) with per-decision noise."""
    u = int(hashlib.sha256(f"outcome|{rec_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    bias = {"replace_creative": 0.88, "pause_campaign": 1.0}.get(rec_type, 0.94)
    factor = bias * (0.88 + 0.24 * u)
    return float(round(predicted * factor, 0))


def _now() -> str:
    return datetime(AS_OF.year, AS_OF.month, AS_OF.day, 10, 0, 0).isoformat()


def record_decision(con: sqlite3.Connection, rec: dict, approve: bool) -> dict:
    rid = rec["rec_id"]
    status = "approved" if approve else "rejected"
    con.execute("DELETE FROM feedback WHERE rec_id=?", (rid,))
    con.execute("DELETE FROM recommendations WHERE rec_id=?", (rid,))
    con.execute(
        "INSERT INTO recommendations (rec_id, company_id, policy_id, created_at, rec_type, title, source_campaign_id,"
        " target_campaign_id, amount, expected_profit, confidence, why, payload, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, rec["company_id"], rec.get("policy_id", rec["company_id"]), _now(), rec["rec_type"], rec["title"],
         rec.get("source_campaign_id"), rec.get("target_campaign_id"), rec.get("amount") or 0.0,
         rec["expected_profit"], rec["confidence"], " ".join(rec.get("why", [])), json.dumps(rec), status))
    if not approve:
        con.commit()
        return dict(rec_id=rid, status=status)

    predicted = float(rec["expected_profit"])
    actual = simulated_outcome(rid, rec["rec_type"], predicted)
    err = actual - predicted
    err_pct = err / predicted if predicted else 0.0
    acc = float(max(0.0, 1 - abs(err_pct)))
    conf_b = float(rec["confidence"])
    conf_a = float(np.clip(conf_b + 0.3 * (acc - conf_b), 0.3, 0.97))
    con.execute(
        "INSERT INTO feedback (rec_id, company_id, predicted_profit, action, actual_profit, error, error_pct,"
        " confidence_before, confidence_after, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (rid, rec["company_id"], predicted, rec["title"], actual, round(err, 2), round(err_pct, 4),
         conf_b, round(conf_a, 3), _now()))
    row = con.execute("SELECT accuracy, n FROM calibration WHERE company_id=? AND rec_type=?",
                      (rec["company_id"], rec["rec_type"])).fetchone()
    if row:
        new_acc, n = 0.7 * row["accuracy"] + 0.3 * acc, row["n"] + 1
        con.execute("UPDATE calibration SET accuracy=?, n=? WHERE company_id=? AND rec_type=?",
                    (new_acc, n, rec["company_id"], rec["rec_type"]))
    else:
        new_acc, n = acc, 1
        con.execute("INSERT INTO calibration VALUES (?,?,?,?)", (rec["company_id"], rec["rec_type"], new_acc, n))
    con.commit()
    return dict(rec_id=rid, status=status, title=rec["title"], predicted_profit=predicted, actual_profit=actual,
                error=round(err, 0), error_pct=round(err_pct, 4), confidence_before=conf_b,
                confidence_after=round(conf_a, 2), calibration_accuracy=round(new_acc, 3), calibration_n=n,
                rec_type=rec["rec_type"])


def history(con: sqlite3.Connection, company_id: str) -> dict:
    rows = con.execute(
        "SELECT r.rec_id, r.created_at, r.rec_type, r.title, r.expected_profit, r.confidence, r.status, r.policy_id, "
        "f.actual_profit, f.error, f.error_pct, f.confidence_before, f.confidence_after, f.recorded_at "
        "FROM recommendations r LEFT JOIN feedback f USING(rec_id) WHERE r.company_id=? ORDER BY r.created_at DESC, r.rowid DESC",
        (company_id,)).fetchall()
    items = [dict(r) for r in rows]
    done = [i for i in items if i["actual_profit"] is not None]
    calib = [dict(r) for r in con.execute("SELECT rec_type, accuracy, n FROM calibration WHERE company_id=?", (company_id,))]
    summary = dict(
        decisions=len(items), approved=sum(1 for i in items if i["status"] == "approved"),
        predicted_total=sum(i["expected_profit"] for i in done), actual_total=sum(i["actual_profit"] for i in done),
        mean_abs_error_pct=float(np.mean([abs(i["error_pct"]) for i in done])) if done else 0.0,
        avg_confidence=float(np.mean([i["confidence_after"] for i in done])) if done else 0.0,
    )
    return dict(items=items, summary=summary, calibration=calib)
