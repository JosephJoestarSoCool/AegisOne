"""Orchestration: data -> diagnosis -> policy -> optimizer -> recommendations / what-if / compare."""
from __future__ import annotations

import sqlite3
from collections import defaultdict

import numpy as np
import pandas as pd

from . import optimizer as opt
from .config import AS_OF, HISTORY_DAYS
from .diagnosis import detect
from .metrics import CompanyData, build_state, daily_series, load_company
from .policy import WEIGHT_KEYS, Policy

MIN_REC_AMOUNT = 2000.0
_CACHE: dict[str, CompanyData] = {}

DIM_LABEL = {"profitability": "Profitability", "growth": "Growth", "revenue": "Revenue", "inventory": "Inventory",
             "cac": "CAC / efficiency", "risk": "Risk"}


def clear_cache() -> None:
    _CACHE.clear()


def get_data(con: sqlite3.Connection, company_id: str) -> CompanyData:
    if company_id not in _CACHE:
        _CACHE[company_id] = load_company(con, company_id)
    return _CACHE[company_id]


def inr(x: float) -> str:
    return f"₹{x:,.0f}"


def _calibration(con: sqlite3.Connection, company_id: str) -> dict:
    rows = con.execute("SELECT rec_type, accuracy, n FROM calibration WHERE company_id=?", (company_id,)).fetchall()
    return {r["rec_type"]: (float(r["accuracy"]), int(r["n"])) for r in rows}


# --------------------------------------------------------------------------- #
# Plan
# --------------------------------------------------------------------------- #

def avg_price(con, company_id: str) -> float:
    r = con.execute("SELECT AVG(p.list_price) AS a FROM pricing p JOIN products s USING(sku_id) "
                    "WHERE s.company_id=? AND p.date=?", (company_id, AS_OF.isoformat())).fetchone()
    return float(r["a"] or 1.0)


def resolve_policy(con, d: CompanyData, policy_id: str | None, scenario: dict | None) -> Policy:
    """Policy to apply. Borrowing another company's policy rescales its absolute-rupee
    guardrails (max CAC, LTV) by relative price level so they stay meaningful."""
    from dataclasses import replace
    from .metrics import all_policies
    pol = d.policy
    if policy_id and policy_id != d.company_id:
        pol = all_policies(con)[policy_id]
        k = avg_price(con, d.company_id) / avg_price(con, policy_id)
        pol = replace(pol, max_cac=pol.max_cac * k, ltv_per_customer=pol.ltv_per_customer * k)
    scenario = scenario or {}
    return pol.with_overrides(scenario.get("weights"), scenario.get("constraints"))


def build_plan(con: sqlite3.Connection, company_id: str, policy_id: str | None = None,
               scenario: dict | None = None) -> dict:
    d = get_data(con, company_id)
    scenario = scenario or {}
    pol = resolve_policy(con, d, policy_id, scenario)
    overrides = {k: v for k, v in (scenario.get("sku_overrides") or {}).items() if v}
    states = build_state(d, overrides, pol)
    anomalies = detect(d, states, pol)
    cprep = opt.prepare(states, pol, anomalies)
    plan = opt.optimize(cprep, pol, float(scenario.get("total_budget_delta") or 0.0))
    marg = opt.marginal_table(cprep, pol)
    cs = {c["campaign_id"]: c for c in cprep}
    calib = _calibration(con, company_id)

    # ---- allocation ----
    mus = [m["mu"] for m in marg.values() if m["eligible"]]
    top_mu = max(mus) if mus else 1.0
    allocation, new_profit_total, old_profit_total = [], 0.0, 0.0
    for c in cprep:
        cid = c["campaign_id"]
        b_new = plan.budgets[cid]
        p_old = opt.terms(c, c["b0"], pol)["profit"]
        p_new = opt.terms(c, b_new, pol)["profit"]
        old_profit_total += p_old
        new_profit_total += p_new
        m = marg[cid]
        action = "pause" if cid in plan.paused else ("increase" if b_new > c["b0"] + 1 else ("decrease" if b_new < c["b0"] - 1 else "hold"))
        opp = 100.0 * max(0.0, m["mu"]) / max(top_mu, 1e-9)
        if not m["eligible"]:
            opp = min(opp, 15.0)
        allocation.append(dict(
            campaign_id=cid, name=c["name"], sku_id=c["sku_id"], sku_name=c["sku_name"], platform=c["platform"],
            platform_id=c["platform_id"], audience=c["audience"], current=c["b0"], recommended=b_new,
            delta=b_new - c["b0"], action=action, roas=c["roas"], marginal_roas=m["marginal_roas"],
            marginal_profit_per_rupee=m["marginal_profit_per_rupee"], opportunity_score=round(opp, 0),
            eligible=m["eligible"], profit_now=p_old, profit_new=p_new,
            anomaly=c["anomaly"]["kind"] if c["anomaly"] else None,
        ))

    recs = _build_recs(con, d, pol, cs, plan, marg, anomalies, calib, overrides)
    creative_gain = sum(r["expected_profit"] for r in recs if r["rec_type"] == "replace_creative")
    return dict(
        company_id=company_id, company_name=d.name, policy=pol.to_dict(), step=plan.step,
        allocation=allocation, recommendations=recs, anomalies=anomalies,
        totals=dict(
            budget_before=sum(c["b0"] for c in cprep), budget_after=sum(plan.budgets.values()),
            profit_before=old_profit_total, profit_after=new_profit_total,
            incremental_profit=new_profit_total - old_profit_total + creative_gain,
            incremental_profit_30d=(new_profit_total - old_profit_total + creative_gain) * 30,
            moved=sum(abs(a["delta"]) for a in allocation) / 2,
        ),
        campaigns={c["campaign_id"]: _public_campaign(c, marg[c["campaign_id"]]) for c in cprep},
        **_portfolio(cprep, pol, marg, allocation),
    )


def _gate_reason(c: dict, pol: Policy, units_by_sku: dict) -> str | None:
    """Why a campaign cannot take the next rupee (None = eligible)."""
    if not c["margin_ok"]:
        return f"margin {c['margin']*100:.1f}% below {pol.min_margin*100:.0f}% floor"
    t = opt.terms(c, c["b0"] + 1000.0, pol)
    if t["orders"] <= 0:
        return "no demand signal"
    if t["revenue"] / (c["b0"] + 1000.0) < pol.min_roas:
        return f"ROAS below {pol.min_roas:.1f}× floor"
    if (c["b0"] + 1000.0) / t["orders"] > pol.max_cac:
        return f"CAC above {inr(pol.max_cac)} cap"
    if units_by_sku[c["sku_id"]] >= c["cap_units"]:
        return f"stock cap reached ({c['inventory_days']:.0f} days of cover vs {c['lead_time']:.0f}-day lead time)"
    return None


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _health(c: dict, mp: float, cvr_ref: float, pol: Policy) -> dict:
    """Transparent 0-100 campaign health: weighted blend of six 0-100 components."""
    parts = [
        ("Contribution profit", 0.30, _clamp((mp + 0.5) / 1.5)),
        ("ROAS vs floor", 0.15, _clamp(c["roas"] / (2 * pol.min_roas))),
        ("Conversion rate", 0.15, _clamp(c["cvr"] / (2 * cvr_ref)) if cvr_ref else 0.5),
        ("Inventory fit", 0.15, 1 - c["stockout_risk"]),
        ("Creative freshness", 0.10, _clamp(1 - c["creative_age"] / 90)),
        ("Stability", 0.15, _clamp(1 - c["roas_cv"])),
    ]
    score = round(100 * sum(w * v for _, w, v in parts))
    return dict(score=score, status="Healthy" if score >= 70 else "Watch" if score >= 45 else "At risk",
                parts=[dict(label=n, weight=w, score=round(100 * v)) for n, w, v in parts])


def _candidate(c: dict, m: dict, reason: str | None, a: dict, pol: Policy, cvr_ref: float) -> dict:
    step = 1000.0
    d_orders = opt.terms(c, c["b0"] + step, pol)["orders"] - opt.terms(c, c["b0"], pol)["orders"]
    return dict(
        campaign_id=c["campaign_id"], campaign=c["name"], sku_id=c["sku_id"], sku_name=c["sku_name"],
        platform=c["platform"], audience=c["audience"], eligible=reason is None, gate_reason=reason,
        roas=c["roas"], marginal_roas=m["marginal_roas"], profit_per_rupee=m["marginal_profit_per_rupee"],
        policy_value_per_rupee=m["mu"], marginal_cac=step / d_orders if d_orders > 0 else None,
        margin=c["margin"], cvr=c["cvr"], ctr=c["ctr"], cac=c["cac"], inventory_days=c["inventory_days"],
        stockout_risk=c["stockout_risk"], lead_time=c["lead_time"], creative_age=c["creative_age"],
        anomaly=c["anomaly"]["kind"] if c["anomaly"] else None,
        current=c["b0"], recommended=a["recommended"], delta=a["delta"], action=a["action"],
        recommended_profit=a["profit_new"] - a["profit_now"], step_profit=m["marginal_profit_per_rupee"] * step,
        confidence=round(_clamp(0.5 * c["fit_quality"] + 0.3 * (1 - c["stockout_risk"]) + 0.2 * (1 - _clamp(c["roas_cv"]))), 2),
        health=_health(c, m["marginal_profit_per_rupee"], cvr_ref, pol),
    )


def _why_won(w: dict, ru: dict | None, pol: Policy) -> list[str]:
    out = []
    if ru and w["profit_per_rupee"] > ru["profit_per_rupee"]:
        out.append(f"Highest incremental profit per ₹1: ₹{w['profit_per_rupee']:.2f} vs ₹{ru['profit_per_rupee']:.2f} "
                   f"for {ru['sku_name']} × {ru['platform']}.")
    elif not ru:
        out.append(f"Only eligible opportunity: ₹{w['profit_per_rupee']:.2f} incremental profit per ₹1.")
    else:
        out.append(f"Highest policy-weighted value per ₹1: {w['policy_value_per_rupee']:.2f} vs {ru['policy_value_per_rupee']:.2f} "
                   f"(growth, inventory and risk weights outweigh raw profit).")
    if ru and w["margin"] > ru["margin"]:
        out.append(f"Better contribution margin: {w['margin']*100:.0f}% vs {ru['margin']*100:.0f}%.")
    if ru and w["marginal_cac"] and ru["marginal_cac"] and w["marginal_cac"] < ru["marginal_cac"]:
        out.append(f"Lower marginal CAC: {inr(w['marginal_cac'])} vs {inr(ru['marginal_cac'])}.")
    if ru and w["cvr"] > ru["cvr"]:
        out.append(f"Stronger conversion: {w['cvr']*100:.1f}% CVR vs {ru['cvr']*100:.1f}%.")
    if w["stockout_risk"] < 0.2:
        out.append(f"Stock is healthy: {w['inventory_days']:.0f} days of cover, {w['stockout_risk']*100:.0f}% stockout risk.")
    out.append(f"Clears every guardrail: margin ≥ {pol.min_margin*100:.0f}%, ROAS ≥ {pol.min_roas:.1f}×, CAC ≤ {inr(pol.max_cac)}.")
    return out[:5]


def _why_lost(x: dict, w: dict) -> list[str]:
    out = []
    if x["gate_reason"]:
        out.append(f"Blocked by policy: {x['gate_reason']}.")
    elif x["profit_per_rupee"] > w["profit_per_rupee"]:
        out.append(f"Earns more profit per ₹1 (₹{x['profit_per_rupee']:.2f}) but lower policy-weighted value "
                   f"({x['policy_value_per_rupee']:.2f} vs {w['policy_value_per_rupee']:.2f}).")
    if x["stockout_risk"] >= max(0.25, w["stockout_risk"] + 0.1):
        out.append(f"Inventory constrained: {x['inventory_days']:.0f} days of cover vs {x['lead_time']:.0f}-day lead time.")
    if x["anomaly"]:
        out.append(f"Active issue: {x['anomaly'].replace('_', ' ')}.")
    if x["marginal_cac"] and w["marginal_cac"] and x["marginal_cac"] > w["marginal_cac"] * 1.05:
        out.append(f"Higher marginal CAC: {inr(x['marginal_cac'])} vs {inr(w['marginal_cac'])}.")
    if x["margin"] < w["margin"] - 0.02:
        out.append(f"Thinner margin: {x['margin']*100:.0f}% vs {w['margin']*100:.0f}%.")
    if x["cvr"] < w["cvr"] * 0.95:
        out.append(f"Weaker conversion: {x['cvr']*100:.1f}% vs {w['cvr']*100:.1f}% CVR.")
    if x["profit_per_rupee"] < w["profit_per_rupee"]:
        out.append(f"Lower incremental profit per ₹1: ₹{x['profit_per_rupee']:.2f} vs ₹{w['profit_per_rupee']:.2f}.")
    return out[:3] or ["Lower policy-weighted value per ₹1."]


def _portfolio(cprep: list[dict], pol: Policy, marg: dict, allocation: list[dict]) -> dict:
    """Company-scoped ranking: SKU x campaign x platform -> marginal economics -> next rupee, with why / why-not / ROAS trap."""
    units = defaultdict(float)
    for c in cprep:
        units[c["sku_id"]] += opt.terms(c, c["b0"], pol)["orders"]
    alloc = {a["campaign_id"]: a for a in allocation}
    cvrs = sorted(c["cvr"] for c in cprep if c["cvr"] > 0)
    cvr_ref = cvrs[len(cvrs) // 2] if cvrs else 0.0
    cands = []
    for c in cprep:
        m = marg[c["campaign_id"]]
        reason = None if m["eligible"] else (_gate_reason(c, pol, units) or "gated by policy")
        cands.append(_candidate(c, m, reason, alloc[c["campaign_id"]], pol, cvr_ref))
    cands.sort(key=lambda x: (not x["eligible"], -x["policy_value_per_rupee"]))
    for i, x in enumerate(cands, 1):
        x["rank"] = i

    by_sku: dict[str, list[dict]] = defaultdict(list)
    for x in cands:
        by_sku[x["sku_id"]].append(x)
    spend_rev = defaultdict(lambda: [0.0, 0.0])
    for c in cprep:
        spend_rev[c["sku_id"]][0] += c["spend"]
        spend_rev[c["sku_id"]][1] += c["revenue"]
    rows = []
    for sku_id, xs in by_sku.items():
        b = xs[0]  # already sorted best-first
        sp, rv = spend_rev[sku_id]
        rows.append(dict(
            sku_id=sku_id, sku_name=b["sku_name"], campaigns=len(xs), budget=sum(x["current"] for x in xs),
            roas=rv / sp if sp else 0.0, margin=b["margin"], inventory_days=b["inventory_days"],
            stockout_risk=b["stockout_risk"], best_campaign_id=b["campaign_id"], best_campaign=b["campaign"],
            platform=b["platform"], audience=b["audience"], marginal_roas=b["marginal_roas"],
            profit_per_rupee=b["profit_per_rupee"], policy_value_per_rupee=b["policy_value_per_rupee"],
            eligible=b["eligible"], gate_reason=b["gate_reason"], recommended_delta=b["delta"],
            recommended_profit=b["recommended_profit"],
        ))
    rows.sort(key=lambda r: (not r["eligible"], -r["policy_value_per_rupee"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    win = next((x for x in cands if x["eligible"]), None)
    next_rupee = None
    trap = dict(active=False, message="No eligible opportunity.", roas_leader=None, winner=None)
    if win:
        others = [x for x in cands if x is not win]
        runner = next((x for x in others if x["eligible"]), None)
        for x in others:
            x["why_lost"] = _why_lost(x, win)
        pl = max((x for x in cands if x["eligible"]), key=lambda x: x["profit_per_rupee"])
        top_dims = ", ".join(DIM_LABEL[k].lower() for k, _ in sorted(pol.weights.items(), key=lambda kv: -kv[1])[:2])
        policy_note = None if pl is win else (
            f"{pl['sku_name']} × {pl['platform']} earns more raw profit per ₹1 (₹{pl['profit_per_rupee']:.2f}), but "
            f"{pol.name} policy weights {top_dims} most, so {win['sku_name']} × {win['platform']} ranks first on policy-weighted value.")
        next_rupee = dict(
            next(r for r in rows if r["sku_id"] == win["sku_id"]), **win,
            policy_note=policy_note, why_won=_why_won(win, runner, pol),
            alternatives=others[:3],
        )
        leader = max(cands, key=lambda x: x["roas"])
        if leader["campaign_id"] != win["campaign_id"]:
            msg = (f"{leader['sku_name']} × {leader['platform']} has the highest ROAS ({leader['roas']:.1f}×) but returns "
                   f"₹{leader['profit_per_rupee']:.2f} marginal profit per ₹1. {win['sku_name']} × {win['platform']} "
                   f"({win['roas']:.1f}× ROAS) returns ₹{win['profit_per_rupee']:.2f}, so it wins the next rupee.")
            if not leader["eligible"]:
                msg += f" The ROAS leader is also blocked: {leader['gate_reason']}."
            trap = dict(active=True, message=msg, roas_leader=leader, winner=win)
        else:
            trap = dict(active=False, winner=win, roas_leader=leader,
                        message="The ROAS leader is also the marginal-profit leader here.")
    return dict(portfolio=rows, candidates=cands, next_rupee=next_rupee, roas_trap=trap)


def _public_campaign(c: dict, m: dict) -> dict:
    keys = ["campaign_id", "name", "sku_id", "sku_name", "platform", "platform_id", "audience", "audience_type",
            "creative", "creative_age", "b0", "spend", "orders", "revenue", "roas", "cac", "ctr", "cpc", "cvr", "profit",
            "margin", "inventory_days", "stockout_risk", "elasticity", "status", "price", "unit_cost", "on_hand",
            "lead_time", "target_days", "shelf_life"]
    out = {k: c[k] for k in keys}
    out["marginal_roas"] = m["marginal_roas"]
    out["marginal_profit_per_rupee"] = m["marginal_profit_per_rupee"]
    return out


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #

def _relation(a: dict, b: dict) -> str:
    if a["sku_id"] == b["sku_id"] and a["platform_id"] == b["platform_id"]:
        return "change_audience"
    if a["sku_id"] == b["sku_id"]:
        return "shift_platform"
    return "promote_sku"


_REL_LABEL = {"change_audience": "Change audience allocation", "shift_platform": "Move budget between platforms",
              "promote_sku": "Promote another SKU"}


def _conf(base: float, rec_type: str, calib: dict) -> float:
    acc, n = calib.get(rec_type, (0.8, 0))
    return float(np.clip(base * (0.75 + 0.25 * acc), 0.3, 0.97))


def _build_recs(con, d, pol, cs, plan, marg, anomalies, calib, overrides) -> list[dict]:
    recs: list[dict] = []
    name = {cid: c["name"] for cid, c in cs.items()}

    def drivers(cid_list: list[tuple[str, float, float]]) -> list[dict]:
        tot = defaultdict(float)
        for cid, b0, b1 in cid_list:
            for k, v in opt.utility_parts(cs[cid], b0, b1, pol).items():
                tot[k] += v
        total_abs = sum(abs(v) for v in tot.values()) or 1.0
        rows = [dict(dim=k, label=DIM_LABEL[k], value=round(v, 0), share=round(abs(v) / total_abs, 3),
                     weight=round(pol.weights[k], 2)) for k, v in tot.items()]
        return sorted(rows, key=lambda r: -abs(r["value"]))

    def guardrails(cid: str) -> list[dict]:
        c = cs[cid]
        b = plan.budgets[cid]
        t = opt.terms(c, b, pol)
        roas = t["revenue"] / b if b else 0
        cac = b / t["orders"] if t["orders"] else 0
        units = sum(opt.terms(x, plan.budgets[x["campaign_id"]], pol)["orders"] for x in cs.values() if x["sku_id"] == c["sku_id"])
        return [
            dict(label=f"ROAS ≥ {pol.min_roas:.1f}", value=f"{roas:.2f}", ok=bool(roas >= pol.min_roas)),
            dict(label=f"CAC ≤ {inr(pol.max_cac)}", value=inr(cac), ok=bool(cac <= pol.max_cac)),
            dict(label=f"Margin ≥ {pol.min_margin*100:.0f}%", value=f"{c['margin']*100:.0f}%", ok=bool(c["margin"] >= pol.min_margin)),
            dict(label="Within safe stock", value=f"{units:.0f}/{c['cap_units']:.0f} units/day", ok=bool(units <= c["cap_units"] + 1e-6)),
        ]

    for f in sorted(plan.flows, key=lambda f: -f["amount"]):
        src, dst, amt = f["src"], f["dst"], f["amount"]
        if amt < MIN_REC_AMOUNT or src in plan.paused:
            continue
        if dst in ("RELEASED", "CUT"):
            if src not in cs:
                continue
            c = cs[src]
            title = f"Decrease {c['name']} by {inr(amt)}/day"
            why = [f"Marginal ROAS is {marg[src]['marginal_roas']:.2f}: the next rupee returns {inr(marg[src]['marginal_roas'])} of revenue "
                   f"but only {c['margin']*100:.0f}% of that is margin.",
                   "No campaign has a better guardrail-safe use for the money, so it is held back."]
            recs.append(_rec(pol, d, "decrease_budget", title, src, None, amt, f["profit"], 0.7, why, cs, calib,
                             drivers([(src, c["b0"], c["b0"] - amt)]), guardrails(src), name))
            continue
        if dst not in cs:
            continue
        cd = cs[dst]
        if src == "RESERVE":
            title = f"Increase {cd['name']} by {inr(amt)}/day"
            why = [f"{cd['name']} has marginal ROAS {marg[dst]['marginal_roas']:.2f} at {cd['margin']*100:.0f}% margin — "
                   f"each extra rupee earns about {inr(marg[dst]['marginal_profit_per_rupee'])} of profit.",
                   "Funded from the extra budget made available in this scenario."]
            recs.append(_rec(pol, d, "increase_budget", title, None, dst, amt, f["profit"], 0.72, why, cs, calib,
                             drivers([(dst, cd["b0"], cd["b0"] + amt)]), guardrails(dst), name))
            continue
        if src not in cs:
            continue
        cs_ = cs[src]
        rel = _relation(cs_, cd)
        rtype = "pause_campaign" if src in plan.paused else "move_budget"
        # confidence: model fit quality, source anomaly certainty, destination stock safety
        q_src = cs_["anomaly"]["confidence"] if cs_["anomaly"] else cs_["fit_quality"]
        base = 0.42 + 0.22 * cd["fit_quality"] + 0.18 * q_src + 0.15 * (1 - cd["stockout_risk"])
        title = f"Move {inr(amt)}/day from {cs_['name']} to {cd['name']}"
        why = _why_move(pol, cs_, cd, amt, marg, rel, f["util"] / max(amt, 1))
        rec = _rec(pol, d, "move_budget", title, src, dst, amt, f["profit"], base, why, cs, calib,
                   drivers([(src, cs_["b0"], cs_["b0"] - amt), (dst, cd["b0"], cd["b0"] + amt)]), guardrails(dst), name)
        rec["relation"] = rel
        rec["relation_label"] = _REL_LABEL[rel]
        rec["source_anomaly"] = cs_["anomaly"]["kind"] if cs_["anomaly"] else None
        recs.append(rec)

    for cid in plan.paused:
        c = cs[cid]
        outs = [f for f in plan.flows if f["src"] == cid]
        gain = sum(f["profit"] for f in outs)
        dests = sorted([f for f in outs if f["dst"] in cs], key=lambda f: -f["amount"])
        where = ", ".join(f"{inr(f['amount'])} → {name[f['dst']]}" for f in dests[:3]) or "held back as cash"
        weak = c["roas"] < 0.65 * pol.min_roas
        why = [(f"ROAS {c['roas']:.2f} is far below the {pol.min_roas:.1f} floor in this policy and no diagnosed fix applies."
                if weak else f"Unit margin {c['margin']*100:.0f}% is well under the {pol.min_margin*100:.0f}% policy floor."),
               f"Pausing frees {inr(c['b0'])}/day, redeployed: {where}."]
        title = f"Pause {c['name']}" + (f" and redeploy {inr(sum(f['amount'] for f in dests))}/day" if dests else "")
        recs.append(_rec(pol, d, "pause_campaign", title, cid, None, c["b0"], gain, 0.8, why, cs, calib,
                         drivers([(cid, c["b0"], 0.0)]), [], name))

    # creative replacement for fatigue anomalies
    for a in anomalies:
        if a["kind"] == "creative_fatigue" and a["confidence"] >= 0.6 and a.get("campaign_id") in cs:
            c = cs[a["campaign_id"]]
            b_after = plan.budgets[c["campaign_id"]]
            lost = max(0.0, a["raw"]["roas_base"] - a["raw"]["roas_now"])
            gain = lost * b_after * c["margin"] * 0.5
            why = [f"CTR fell {abs(a['raw']['ctr_change'])*100:.0f}% while conversion held — the audience is tired of "
                   f"“{c['creative']}” ({c['creative_age']} days old).",
                   f"A fresh creative should recover roughly half of the lost ROAS ({a['raw']['roas_now']:.2f} → "
                   f"{a['raw']['roas_now'] + 0.5*lost:.2f})."]
            recs.append(_rec(pol, d, "replace_creative", f"Replace creative on {c['name']}", c["campaign_id"], None, 0.0,
                             gain, a["confidence"], why, cs, calib, [], [], name))

    recs.sort(key=lambda r: -r["expected_profit"])
    for i, r in enumerate(recs, 1):
        r["rank"] = i
    _attach_status(con, recs)
    return recs


def _attach_status(con, recs: list[dict]) -> None:
    ids = [r["rec_id"] for r in recs]
    if not ids:
        return
    q = ",".join("?" * len(ids))
    rows = con.execute(f"SELECT rec_id, status FROM recommendations WHERE rec_id IN ({q})", ids).fetchall()
    st = {r["rec_id"]: r["status"] for r in rows}
    for r in recs:
        r["status"] = st.get(r["rec_id"], "pending")


def _rec(pol, d, rtype, title, src, dst, amount, profit, base_conf, why, cs, calib, drivers, guards, names) -> dict:
    conf = _conf(base_conf, rtype, calib)
    rid = opt.stable_id(d.company_id, pol.policy_id, rtype, src, dst, round(amount, -2))
    return dict(
        rec_id=rid, rec_type=rtype, title=title, source_campaign_id=src, target_campaign_id=dst,
        source_name=names.get(src), target_name=names.get(dst), amount=float(amount),
        expected_profit=float(round(profit, 0)), expected_profit_30d=float(round(profit * 30, 0)),
        confidence=round(conf, 2), why=why, policy_drivers=drivers, guardrails=guards,
        policy_id=pol.policy_id, policy_name=pol.name, company_id=d.company_id, status="pending",
    )


def _why_move(pol, a, b, amt, marg, rel, util_gain) -> list[str]:
    pts = []
    if a["anomaly"]:
        an = a["anomaly"]
        pts.append(f"{a['name']}: {an['title'].split(' — ')[0]} — {an['what_happened']} "
                   f"Diagnosed as {an['probable_cause'].lower()} ({an['confidence']*100:.0f}% confidence).")
    else:
        pts.append(f"{a['name']} returns {marg[a['campaign_id']]['marginal_roas']:.2f} of revenue on the next rupee "
                   f"(blended ROAS {a['roas']:.2f}) — the weakest use of budget in the portfolio under this policy.")
    pts.append(f"{b['name']}: marginal ROAS {marg[b['campaign_id']]['marginal_roas']:.2f} vs {marg[a['campaign_id']]['marginal_roas']:.2f} at the source, "
               f"{b['margin']*100:.0f}% unit margin, {b['inventory_days']:.0f} days of stock cover"
               + (f" ({b['target_days']:.0f}-day target)." if b["inventory_days"] < b["target_days"] else "."))
    pts.append(f"Each rupee moved gains ≈{util_gain:.1f}× policy-weighted value. Guardrails hold at the destination: "
               f"ROAS ≥ {pol.min_roas:.1f}, CAC ≤ {inr(pol.max_cac)}, margin ≥ {pol.min_margin*100:.0f}%, stock cap respected.")
    return pts


# --------------------------------------------------------------------------- #
# Overview / series
# --------------------------------------------------------------------------- #

def overview(con, company_id: str, policy_id: str | None = None) -> dict:
    d = get_data(con, company_id)
    plan = build_plan(con, company_id, policy_id)
    s = daily_series(d)
    last7, prev7 = s[s.day >= HISTORY_DAYS - 7], s[(s.day < HISTORY_DAYS - 7) & (s.day >= HISTORY_DAYS - 14)]

    def agg(x: pd.DataFrame) -> dict:
        sp, rev, pr, od = x.spend.sum(), x.revenue.sum(), x.profit.sum(), x.orders.sum()
        return dict(spend=sp, revenue=rev, profit=pr, roas=rev / sp if sp else 0, cac=sp / od if od else 0)

    cur, prv = agg(last7), agg(prev7)
    delta = {k: (cur[k] - prv[k]) / prv[k] if prv[k] else 0.0 for k in cur}
    trend = s.tail(30)[["date", "spend", "revenue", "profit", "roas"]].round(2).to_dict("records")
    top_anoms = plan["anomalies"][:6]
    opps = sorted(plan["allocation"], key=lambda a: -a["opportunity_score"])[:5]
    return dict(
        company=dict(company_id=company_id, name=d.name, vertical=d.vertical), as_of=AS_OF.isoformat(),
        kpis=cur, kpi_delta=delta, trend=trend, anomaly_count=len(plan["anomalies"]),
        anomalies=top_anoms, opportunities=opps, top_recommendations=plan["recommendations"][:3],
        incremental_profit=plan["totals"]["incremental_profit"],
        incremental_profit_30d=plan["totals"]["incremental_profit_30d"],
        reconciliation=reconciliation(d), portfolio=plan["portfolio"], candidates=plan["candidates"], next_rupee=plan["next_rupee"],
        roas_trap=plan["roas_trap"],
        policy=plan["policy"],
    )


def reconciliation(d: CompanyData) -> dict:
    last = d.ad[d.ad.day >= HISTORY_DAYS - 7]
    rf = d.recon.set_index("sku_id")["recon_factor"]
    rep_orders = float(last.platform_orders.sum())
    rec_orders = float((last.platform_orders * last.sku_id.map(rf)).sum())
    rep_rev, spend = float(last.platform_revenue.sum()), float(last.spend.sum())
    return dict(reported_orders=rep_orders, reconciled_orders=rec_orders,
                overcount_pct=(rep_orders / rec_orders - 1) if rec_orders else 0.0,
                reported_roas=rep_rev / spend if spend else 0.0,
                reconciled_roas=(rep_rev * rec_orders / rep_orders) / spend if spend and rep_orders else 0.0,
                platforms=int(d.ad.platform_id.nunique()), campaigns=int(d.campaigns.shape[0]),
                skus=int(d.products.shape[0]), rows=int(len(d.ad)))


def campaign_series(con, company_id: str, campaign_id: str) -> dict:
    d = get_data(con, company_id)
    s = daily_series(d, campaign_id).tail(45)
    return dict(campaign_id=campaign_id, series=s[["date", "spend", "roas", "ctr", "cpc", "cvr", "frequency", "orders"]]
                .round(4).to_dict("records"))


# --------------------------------------------------------------------------- #
# What-if + cross-policy comparison
# --------------------------------------------------------------------------- #

def _summ(rec: dict | None) -> dict | None:
    if not rec:
        return None
    return dict(rec_id=rec["rec_id"], title=rec["title"], rec_type=rec["rec_type"], amount=rec["amount"],
                source=rec["source_name"], target=rec["target_name"], source_id=rec["source_campaign_id"],
                target_id=rec["target_campaign_id"], expected_profit=rec["expected_profit"], confidence=rec["confidence"])


def whatif(con, company_id: str, scenario: dict, policy_id: str | None = None, base: dict | None = None) -> dict:
    base = base or build_plan(con, company_id, policy_id)
    scen = build_plan(con, company_id, policy_id, scenario)
    key = lambda r: (r["rec_type"], r["source_campaign_id"], r["target_campaign_id"])
    bkeys = {key(r) for r in base["recommendations"][:3]}
    skeys = {key(r) for r in scen["recommendations"][:3]}
    btop = next((r for r in base["recommendations"] if r["rec_type"] in ("move_budget", "increase_budget")), None)
    stop = next((r for r in scen["recommendations"] if r["rec_type"] in ("move_budget", "increase_budget")), None)
    changed = bool(btop and stop and (btop["target_campaign_id"] != stop["target_campaign_id"]
                                      or btop["source_campaign_id"] != stop["source_campaign_id"]
                                      or abs(btop["amount"] - stop["amount"]) >= 1)) or (bool(btop) != bool(stop))
    ba = {a["campaign_id"]: a for a in base["allocation"]}
    diff = [dict(campaign_id=a["campaign_id"], name=a["name"], platform=a["platform"], current=a["current"],
                 baseline=ba[a["campaign_id"]]["recommended"], scenario=a["recommended"],
                 shift=a["recommended"] - ba[a["campaign_id"]]["recommended"]) for a in scen["allocation"]]
    bw, sw = base["next_rupee"], scen["next_rupee"]
    winner_changed = (bw["campaign_id"] if bw else None) != (sw["campaign_id"] if sw else None)
    reason = None
    if winner_changed and bw:
        lost = next((c for c in scen["candidates"] if c["campaign_id"] == bw["campaign_id"]), None)
        reason = (lost.get("why_lost") or [None])[0] if lost else None
    return dict(
        next_rupee=dict(before=bw, after=sw, changed=winner_changed, reason=reason),
        baseline=base, scenario=scen, changed=changed, top_before=_summ(btop), top_after=_summ(stop),
        profit_delta=scen["totals"]["incremental_profit"] - base["totals"]["incremental_profit"],
        allocation_diff=diff, same_top3=bkeys == skeys,
        narrative=_narrate_whatif(base, scen, btop, stop, changed, scenario),
    )


def _narrate_whatif(base, scen, btop, stop, changed, scenario) -> str:
    if not btop and not stop:
        return "No budget move clears the guardrails in either scenario."
    if not changed:
        return (f"Recommendation unchanged — top action remains: {stop['title']}. "
                f"Expected profit moves to {inr(scen['totals']['incremental_profit'])}/day.")
    if btop and not stop:
        return f"The previous top move ({btop['title']}) no longer clears the guardrails — the engine holds budget."
    if not btop:
        return f"A new opportunity appears: {stop['title']}."
    if btop["target_campaign_id"] != stop["target_campaign_id"]:
        why = ""
        tgt = scen["campaigns"].get(btop["target_campaign_id"])
        if tgt:
            if tgt["stockout_risk"] >= 0.5:
                why = (f" {tgt['sku_name']} now has only {tgt['inventory_days']:.1f} days of cover against the "
                       f"{tgt['lead_time']:.0f}-day restock lead time, so scaling it would stock out.")
            elif tgt["margin"] < scen["policy"]["min_margin"]:
                why = f" {tgt['sku_name']} margin ({tgt['margin']*100:.0f}%) is now under the policy floor."
        return (f"Recommendation CHANGED. Before: {btop['title']}. After: {stop['title']}.{why}")
    return f"Same destination, new size: {btop['title']} → {stop['title']}."


def compare_policies(con, company_id: str) -> dict:
    from .metrics import all_policies
    pols = all_policies(con)
    out, matrix = [], {}
    base_alloc = None
    for pid, pol in pols.items():
        plan = build_plan(con, company_id, pid)
        top = [_summ(r) for r in plan["recommendations"] if r["rec_type"] in ("move_budget", "increase_budget", "pause_campaign")][:3]
        out.append(dict(policy_id=pid, policy_name=pol.name, weights=pol.weights, min_margin=pol.min_margin,
                        max_cac=pol.max_cac, min_roas=pol.min_roas, inventory_target_days=pol.inventory_target_days,
                        top=top, incremental_profit=plan["totals"]["incremental_profit"],
                        moved=plan["totals"]["moved"]))
        for a in plan["allocation"]:
            matrix.setdefault(a["campaign_id"], dict(campaign_id=a["campaign_id"], name=a["name"], platform=a["platform"],
                                                      current=a["current"], by_policy={}))["by_policy"][pid] = a["delta"]
        base_alloc = base_alloc or plan["allocation"]
    return dict(company_id=company_id, policies=out, matrix=list(matrix.values()))
