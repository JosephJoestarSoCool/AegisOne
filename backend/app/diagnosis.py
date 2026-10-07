"""AI diagnosis: statistical anomaly detection + rule-scored root-cause hypotheses.

Every anomaly is explained as:
    what happened -> probable cause -> confidence -> recommended action

Detection: recent window (last 5 days) vs a clean 25-day baseline, robust z-score
(median / MAD) plus a minimum relative change. Root cause: each hypothesis is
scored from independent signals (CTR, CPC, CVR, frequency, creative age,
competitor price, unit cost, platform-wide peers); confidence = evidence score.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BASELINE_END, BASELINE_START, HISTORY_DAYS, RECENT_DAYS
from .metrics import CompanyData, daily_series
from .policy import Policy

REC_START = HISTORY_DAYS - RECENT_DAYS
BASE_START = HISTORY_DAYS - BASELINE_START
BASE_END = HISTORY_DAYS - BASELINE_END


def _robust_z(base: np.ndarray, recent_mean: float) -> float:
    med = float(np.median(base))
    mad = float(np.median(np.abs(base - med))) * 1.4826
    sd = max(mad, float(np.std(base)) * 0.6, abs(med) * 0.01, 1e-9)
    return (recent_mean - med) / (sd / np.sqrt(RECENT_DAYS))


_RATIOS = {"roas": ("revenue", "spend"), "ctr": ("clicks", "impressions"), "cpc": ("spend", "clicks"),
           "cvr": ("orders", "clicks"), "cac": ("spend", "orders"), "frequency": ("impressions", "reach")}


def _window(series: pd.DataFrame, col: str) -> tuple[float, float, float, float]:
    """(baseline, recent, relative change, robust z). Ratios use ratio-of-sums (not mean-of-ratios)."""
    bs = series[(series.day >= BASE_START) & (series.day < BASE_END)]
    rs = series[series.day >= REC_START]
    base = bs[col].to_numpy()
    base = base[np.isfinite(base)]
    num, den = _RATIOS[col]
    b = float(bs[num].sum() / bs[den].sum())
    r = float(rs[num].sum() / rs[den].sum())
    chg = (r - b) / b if b else 0.0
    return b, r, chg, _robust_z(base, r)


def _evid(label: str, base: float, cur: float, chg: float, fmt: str = "{:.2f}") -> dict:
    return dict(label=label, baseline=fmt.format(base), current=fmt.format(cur), change_pct=round(chg * 100, 1))


def detect(d: CompanyData, states: list[dict], policy: Policy | None = None) -> list[dict]:
    policy = policy or d.policy
    out: list[dict] = []
    st = {s["campaign_id"]: s for s in states}

    series = {cid: daily_series(d, cid) for cid in st}
    win = {cid: {m: _window(series[cid], m) for m in ["roas", "ctr", "cpc", "cvr", "frequency", "cac"]} for cid in st}

    # platform-wide CPC drift (peers) — separates auction pressure from campaign-specific problems
    plat_cpc: dict[str, list[float]] = {}
    for cid, w in win.items():
        plat_cpc.setdefault(st[cid]["platform_id"], []).append(w["cpc"][2])

    # SKU level: price ratio (competitor / ours) and unit cost / margin windows
    sku_sig = {}
    for sku_id in d.products["sku_id"]:
        pr = d.pricing[d.pricing.sku_id == sku_id].set_index("day")
        cp = d.comp[d.comp.sku_id == sku_id].set_index("day")
        net = pr["list_price"] * (1 - pr["discount_pct"])
        ratio = (cp["competitor_price"] / net).dropna()
        cost = pr["unit_cost"]
        margin = (net - cost) / net
        def w(s):
            b = float(s[(s.index >= BASE_START) & (s.index < BASE_END)].mean())
            r = float(s[s.index >= REC_START].mean())
            return b, r
        sku_sig[sku_id] = dict(ratio=w(ratio), cost=w(cost), margin=w(margin), net=float(net.iloc[-1]))

    for cid, s in st.items():
        w = win[cid]
        roas_b, roas_r, roas_c, roas_z = w["roas"]
        ctr_b, ctr_r, ctr_c, ctr_z = w["ctr"]
        cpc_b, cpc_r, cpc_c, cpc_z = w["cpc"]
        cvr_b, cvr_r, cvr_c, cvr_z = w["cvr"]
        fr_b, fr_r, fr_c, _ = w["frequency"]
        sig = sku_sig[s["sku_id"]]
        ratio_b, ratio_r = sig["ratio"]
        ratio_c = (ratio_r - ratio_b) / ratio_b if ratio_b else 0.0

        hit_roas = roas_c <= -0.15 and roas_z <= -3
        hit_cpc = cpc_c >= 0.20 and cpc_z >= 3
        hit_ctr = ctr_c <= -0.18 and ctr_z <= -3
        hit_cvr = cvr_c <= -0.20 and cvr_z <= -3
        if not (hit_roas or hit_cpc or hit_ctr or hit_cvr):
            continue

        peers = [v for k, v in plat_cpc.items() if k == s["platform_id"]][0]
        peers_up = sum(1 for x in peers if x >= 0.10) / max(len(peers), 1)

        hyp = {}
        # 1) creative fatigue
        if ctr_c <= -0.15:
            sc = 0.35 + 0.20 * (ctr_c <= -0.25) + 0.15 * (fr_c >= 0.40) + 0.10 * (abs(cvr_c) < 0.12) \
                + 0.10 * (s["creative_age"] > 35) + 0.10 * (cpc_c > 0.10)
            hyp["creative_fatigue"] = sc
        # 2) auction pressure / CPC inflation
        if cpc_c >= 0.20 and abs(ctr_c) < 0.10:
            sc = 0.45 + 0.20 * (cpc_c >= 0.35) + 0.15 * (abs(cvr_c) < 0.10) + 0.15 * (peers_up >= 0.3)
            hyp["auction_pressure"] = sc
        # 3) competitor price pressure
        if cvr_c <= -0.15 and ratio_c <= -0.08:
            sc = 0.50 + 0.20 * (ratio_c <= -0.15) + 0.15 * (abs(ctr_c) < 0.10) + 0.05 * (cvr_c <= -0.25)
            hyp["competitor_price_pressure"] = sc
        # 4) post-click problem (landing page / checkout / stock messaging)
        if cvr_c <= -0.25 and abs(ctr_c) < 0.08 and ratio_c > -0.08:
            sc = 0.55 + 0.15 * (cvr_c <= -0.40) + 0.10 * (abs(cpc_c) < 0.10) + 0.10 * (fr_c < 0.25)
            hyp["post_click_issue"] = sc
        if not hyp:
            hyp["unexplained_volatility"] = 0.40

        ranked = sorted(hyp.items(), key=lambda kv: -kv[1])
        cause, score = ranked[0]
        conf = float(min(0.95, score))
        alts = [dict(cause=_cause_label(k), confidence=round(min(0.9, v) * 0.8, 2)) for k, v in ranked[1:3]]

        evid = [_evid("ROAS (reconciled)", roas_b, roas_r, roas_c),
                _evid("CTR %", ctr_b * 100, ctr_r * 100, ctr_c),
                _evid("CPC ₹", cpc_b, cpc_r, cpc_c),
                _evid("Conversion rate %", cvr_b * 100, cvr_r * 100, cvr_c),
                _evid("Frequency", fr_b, fr_r, fr_c)]
        if cause == "competitor_price_pressure":
            evid.append(_evid("Competitor / our price", ratio_b, ratio_r, ratio_c, "{:.2f}x"))
        if cause == "creative_fatigue":
            evid.append(dict(label="Creative age (days)", baseline="—", current=str(s["creative_age"]), change_pct=0.0))

        what, action, atype = _narrate(cause, s, roas_b, roas_r, roas_c, ctr_c, cpc_c, cvr_c, fr_c, ratio_c, policy)
        sev = float(np.clip(abs(roas_c) * 1.6 if hit_roas else abs(max(abs(cpc_c), abs(ctr_c), abs(cvr_c))) * 1.1, 0.1, 1.0))
        spend_at_risk = s["b0"] * max(0.0, (roas_b - roas_r) / roas_b) if roas_b else 0.0
        out.append(dict(
            anomaly_id=f"an-{cid}-{cause}", kind=cause, level="campaign", campaign_id=cid, sku_id=s["sku_id"],
            campaign=s["name"], title=_title(cause, s), severity=round(sev, 2),
            metric="ROAS" if hit_roas else ("CPC" if hit_cpc else ("CTR" if hit_ctr else "Conversion")),
            what_happened=what, probable_cause=_cause_label(cause), confidence=round(conf, 2),
            recommended_action=action, action_type=atype, evidence=evid, alternatives=alts,
            daily_value_at_risk=round(spend_at_risk, 0),
            raw=dict(roas_base=roas_b, roas_now=roas_r, ctr_change=ctr_c, cpc_change=cpc_c, cvr_change=cvr_c),
        ))

    # ---- SKU level: margin, inventory, competitor pressure (no campaign hit) ----
    seen_skus = {s["sku_id"]: s for s in states}
    camp_hit_skus = {a["sku_id"] for a in out if a["kind"] == "competitor_price_pressure"}
    for sku_id, s in seen_skus.items():
        sig = sku_sig[sku_id]
        m_b, m_r = sig["margin"]
        c_b, c_r = sig["cost"]
        # margin
        cost_chg = (c_r - c_b) / c_b if c_b else 0.0
        if (m_b - m_r) >= 0.03 or (m_r < policy.min_margin <= m_b):
            conf = float(min(0.95, 0.60 + 0.20 * (cost_chg >= 0.05) + 0.10 * (m_r < policy.min_margin) + 0.05))
            breach = m_r < policy.min_margin
            out.append(dict(
                anomaly_id=f"an-{sku_id}-margin", kind="margin_squeeze", level="sku", campaign_id=None, sku_id=sku_id,
                campaign=s["sku_name"], title=f"Margin squeeze on {s['sku_name']}",
                severity=round(float(np.clip((m_b - m_r) * 8, 0.2, 1.0)), 2), metric="Margin",
                what_happened=f"Unit margin fell from {m_b*100:.1f}% to {m_r*100:.1f}% "
                              f"({'below' if breach else 'still above'} the {policy.min_margin*100:.0f}% policy floor).",
                probable_cause=f"Unit cost up {cost_chg*100:.1f}% (supplier / landed-cost increase) with no price change",
                confidence=round(conf, 2),
                recommended_action=("Stop scaling this SKU, cut spend on it and raise list price ~"
                                    f"{max(cost_chg*100, 3):.0f}% to restore margin." if breach else
                                    "Hold spend, watch margin; consider a small price increase."),
                action_type="guard_margin",
                evidence=[_evid("Unit margin %", m_b * 100, m_r * 100, (m_r - m_b) / m_b if m_b else 0),
                          _evid("Unit cost ₹", c_b, c_r, cost_chg, "{:.0f}")],
                alternatives=[], daily_value_at_risk=round(sum(x["revenue"] for x in states if x["sku_id"] == sku_id) * (m_b - m_r), 0)))
        # competitor price pressure standalone
        r_b, r_r = sig["ratio"]
        r_c = (r_r - r_b) / r_b if r_b else 0
        if r_c <= -0.10 and sku_id not in camp_hit_skus:
            out.append(dict(
                anomaly_id=f"an-{sku_id}-comp", kind="competitor_price_pressure", level="sku", campaign_id=None,
                sku_id=sku_id, campaign=s["sku_name"], title=f"Competitors undercutting {s['sku_name']}",
                severity=round(float(np.clip(abs(r_c) * 2, 0.2, 1.0)), 2), metric="Price gap",
                what_happened=f"Competitor price relative to ours dropped {abs(r_c)*100:.0f}%.",
                probable_cause=_cause_label("competitor_price_pressure"), confidence=0.6,
                recommended_action="Avoid scaling spend until price position is reviewed.",
                action_type="guard_price", evidence=[_evid("Competitor / our price", r_b, r_r, r_c, "{:.2f}x")],
                alternatives=[], daily_value_at_risk=0.0))
        # inventory
        dc, lead = s["inventory_days"], s["lead_time"]
        if s["stockout_risk"] >= 0.5:
            days_short = max(0.0, lead - dc)
            out.append(dict(
                anomaly_id=f"an-{sku_id}-stockout", kind="stockout_risk", level="sku", campaign_id=None, sku_id=sku_id,
                campaign=s["sku_name"], title=f"Stockout risk: {s['sku_name']}",
                severity=round(float(s["stockout_risk"]), 2), metric="Inventory",
                what_happened=f"{dc:.1f} days of cover left vs a {lead:.0f}-day restock lead time "
                              f"(≈{days_short:.1f} days of lost sales if ads keep scaling).",
                probable_cause="Ad-driven demand is outrunning replenishment",
                confidence=round(float(min(0.95, 0.65 + 0.3 * s["stockout_risk"])), 2),
                recommended_action="Cap spend on this SKU and redirect budget to SKUs with healthy cover.",
                action_type="guard_inventory",
                evidence=[dict(label="Days of cover", baseline=f"≥{lead*1.5:.0f} (safe)", current=f"{dc:.1f}", change_pct=0.0),
                          dict(label="Restock lead time (days)", baseline="—", current=f"{lead:.0f}", change_pct=0.0)],
                alternatives=[], daily_value_at_risk=round(sum(x["revenue"] for x in states if x["sku_id"] == sku_id) * 0.2, 0)))
        elif s["inv_pressure"] >= 1.0 and dc > s["target_days"] * 1.8:
            perish = s["shelf_life"] < 900
            out.append(dict(
                anomaly_id=f"an-{sku_id}-overstock", kind="overstock_risk", level="sku", campaign_id=None, sku_id=sku_id,
                campaign=s["sku_name"], title=f"{'Spoilage' if perish else 'Overstock'} risk: {s['sku_name']}",
                severity=round(float(np.clip(s["inv_pressure"] / 3, 0.2, 1.0)), 2), metric="Inventory",
                what_happened=f"{dc:.0f} days of cover vs a {s['target_days']:.0f}-day target"
                              + (f" and {s['shelf_life']:.0f}-day shelf life." if perish else "."),
                probable_cause="Sell-through slower than replenishment",
                confidence=0.8,
                recommended_action="Lean budget toward this SKU to clear stock" + (" before it expires." if perish else "."),
                action_type="push_inventory",
                evidence=[dict(label="Days of cover", baseline=f"{s['target_days']:.0f} target", current=f"{dc:.0f}", change_pct=0.0)],
                alternatives=[], daily_value_at_risk=0.0))

    out.sort(key=lambda a: (-a["severity"], -a["confidence"]))
    return out


_CAUSE = {
    "creative_fatigue": "Creative fatigue (audience has seen the ad too often)",
    "auction_pressure": "Auction pressure — CPMs rising, not a creative or funnel issue",
    "competitor_price_pressure": "Competitor price pressure (we are now priced above the market)",
    "post_click_issue": "Post-click problem (landing page / checkout / stock messaging)",
    "unexplained_volatility": "Unexplained volatility (no dominant signal)",
}


def _cause_label(k: str) -> str:
    return _CAUSE.get(k, k)


def _title(cause: str, s: dict) -> str:
    return {
        "creative_fatigue": f"ROAS drop · creative fatigue — {s['name']}",
        "auction_pressure": f"CPC spike — {s['name']}",
        "competitor_price_pressure": f"Conversion drop · competitor undercut — {s['name']}",
        "post_click_issue": f"Conversion drop · post-click issue — {s['name']}",
    }.get(cause, f"Anomaly — {s['name']}")


def _narrate(cause, s, roas_b, roas_r, roas_c, ctr_c, cpc_c, cvr_c, fr_c, ratio_c, policy):
    head = f"ROAS fell {abs(roas_c)*100:.0f}% (from {roas_b:.2f} to {roas_r:.2f}). " if roas_c <= -0.15 else ""
    if cause == "creative_fatigue":
        return (head + f"CTR dropped {abs(ctr_c)*100:.0f}% and CPC rose {max(cpc_c,0)*100:.0f}% while conversion rate "
                       f"held ({cvr_c*100:+.0f}%). Frequency is up {fr_c*100:.0f}% on a {s['creative_age']}-day-old creative.",
                "Replace the creative and pull budget toward higher-marginal-return campaigns until it recovers.",
                "replace_creative")
    if cause == "auction_pressure":
        return (head + f"CPC rose {cpc_c*100:.0f}% with CTR flat ({ctr_c*100:+.0f}%) and conversion flat ({cvr_c*100:+.0f}%): "
                       "you are paying more per impression, not getting worse engagement.",
                "Do not chase the auction — trim spend here and redeploy to platforms with cheaper reach.",
                "reduce_budget")
    if cause == "competitor_price_pressure":
        return (head + f"Conversion rate fell {abs(cvr_c)*100:.0f}% while CTR is stable ({ctr_c*100:+.0f}%). "
                       f"Competitor price relative to ours moved {ratio_c*100:.0f}% over the same days.",
                "Hold spend until pricing is reviewed; shift budget to SKUs where we hold price advantage.",
                "reduce_budget")
    if cause == "post_click_issue":
        return (head + f"Conversion rate collapsed {abs(cvr_c)*100:.0f}% while CTR and CPC are normal — "
                       "clicks arrive but do not buy.",
                "Pause scaling, audit the landing page / checkout, and divert spend meanwhile.",
                "reduce_budget")
    return (head + "Metrics moved outside their normal range without a dominant driver.",
            "Monitor for two more days; no budget change recommended.", "monitor")
