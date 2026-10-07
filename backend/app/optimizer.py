"""Decision optimizer: policy-weighted incremental-profit budget reallocation.

Model per campaign (b = daily budget):
    orders(b)  = orders0 * (b / b0) ** e          # fitted spend elasticity e < 1  (diminishing returns)
    profit(b)  = orders * unit_margin - b          # incremental contribution after ad spend
    U(b)       = 6 * [ w_profit  * profit
                     + w_revenue * 0.05 * revenue
                     + w_growth  * new_customers * LTV * 0.1
                     + w_inventory * inventory_pressure * orders * unit_cost * 0.15
                     - w_cac     * (CAC-over-cap + ROAS shortfall penalties)
                     - w_risk    * b * volatility ]
(equal weights => multiplier 1; the weights are the company's Business Policy.)

Because every U_i is concave in b, a greedy "move one step from the lowest
marginal utility to the highest" loop is optimal. Hard guardrails (min margin,
min ROAS, max CAC, stock cap) gate every increase; per-source and total
turnover caps keep changes sane.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .policy import Policy

REV_VALUE = 0.05
LTV_DISCOUNT = 0.10
INV_VALUE = 0.15
STOCK_PEN = 1.0
EPS = 0.06               # min marginal-utility gain per rupee to justify a move
SRC_CAP = 0.30           # max share of a campaign's budget that can be taken in one decision
FLOOR = 0.40             # campaigns never drop below 40% of budget (except pause)
CEIL = 2.0
TURNOVER_CAP = 0.15      # max share of total budget moved in one decision


def _w(policy: Policy) -> dict:
    return {k: 6.0 * v for k, v in policy.weights.items()}


def terms(c: dict, b: float, pol: Policy) -> dict:
    """Natural-unit components (INR/day) at budget b."""
    if b <= 0:
        return dict(orders=0.0, revenue=0.0, profit=0.0, revenue_v=0.0, growth=0.0, inventory=0.0, cac=0.0, risk=0.0)
    orders = c["orders0"] * (b / c["b0"]) ** c["elasticity"]
    revenue = orders * c["price"]
    profit = revenue * c["margin"] - b
    cac_over = max(0.0, b - pol.max_cac * orders)
    roas_short = max(0.0, pol.min_roas * b - revenue) * 0.25
    return dict(
        orders=orders, revenue=revenue, profit=profit, revenue_v=REV_VALUE * revenue,
        growth=orders * c["new_share"] * pol.ltv_per_customer * LTV_DISCOUNT,
        inventory=c["inv_pressure"] * orders * c["unit_cost"] * INV_VALUE,
        cac=-(cac_over + roas_short), risk=-(b * c["risk_coef"]),
    )


def utility(c: dict, b: float, pol: Policy) -> float:
    t = terms(c, b, pol)
    w = _w(pol)
    return (w["profitability"] * t["profit"] + w["revenue"] * t["revenue_v"] + w["growth"] * t["growth"]
            + w["inventory"] * t["inventory"] + w["cac"] * t["cac"] + w["risk"] * t["risk"])


def utility_parts(c: dict, b0: float, b1: float, pol: Policy) -> dict:
    """Weighted contribution of each policy dimension to the change b0 -> b1."""
    a, z, w = terms(c, b0, pol), terms(c, b1, pol), _w(pol)
    return {
        "profitability": w["profitability"] * (z["profit"] - a["profit"]),
        "revenue": w["revenue"] * (z["revenue_v"] - a["revenue_v"]),
        "growth": w["growth"] * (z["growth"] - a["growth"]),
        "inventory": w["inventory"] * (z["inventory"] - a["inventory"]),
        "cac": w["cac"] * (z["cac"] - a["cac"]),
        "risk": w["risk"] * (z["risk"] - a["risk"]),
    }


def prepare(states: list[dict], pol: Policy, anomalies: list[dict]) -> list[dict]:
    anomalous = {a["campaign_id"]: a for a in anomalies if a.get("campaign_id")}
    out = []
    for s in states:
        c = dict(s)
        a = anomalous.get(c["campaign_id"])
        c["risk_coef"] = 0.35 * c["roas_cv"] + (0.25 * a["confidence"] * a["severity"] if a else 0.0)
        c["anomaly"] = a
        c["margin_ok"] = c["margin"] >= pol.min_margin
        out.append(c)
    return out


@dataclass
class Plan:
    budgets: dict           # campaign_id -> new budget
    flows: list             # [{src, dst, amount, profit, util}]
    paused: list            # campaign ids
    step: float
    reserve_used: float


def _sku_units(cs: dict, budgets: dict, pol: Policy) -> dict:
    u = defaultdict(float)
    for cid, c in cs.items():
        u[c["sku_id"]] += terms(c, budgets[cid], pol)["orders"]
    return u


def _can_increase(c: dict, b_new: float, pol: Policy, sku_units_after: float) -> bool:
    if not c["margin_ok"] or b_new > CEIL * c["b0"]:
        return False
    t = terms(c, b_new, pol)
    if t["orders"] <= 0:
        return False
    if t["revenue"] / b_new < pol.min_roas or b_new / t["orders"] > pol.max_cac:
        return False
    if sku_units_after > c["cap_units"] + 1e-9 and sku_units_after > 0:
        return False
    return True


def optimize(cprep: list[dict], pol: Policy, total_delta: float = 0.0) -> Plan:
    cs = {c["campaign_id"]: c for c in cprep}
    total = sum(c["b0"] for c in cprep)
    step = 1000.0 if total > 150_000 else 500.0
    budgets = {cid: c["b0"] for cid, c in cs.items()}
    pool: list[list] = []          # FIFO of [origin, amount]
    flows: dict = defaultdict(lambda: [0.0, 0.0, 0.0])   # (src,dst) -> amount, profit, util
    taken = defaultdict(float)
    paused = []

    # Hard pause: campaign is far below the ROAS bar and cannot be rescued by a fix we can name.
    for cid, c in cs.items():
        fixable = bool(c["anomaly"] and c["anomaly"]["kind"] in ("creative_fatigue", "post_click_issue", "auction_pressure"))
        if c["status"] != "active":
            continue
        if (c["roas"] < 0.65 * pol.min_roas and not fixable) or c["margin"] < 0.8 * pol.min_margin:
            paused.append(cid)
            pool.append([cid, budgets[cid]])
            flows[(cid, "POOL")][0] += budgets[cid]
            flows[(cid, "POOL")][1] += terms(c, 0, pol)["profit"] - terms(c, c["b0"], pol)["profit"]
            budgets[cid] = 0.0

    reserve = max(0.0, total_delta)
    if reserve > 0:
        pool.append(["RESERVE", reserve])
    debt = max(0.0, -total_delta)
    moved_cap = TURNOVER_CAP * total
    moved = 0.0

    def mu_up(cid):
        c = cs[cid]
        b = budgets[cid]
        if cid in paused:
            return None
        b2 = b + step
        units = _sku_units(cs, budgets, pol)
        after = units[c["sku_id"]] + terms(c, b2, pol)["orders"] - terms(c, b, pol)["orders"]
        if not _can_increase(c, b2, pol, after):
            return None
        return (utility(c, b2, pol) - utility(c, b, pol)) / step

    def mu_down(cid):
        c = cs[cid]
        b = budgets[cid]
        if cid in paused or b - step < max(FLOOR * c["b0"], 0.0) - 1e-9:
            return None
        if taken[cid] + step > SRC_CAP * c["b0"] + 1e-9 and not debt > 0:
            return None
        b2 = b - step
        du = (utility(c, b, pol) - utility(c, b2, pol)) / step      # utility lost per rupee removed
        units = _sku_units(cs, budgets, pol)
        if units[c["sku_id"]] > c["cap_units"] + 1e-9:                 # removing spend relieves a stockout
            du -= STOCK_PEN * c["price"] * (terms(c, b, pol)["orders"] - terms(c, b2, pol)["orders"]) / step
        return du

    # forced cuts when total budget is reduced
    while debt >= step - 1e-9:
        opts = {cid: mu_down(cid) for cid in cs}
        opts = {k: v for k, v in opts.items() if v is not None}
        if not opts:
            break
        src = min(opts, key=opts.get)
        c = cs[src]
        dprofit = terms(c, budgets[src] - step, pol)["profit"] - terms(c, budgets[src], pol)["profit"]
        budgets[src] -= step
        taken[src] += step
        flows[(src, "CUT")][0] += step
        flows[(src, "CUT")][1] += dprofit
        flows[(src, "CUT")][2] -= opts[src] * step
        debt -= step
        moved += step

    for _ in range(600):
        pool_total = sum(a for _, a in pool)
        ups = {cid: mu_up(cid) for cid in cs}
        ups = {k: v for k, v in ups.items() if v is not None}
        downs = {cid: mu_down(cid) for cid in cs}
        downs = {k: v for k, v in downs.items() if v is not None}
        if not ups:
            break
        dst = max(ups, key=ups.get)
        cands = dict(downs)
        if pool_total >= step - 1e-9:
            cands["POOL"] = 0.0                          # held cash has marginal utility 0
        cands.pop(dst, None)
        if not cands:
            break
        src = min(cands, key=cands.get)
        gain = ups[dst] - cands[src]
        if gain <= EPS or (src != "POOL" and moved + step > moved_cap + 1e-9):
            # nothing worth moving; release value-destroying spend into the pool instead
            neg = {k: v for k, v in downs.items() if v < -EPS}
            if neg and moved + step <= moved_cap + 1e-9:
                k = min(neg, key=neg.get)
                ck = cs[k]
                dprofit = terms(ck, budgets[k] - step, pol)["profit"] - terms(ck, budgets[k], pol)["profit"]
                budgets[k] -= step
                taken[k] += step
                pool.append([k, step])
                flows[(k, "POOL")][0] += step
                flows[(k, "POOL")][1] += dprofit
                flows[(k, "POOL")][2] += -neg[k] * step
                moved += step
                continue
            break
        cd = cs[dst]
        dprofit_dst = terms(cd, budgets[dst] + step, pol)["profit"] - terms(cd, budgets[dst], pol)["profit"]
        budgets[dst] += step
        if src == "POOL":
            origin, amt = pool[0]
            pool[0][1] -= step
            if pool[0][1] <= 1e-9:
                pool.pop(0)
            fl = flows[(origin, dst)]
            fl[0] += step
            fl[1] += dprofit_dst
            fl[2] += ups[dst] * step
        else:
            cs_ = cs[src]
            dprofit_src = terms(cs_, budgets[src] - step, pol)["profit"] - terms(cs_, budgets[src], pol)["profit"]
            budgets[src] -= step
            taken[src] += step
            moved += step
            fl = flows[(src, dst)]
            fl[0] += step
            fl[1] += dprofit_dst + dprofit_src
            fl[2] += gain * step

    # Fold (origin -> POOL) intermediate flows into (origin -> dst) flows; leftovers become RELEASED.
    final: list[dict] = []
    for (s_, d_), v in flows.items():
        if d_ in ("POOL",) or v[0] <= 0:
            continue
        final.append(dict(src=s_, dst=d_, amount=v[0], profit=v[1], util=v[2]))
    for (s_, d_), v in list(flows.items()):
        if d_ != "POOL":
            continue
        out_amt = sum(f["amount"] for f in final if f["src"] == s_ and f["dst"] not in ("CUT", "RELEASED"))
        for f in final:
            if f["src"] == s_ and f["dst"] not in ("CUT", "RELEASED"):
                f["profit"] += v[1] * f["amount"] / v[0]
        left = v[0] - out_amt
        if left > 1e-9:
            final.append(dict(src=s_, dst="RELEASED", amount=left, profit=v[1] * left / v[0], util=v[2] * left / v[0]))
    return Plan(budgets=budgets, flows=final, paused=paused, step=step,
                reserve_used=reserve - sum(a for o, a in pool if o == "RESERVE"))


def marginal_table(cprep: list[dict], pol: Policy, step: float = 1000.0) -> dict:
    """Marginal utility per rupee of the next step at current budgets (policy-aware)."""
    out = {}
    units = defaultdict(float)
    for c in cprep:
        units[c["sku_id"]] += terms(c, c["b0"], pol)["orders"]
    for c in cprep:
        b = c["b0"]
        mu = (utility(c, b + step, pol) - utility(c, b, pol)) / step
        after = units[c["sku_id"]] + terms(c, b + step, pol)["orders"] - terms(c, b, pol)["orders"]
        ok = _can_increase(c, b + step, pol, after)
        t0, t1 = terms(c, b, pol), terms(c, b + step, pol)
        marg_roas = (t1["revenue"] - t0["revenue"]) / step
        mp = (t1["profit"] - t0["profit"]) / step
        out[c["campaign_id"]] = dict(mu=mu, eligible=ok, marginal_roas=marg_roas, marginal_profit_per_rupee=mp)
    return out


def stable_id(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]
