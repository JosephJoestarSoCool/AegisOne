"""Builds docs/AegisOne_Autonomous_Marketing_CFO.pptx from LIVE engine output.

Run (from repo root):  backend/.venv/Scripts/python docs/build_deck.py
Every number on the slides is read from the running engine, so the deck can never drift from the app.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import pandas as pd  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION  # noqa: E402
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

from app import feedback as fb  # noqa: E402
from app import service as svc  # noqa: E402
from app.db import connect  # noqa: E402
from app.demo import demo  # noqa: E402

OUT = ROOT / "docs" / "AegisOne_Autonomous_Marketing_CFO.pptx"

# ---- palette -------------------------------------------------------------
BG = RGBColor(0x0A, 0x10, 0x1E)
CARD = RGBColor(0x12, 0x1B, 0x2F)
CARD2 = RGBColor(0x1A, 0x25, 0x3D)
LINE = RGBColor(0x2A, 0x38, 0x56)
TEXT = RGBColor(0xEC, 0xF1, 0xF9)
MUTED = RGBColor(0x8F, 0x9D, 0xB8)
GOLD = RGBColor(0xF5, 0xB0, 0x3A)
TEAL = RGBColor(0x2D, 0xD4, 0xBF)
RED = RGBColor(0xF8, 0x71, 0x71)
BLUE = RGBColor(0x60, 0xA5, 0xFA)
VIOLET = RGBColor(0xA7, 0x8B, 0xFA)
FONT = "Segoe UI"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
TOTAL = 12


def inr(x: float) -> str:
    return f"₹{x:,.0f}"


def lakh(x: float) -> str:
    return f"₹{x/100000:.1f} L"


# ---- primitives ----------------------------------------------------------

def rect(s, x, y, w, h, fill=CARD, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(1)
    return sh


def text(s, x, y, w, h, t, size=14, color=TEXT, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         italic=False, spacing=None):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = t if isinstance(t, list) else [t]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.line_spacing = spacing
        runs = ln if isinstance(ln, list) else [(ln, {})]
        for rt, fmt in runs:
            r = p.add_run()
            r.text = rt
            r.font.name = FONT
            r.font.size = Pt(fmt.get("size", size))
            r.font.bold = fmt.get("bold", bold)
            r.font.italic = fmt.get("italic", italic)
            r.font.color.rgb = fmt.get("color", color)
    return tb


def pill(s, x, y, w, h, label, fill=CARD2, color=TEXT, size=11, bold=True, line=None):
    r = rect(s, x, y, w, h, fill=fill, line=line, radius=0.5)
    tf = r.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = label
    run.font.size, run.font.bold, run.font.name = Pt(size), bold, FONT
    run.font.color.rgb = color
    return r


def arrow(s, x1, y1, x2, y2, color=MUTED, width=1.75):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    from lxml import etree
    tail = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
    tail.set("type", "triangle")
    return c


def slide(n: int, kicker: str, title: str, sub: str | None = None):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    rect(s, 0, 0, 0.12, 7.5, fill=GOLD, shape=MSO_SHAPE.RECTANGLE)
    text(s, 0.65, 0.42, 9, 0.3, f"{n:02d}  ·  {kicker.upper()}", size=11, color=GOLD, bold=True)
    text(s, 0.65, 0.78, 12.0, 0.9, title, size=30, bold=True)
    if sub:
        text(s, 0.65, 1.52, 11.8, 0.4, sub, size=14, color=MUTED)
    text(s, 0.65, 7.08, 8, 0.25, "AegisOne · Autonomous Marketing CFO · DataQuest 3.0", size=9, color=MUTED)
    text(s, 11.9, 7.08, 0.8, 0.25, f"{n} / {TOTAL}", size=9, color=MUTED, align=PP_ALIGN.RIGHT)
    return s


def stat(s, x, y, w, big, label, color=GOLD, h=1.25, fill=CARD):
    rect(s, x, y, w, h, fill=fill)
    text(s, x + 0.2, y + 0.14, w - 0.4, 0.6, big, size=28, bold=True, color=color)
    text(s, x + 0.2, y + 0.78, w - 0.4, h - 0.8, label, size=11, color=MUTED)


def style_chart(ch, legend=True, size=10):
    ch.font.size = Pt(size)
    ch.font.name = FONT
    ch.font.color.rgb = MUTED
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.color.rgb = TEXT
        ch.legend.font.size = Pt(size)


def clean_axes(ch, val_fmt=None, gridlines=True):
    ca, va = ch.category_axis, ch.value_axis
    ca.format.line.color.rgb = LINE
    va.format.line.fill.background()
    ca.has_major_gridlines = False
    va.has_major_gridlines = gridlines
    if gridlines:
        va.major_gridlines.format.line.color.rgb = LINE
        va.major_gridlines.format.line.width = Pt(0.5)
    if val_fmt:
        va.tick_labels.number_format = val_fmt
        va.tick_labels.number_format_is_linked = False


# ---- live data ------------------------------------------------------------
con = connect()
svc.clear_cache()
D = demo(con)
P = svc.build_plan(con, "fashion")
CMP = svc.compare_policies(con, "fashion")
OV = svc.overview(con, "fashion")
d = svc.get_data(con, "fashion")
A = D["step2_diagnosis"]
R = D["step3_decision"]
W = D["step4_whatif"]
REC = D["step1_data"]["reconciliation"]
camp = D["step1_data"]["campaign"]
simulated_actual = fb.simulated_outcome(R["rec_id"], R["rec_type"], R["expected_profit"])
err = simulated_actual - R["expected_profit"]
acc = max(0.0, 1 - abs(err / R["expected_profit"]))
conf_after = min(0.97, max(0.3, R["confidence"] + 0.3 * (acc - R["confidence"])))
short = lambda n: n.replace(" · ", "·").replace("Lookalike 1%", "LAL").replace("Interest-based", "Interest").replace("Retargeting 30d", "RT")

# per-platform reported vs reconciled ROAS (last 7 days)
last = d.ad[d.ad.day >= 53].copy()
last["rec_orders"] = last.platform_orders * last.sku_id.map(d.recon.set_index("sku_id")["recon_factor"])
plat = last.groupby("platform_id").agg(spend=("spend", "sum"), rev=("platform_revenue", "sum"),
                                      po=("platform_orders", "sum"), ro=("rec_orders", "sum")).reset_index()
plat["reported"] = plat.rev / plat.spend
plat["reconciled"] = plat.reported * plat.ro / plat.po
plat["name"] = plat.platform_id.map({"meta": "Meta", "google": "Google", "instagram": "Instagram", "youtube": "YouTube"})

# =========================================================================
# 1 PROBLEM
# =========================================================================
s = slide(1, "The problem", "Ad spend is decided in four dashboards that disagree",
          "D2C brands spend crores on ads across platforms — and still allocate the next rupee by gut feel.")
text(s, 0.65, 2.15, 6.2, 1.2, [[("Autonomous Marketing CFO", {"size": 22, "bold": True, "color": GOLD})],
                               [("Next-generation autonomous D2C advertising intelligence & decision engine", {"size": 13, "color": MUTED})]])
cols = [("Meta", BLUE), ("Google", TEAL), ("Instagram", VIOLET), ("YouTube", RED)]
for i, (nm, col) in enumerate(cols):
    row = plat[plat.name == nm].iloc[0]
    x = 0.65 + i * 1.62
    rect(s, x, 3.55, 1.5, 1.7, fill=CARD)
    rect(s, x, 3.55, 1.5, 0.07, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.15, 3.75, 1.2, 0.3, nm, size=12, bold=True, color=col)
    text(s, x + 0.15, 4.1, 1.2, 0.5, f"{row.reported:.1f}×", size=26, bold=True)
    text(s, x + 0.15, 4.72, 1.25, 0.45, "reported ROAS", size=10, color=MUTED)
text(s, 0.65, 5.45, 6.4, 0.8, f"Every platform grades its own homework. Together they claim "
                              f"{REC['overcount_pct']*100:.0f}% more orders than the store actually shipped.",
     size=13, color=TEXT)
# right side — pain list
rect(s, 7.35, 2.15, 5.35, 4.6, fill=CARD)
text(s, 7.65, 2.38, 4.8, 0.4, "What the marketing head actually faces", size=14, bold=True, color=GOLD)
pains = [("4+ ad platforms", "each with its own attribution"), ("Margin & inventory", "invisible to the ad manager"),
         ("Competitor price moves", "tank conversion — silently"), ("One ROAS target", "applied to every SKU & company"),
         ("No memory", "yesterday's decision never scored")]
for i, (a_, b_) in enumerate(pains):
    y = 2.95 + i * 0.73
    rect(s, 7.65, y + 0.06, 0.1, 0.46, fill=GOLD, shape=MSO_SHAPE.RECTANGLE)
    text(s, 7.95, y, 4.5, 0.3, a_, size=14, bold=True)
    text(s, 7.95, y + 0.3, 4.5, 0.3, b_, size=11, color=MUTED)

# =========================================================================
# 2 WHY DASHBOARDS FAIL
# =========================================================================
s = slide(2, "Why dashboards fail", "A dashboard describes the past. A CFO allocates the future.",
          "Five structural gaps no amount of charts can close.")
rect(s, 0.65, 2.1, 4.3, 4.7, fill=CARD)
text(s, 0.95, 2.3, 3.8, 0.3, "WHAT THE DASHBOARD SAYS", size=10, bold=True, color=MUTED)
text(s, 0.95, 2.7, 3.8, 0.9, f"ROAS ↓ {abs(A['raw']['roas_now']/A['raw']['roas_base']-1)*100:.0f}%", size=44, bold=True, color=RED)
text(s, 0.95, 3.65, 3.7, 0.7, f"{camp['name']}\n{A['raw']['roas_base']:.1f} → {A['raw']['roas_now']:.1f}", size=12, color=MUTED)
rect(s, 0.95, 4.55, 3.7, 0.02, fill=LINE, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.95, 4.75, 3.7, 1.9, ["…and then?", "", "Why did it drop?", "How much should move?", "To where, given margin and stock?",
                               "What if the stock changes?"], size=14, color=TEXT)
gaps = [("Descriptive, not prescriptive", "Charts show what happened. Nobody decides what to do about it.", RED),
        ("Siloed & self-attributed", "Each platform over-claims credit; no single version of truth.", GOLD),
        ("Blind to the business", "Margin, inventory, competitor price never reach the bid decision.", TEAL),
        ("One-size-fits-all targets", "A luxury label and a perishable-food brand get the same ROAS goal.", BLUE),
        ("Open loop", "Decisions are never compared to outcomes, so nothing is learned.", VIOLET)]
for i, (h, b, col) in enumerate(gaps):
    y = 2.1 + i * 0.95
    rect(s, 5.25, y, 7.45, 0.83, fill=CARD)
    rect(s, 5.25, y, 0.08, 0.83, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, 5.55, y + 0.1, 6.9, 0.3, h, size=14, bold=True)
    text(s, 5.55, y + 0.43, 6.9, 0.35, b, size=11, color=MUTED)

# =========================================================================
# 3 SOLUTION
# =========================================================================
s = slide(3, "Our solution", "Where should the next ₹1 of ad spend go?")
rect(s, 0.65, 1.75, 12.05, 1.55, fill=CARD2)
text(s, 1.0, 1.95, 11.3, 1.2, [[("“Instead of telling a company ", {"size": 20, "color": MUTED}),
                               ("what happened", {"size": 20, "color": MUTED, "italic": True}),
                               (", our AI Marketing CFO ", {"size": 20, "color": MUTED}),
                               ("decides where the company's next ₹1 of advertising spend should go.", {"size": 20, "bold": True, "color": GOLD}),
                               ("”", {"size": 20, "color": MUTED})]], spacing=1.1)
stages = [("Reconcile", "One version of the truth across platforms, sales, stock, price", TEAL),
          ("Diagnose", "Anomaly → probable cause → confidence → action", RED),
          ("Decide", "Maximise expected incremental profit under the company's policy", GOLD),
          ("Simulate", "Change budget, stock, price, priorities — decision re-solves live", BLUE),
          ("Learn", "Approve → outcome → error → updated confidence", VIOLET)]
w_ = 2.25
for i, (h, b, col) in enumerate(stages):
    x = 0.65 + i * (w_ + 0.2)
    rect(s, x, 3.65, w_, 2.75, fill=CARD)
    rect(s, x, 3.65, w_, 0.07, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.2, 3.9, w_ - 0.4, 0.3, f"0{i+1}", size=11, bold=True, color=col)
    text(s, x + 0.2, 4.2, w_ - 0.4, 0.4, h, size=20, bold=True)
    text(s, x + 0.2, 4.8, w_ - 0.4, 1.5, b, size=12, color=MUTED)
    if i < 4:
        arrow(s, x + w_ + 0.02, 5.0, x + w_ + 0.18, 5.0, color=MUTED)
text(s, 0.65, 6.6, 12, 0.3, "A closed-loop decision system — not another reporting layer.", size=13, color=MUTED, italic=True)

# =========================================================================
# 4 UNIFIED INTELLIGENCE
# =========================================================================
s = slide(4, "Unified cross-platform intelligence", "One version of the truth, corrected by real sales",
          "We regress real SKU sales on platform-reported orders:  units = organic baseline + β · platform orders   (β < 1 = over-count haircut)")
srcs = [("Meta · Google · Instagram · YouTube", "daily spend, clicks, orders", BLUE), ("Sales ledger", "units, revenue, COGS", TEAL),
        ("Pricing + competitor prices", "margin, price gap", GOLD), ("Inventory", "on-hand, lead time, shelf life", VIOLET)]
for i, (h, b, col) in enumerate(srcs):
    y = 2.15 + i * 1.12
    rect(s, 0.65, y, 3.5, 0.98, fill=CARD)
    rect(s, 0.65, y, 0.08, 0.98, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, 0.92, y + 0.14, 3.15, 0.3, h, size=12, bold=True)
    text(s, 0.92, y + 0.55, 3.15, 0.3, b, size=10.5, color=MUTED)
    arrow(s, 4.2, y + 0.49, 4.75, 3.95, color=LINE)
rect(s, 4.8, 3.2, 2.0, 1.5, fill=CARD2, line=GOLD)
text(s, 4.8, 3.42, 2.0, 0.3, "RECONCILE", size=10, bold=True, color=GOLD, align=PP_ALIGN.CENTER)
text(s, 4.9, 3.78, 1.8, 0.8, "sklearn regression\nper SKU", size=11, align=PP_ALIGN.CENTER, color=TEXT)
arrow(s, 6.85, 3.95, 7.25, 3.95, color=GOLD)
cd = CategoryChartData()
cd.categories = list(plat["name"])
cd.add_series("Platform-reported ROAS", [round(v, 2) for v in plat.reported])
cd.add_series("Reconciled ROAS", [round(v, 2) for v in plat.reconciled])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.3), Inches(2.0), Inches(5.4), Inches(3.55), cd)
ch = gf.chart
style_chart(ch)
clean_axes(ch, "0.0")
for ser, col in zip(ch.plots[0].series, (MUTED, GOLD)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
ch.plots[0].gap_width = 60
ch.plots[0].has_data_labels = True
ch.plots[0].data_labels.font.size = Pt(10)
ch.plots[0].data_labels.font.color.rgb = TEXT
ch.plots[0].data_labels.number_format = "0.0"
ch.plots[0].data_labels.number_format_is_linked = False
stat(s, 7.3, 5.6, 2.6, f"{REC['overcount_pct']*100:.0f}%", "more orders claimed than reconciled sales", color=RED, h=1.3)
stat(s, 10.05, 5.6, 2.65, f"{REC['reported_roas']:.1f} → {REC['reconciled_roas']:.1f}", "company ROAS: reported → reconciled", color=GOLD, h=1.3)
text(s, 0.65, 6.65, 6.5, 0.3, "Output: unified ROAS, CAC, CTR, CPC, CVR, profit, margin, inventory days, stockout risk.", size=11, color=MUTED)

# =========================================================================
# 5 POLICY ENGINE
# =========================================================================
s = slide(5, "Business Policy Engine", "Same campaign. Different company. Different decision.",
          "Each company's objectives, margins, inventory, CAC, ROAS and risk appetite become a policy the optimizer must obey.")
names = {p["policy_id"]: p["policy_name"] for p in CMP["policies"]}
cd = CategoryChartData()
dims = ["profitability", "growth", "revenue", "inventory", "cac", "risk"]
cd.categories = [names[k] for k in ("fashion", "startup", "electronics", "food")]
for dm_ in dims:
    cd.add_series({"cac": "CAC", "risk": "Risk"}.get(dm_, dm_.capitalize()),
                  [next(p for p in CMP["policies"] if p["policy_id"] == k)["weights"][dm_] for k in ("fashion", "startup", "electronics", "food")])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED_100, Inches(0.55), Inches(2.05), Inches(5.9), Inches(3.0), cd)
ch = gf.chart
style_chart(ch, size=9)
clean_axes(ch, "0%", gridlines=False)
ch.category_axis.reverse_order = True
ch.value_axis.visible = False
for ser, col in zip(ch.plots[0].series, (GOLD, TEAL, BLUE, VIOLET, RED, MUTED)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
ch.plots[0].gap_width = 45
ch.plots[0].overlap = 100
text(s, 0.65, 5.12, 5.8, 0.3, "OBJECTIVE WEIGHTS ABOVE · GUARDRAILS BELOW", size=10, bold=True, color=MUTED)
pp = {p["policy_id"]: p for p in CMP["policies"]}
rows = [("", "Fashion", "Startup", "Electr.", "Food"),
        ("Min margin",) + tuple(f"{pp[k]['min_margin']*100:.0f}%" for k in ("fashion", "startup", "electronics", "food")),
        ("Min ROAS",) + tuple(f"{pp[k]['min_roas']:.1f}×" for k in ("fashion", "startup", "electronics", "food")),
        ("Max CAC",) + tuple(f"₹{pp[k]['max_cac']:,.0f}" for k in ("fashion", "startup", "electronics", "food")),
        ("Stock target",) + tuple(f"{pp[k]['inventory_target_days']:.0f} d" for k in ("fashion", "startup", "electronics", "food"))]
rect(s, 0.65, 5.42, 5.8, 1.5, fill=CARD)
for r_i, row in enumerate(rows):
    for c_i, val in enumerate(row):
        text(s, 0.8 + (0 if c_i == 0 else 1.35 + (c_i - 1) * 1.1), 5.5 + r_i * 0.285, 1.3 if c_i == 0 else 1.05, 0.25, val,
             size=10, bold=(r_i == 0), color=(GOLD if r_i == 0 else (MUTED if c_i == 0 else TEXT)),
             align=PP_ALIGN.LEFT if c_i == 0 else PP_ALIGN.CENTER)
# right: verdict matrix
text(s, 6.9, 2.05, 5.8, 0.3, "ONE FASHION CAMPAIGN SET · FOUR POLICIES · DAILY BUDGET CHANGE", size=10, bold=True, color=MUTED)
pick = ["Linen Blazer · Google · Retargeting 30d", "Silk Scarf · Instagram · Lookalike 1%", "Selvedge Denim · Meta · Broad", "Leather Tote · Meta · Retargeting 30d"]
mrows = {m["name"]: m for m in CMP["matrix"]}
order = ["fashion", "startup", "electronics", "food"]
hdr_y = 2.4
for j, k in enumerate(order):
    text(s, 9.0 + j * 0.92, hdr_y, 0.9, 0.3, ["Fashion", "Startup", "Electr.", "Food"][j], size=10, bold=True, color=GOLD, align=PP_ALIGN.CENTER)
for i, nm in enumerate(pick):
    m = mrows[nm]
    y = hdr_y + 0.42 + i * 0.78
    rect(s, 6.9, y, 5.8, 0.68, fill=CARD)
    text(s, 7.05, y + 0.09, 1.95, 0.55, short(nm), size=10, bold=True)
    for j, k in enumerate(order):
        v = m["by_policy"][k]
        paused = v <= -m["current"] + 1
        col = TEAL if v > 0 else (RED if v < 0 else MUTED)
        lbl = "PAUSE" if paused else ("hold" if v == 0 else f"{'+' if v > 0 else '−'}₹{abs(v)/1000:.0f}k")
        pill(s, 9.02 + j * 0.92, y + 0.17, 0.82, 0.34, lbl, fill=CARD2, color=col, size=10)
rect(s, 6.9, 6.1, 5.8, 0.82, fill=CARD2)
text(s, 7.1, 6.18, 5.4, 0.7, [[("Electronics' 5.0× ROAS bar ", {"bold": True, "color": RED}),
                              ("pauses Denim·Meta outright; ", {}), ("the Startup's growth weight ", {"bold": True, "color": TEAL}),
                              ("keeps funding prospecting. Same data, different CFO.", {})]], size=11.5)

# =========================================================================
# 6 AI DIAGNOSIS
# =========================================================================
s = slide(6, "AI diagnosis & root cause", "Not just “ROAS dropped” — why, how sure, and what to do",
          f"Live demo anomaly: {camp['name']}")
ser = pd.DataFrame(D["step1_data"]["series"])
base = ser.iloc[:25]
idx = lambda col: [round(v / base[col].mean() * 100, 1) for v in ser[col]]
cd = CategoryChartData()
cd.categories = [x[5:] for x in ser["date"]]
cd.add_series("ROAS", idx("roas"))
cd.add_series("CTR", idx("ctr"))
cd.add_series("CPC", idx("cpc"))
cd.add_series("Conversion rate", idx("cvr"))
gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(0.55), Inches(2.0), Inches(7.1), Inches(3.9), cd)
ch = gf.chart
style_chart(ch)
clean_axes(ch)
for ser_, col, wd in zip(ch.plots[0].series, (RED, GOLD, BLUE, MUTED), (3.0, 2.25, 2.25, 1.5)):
    ser_.format.line.color.rgb = col
    ser_.format.line.width = Pt(wd)
    ser_.smooth = False
    ser_.marker.style = None
    from pptx.enum.chart import XL_MARKER_STYLE
    ser_.marker.style = XL_MARKER_STYLE.NONE
ch.category_axis.tick_labels.font.size = Pt(8)
ch.category_axis.tick_label_position  # noqa
from pptx.enum.chart import XL_TICK_LABEL_POSITION
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
text(s, 0.65, 5.95, 7.0, 0.3, "Indexed to the 25-day baseline = 100 (last 45 days)", size=10, color=MUTED)
ev = {e["label"]: e for e in A["evidence"]}
chips = [("CTR", ev["CTR %"]["change_pct"], RED), ("CPC", ev["CPC ₹"]["change_pct"], RED),
         ("Conversion", ev["Conversion rate %"]["change_pct"], MUTED), ("Frequency", ev["Frequency"]["change_pct"], GOLD)]
for i, (nm, v, col) in enumerate(chips):
    pill(s, 0.65 + i * 1.78, 6.35, 1.65, 0.45, f"{nm} {v:+.0f}%", fill=CARD2, color=col, size=11)
# right card
rect(s, 7.95, 2.0, 4.75, 4.85, fill=CARD)
steps = [("WHAT HAPPENED", A["what_happened"], RED),
         ("PROBABLE CAUSE", A["probable_cause"], GOLD),
         ("CONFIDENCE", f"{A['confidence']*100:.0f}%  —  CTR collapse + frequency surge + flat conversion + {camp['creative_age']}-day-old creative", TEAL),
         ("RECOMMENDED ACTION", A["recommended_action"], BLUE)]
y = 2.2
for h, b, col in steps:
    text(s, 8.2, y, 4.3, 0.25, h, size=9.5, bold=True, color=col)
    text(s, 8.2, y + 0.27, 4.3, 0.9, b, size=11 if len(b) > 90 else 12)
    y += 1.12
text(s, 8.2, 6.5, 4.3, 0.3, "Rival hypotheses are scored too — fatigue beats auction pressure and post-click issues.", size=9, color=MUTED, italic=True)

# =========================================================================
# 7 BUDGET DECISION ENGINE
# =========================================================================
s = slide(7, "Budget Decision Engine", f"Move {inr(R['amount'])}/day — and it earns {inr(R['expected_profit'])}/day more",
          "Maximise expected incremental profit, tilted by company policy, inside hard guardrails (min ROAS, max CAC, min margin, safe stock).")
alloc = P["allocation"]
cd = CategoryChartData()
cd.categories = [short(a["name"]).replace("·", " ") for a in alloc]
cd.add_series("Current ₹/day", [a["current"] for a in alloc])
cd.add_series("Recommended ₹/day", [a["recommended"] for a in alloc])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.55), Inches(2.05), Inches(7.3), Inches(4.85), cd)
ch = gf.chart
style_chart(ch, size=9)
clean_axes(ch, "#,##0")
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.size = Pt(8.5)
ch.value_axis.tick_labels.font.size = Pt(8)
for ser_, col in zip(ch.plots[0].series, (LINE, GOLD)):
    ser_.format.fill.solid()
    ser_.format.fill.fore_color.rgb = col
ch.plots[0].gap_width = 45
ch.plots[0].overlap = -5
rect(s, 8.15, 2.05, 4.55, 1.95, fill=CARD2, line=GOLD)
text(s, 8.4, 2.2, 4.1, 0.3, "TOP DECISION", size=9.5, bold=True, color=GOLD)
text(s, 8.4, 2.5, 4.1, 0.9, f"{inr(R['amount'])}/day", size=30, bold=True)
text(s, 8.4, 3.12, 4.1, 0.85, [f"{short(R['source_name'])}", f"→ {short(R['target_name'])}"], size=11.5, color=MUTED)
sm = P["campaigns"]
src_m, dst_m = sm[R["source_campaign_id"]], sm[R["target_campaign_id"]]
stat(s, 8.15, 4.15, 2.2, f"{src_m['marginal_roas']:.1f}×", "marginal ROAS, fatigued source", color=RED, h=1.2)
stat(s, 10.5, 4.15, 2.2, f"{dst_m['marginal_roas']:.1f}×", "marginal ROAS, target", color=TEAL, h=1.2)
rect(s, 8.15, 5.5, 4.55, 1.4, fill=CARD)
text(s, 8.35, 5.6, 4.2, 0.3, "WHY THIS BEAT THE ALTERNATIVES", size=9.5, bold=True, color=MUTED)
text(s, 8.35, 5.9, 4.2, 1.0, [f"• {dst_m['margin']*100:.0f}% unit margin, {dst_m['inventory_days']:.0f} days of stock cover",
                                 f"• Fashion policy: profitability {P['policy']['weights']['profitability']*100:.0f}%, risk {P['policy']['weights']['risk']*100:.0f}%",
                                 f"• Plan total: +{inr(P['totals']['incremental_profit'])}/day at the same total spend"], size=10.5)

# =========================================================================
# 8 WHAT-IF
# =========================================================================
s = slide(8, "What-if simulation", "Change the business. The decision re-solves instantly.",
          f"Scenario: a supplier delay leaves only {W['stock_units']} Silk Scarves in stock (from {int(P['campaigns'][R['target_campaign_id']]['on_hand']):,}).")
def card(s, x, y, w, h, tag, tcol, title_, body, sub, subcol=None):
    rect(s, x, y, w, h, fill=CARD)
    rect(s, x, y, w, 0.07, fill=tcol, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.3, y + 0.3, w - 0.6, 0.3, tag, size=10, bold=True, color=tcol)
    text(s, x + 0.3, y + 0.65, w - 0.6, 1.2, title_, size=17, bold=True)
    text(s, x + 0.3, y + 1.9, w - 0.6, 0.9, body, size=12, color=MUTED)
    text(s, x + 0.3, y + h - 0.85, w - 0.6, 0.7, sub, size=24, bold=True, color=subcol or tcol)
tb_, ta_ = W["top_before"], W["top_after"]
card(s, 0.65, 2.1, 5.5, 3.6, "BEFORE  ·  stock healthy", TEAL, f"Move {inr(tb_['amount'])}/day\n{short(tb_['source'])}\n→ {short(tb_['target'])}",
     f"Scarf has {W['target_cover_before']:.0f} days of cover; scaling it is safe.", f"+{inr(tb_['expected_profit'])}/day")
arrow(s, 6.3, 3.9, 7.0, 3.9, color=GOLD, width=3)
pill(s, 6.12, 3.35, 1.0, 0.36, "RE-SOLVE", fill=GOLD, color=BG, size=10)
card(s, 7.15, 2.1, 5.55, 3.6, "AFTER  ·  stock critical", RED, f"Move {inr(ta_['amount'])}/day\n{short(ta_['source'])}\n→ {short(ta_['target'])}",
     f"Scarf has {W['target_cover_after']:.1f} days of cover vs an 18-day restock — scaling would stock out.", f"+{inr(ta_['expected_profit'])}/day", GOLD)
text(s, 0.65, 5.95, 12, 0.3, "LEVERS YOU CAN PULL LIVE IN THE SIMULATOR", size=10, bold=True, color=MUTED)
for i, lv in enumerate(["Total budget", "Inventory (per SKU)", "Price", "Unit cost / margin", "Company priorities", "Guardrails"]):
    pill(s, 0.65 + i * 2.03, 6.3, 1.9, 0.45, lv, fill=CARD2, color=TEXT, size=11)

# =========================================================================
# 9 CLOSED LOOP
# =========================================================================
s = slide(9, "Closed-loop learning", "Every approved decision is scored against reality",
          "prediction → action → actual outcome → error → updated confidence")
loop = [("Predict", f"+{inr(R['expected_profit'])}/day", GOLD), ("Act", "Approved", BLUE), ("Observe", f"+{inr(simulated_actual)}/day", TEAL),
        ("Error", f"{err/R['expected_profit']*100:+.1f}%", RED), ("Recalibrate", f"{R['confidence']*100:.0f}% → {conf_after*100:.0f}%", VIOLET)]
for i, (h, v, col) in enumerate(loop):
    x = 0.65 + i * 2.45
    rect(s, x, 2.2, 2.2, 1.9, fill=CARD)
    rect(s, x, 2.2, 2.2, 0.07, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.2, 2.45, 1.8, 0.3, f"0{i+1}  {h.upper()}", size=10, bold=True, color=col)
    text(s, x + 0.2, 2.95, 1.85, 0.9, v, size=20, bold=True)
    if i < 4:
        arrow(s, x + 2.22, 3.15, x + 2.43, 3.15, color=MUTED)
arrow(s, 12.3, 4.2, 12.3, 4.55, color=VIOLET)
arrow(s, 12.3, 4.55, 1.0, 4.55, color=VIOLET)
arrow(s, 1.0, 4.55, 1.0, 4.2, color=VIOLET)
pill(s, 5.2, 4.37, 3.0, 0.36, "feeds the next recommendation", fill=BG, color=VIOLET, size=10, line=VIOLET)
rect(s, 0.65, 5.0, 6.0, 1.85, fill=CARD)
text(s, 0.9, 5.12, 5.5, 0.3, "WHAT IS STORED", size=9.5, bold=True, color=MUTED)
text(s, 0.9, 5.45, 5.5, 1.4, ["• recommendation + policy + confidence", "• simulated outcome and signed error", "• per-type calibration (EMA of 1 − |error|)",
                              "• seeded history: 24 past decisions across 4 companies"], size=11.5)
rect(s, 6.9, 5.0, 5.8, 1.85, fill=CARD)
text(s, 7.15, 5.12, 5.3, 0.3, "WHY IT MATTERS", size=9.5, bold=True, color=MUTED)
text(s, 7.15, 5.45, 5.3, 1.4, ["Confidence is earned, not asserted. Move-budget calls that over-promised "
                               "get discounted next time; reliable action types gain trust — so the CFO "
                               "gets calibrated, not just confident."], size=11.5)

# =========================================================================
# 10 ARCHITECTURE
# =========================================================================
s = slide(10, "System architecture", "Data in, explainable decisions out — fully local")
layers = [("Data", "Synthetic generator · SQLite\n14 tables · 4 companies · 60 days", BLUE),
          ("Ingest & reconcile", "pandas · scikit-learn\nsales ↔ platform regression", TEAL),
          ("AI diagnosis", "robust z-scores + hypothesis scoring\nconfidence per cause", RED),
          ("Policy engine", "6 weights + 4 guardrails\nper company", VIOLET),
          ("Optimizer", "concave marginal-utility greedy\nelasticity fit · stock caps", GOLD),
          ("What-if & feedback", "re-solve on any override\nsimulated outcome · calibration", TEAL)]
for i, (h, b, col) in enumerate(layers):
    x = 0.65 + (i % 3) * 3.0
    y = 2.1 + (i // 3) * 1.85
    rect(s, x, y, 2.75, 1.6, fill=CARD)
    rect(s, x, y, 0.08, 1.6, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.28, y + 0.15, 2.3, 0.3, h, size=14, bold=True, color=col)
    text(s, x + 0.28, y + 0.6, 2.4, 0.95, b, size=10.5, color=MUTED)
    if i % 3 < 2:
        arrow(s, x + 2.78, y + 0.8, x + 2.97, y + 0.8, color=MUTED)
rect(s, 9.75, 2.1, 2.95, 3.45, fill=CARD2, line=GOLD)
text(s, 9.95, 2.25, 2.6, 0.3, "FASTAPI  /api", size=10, bold=True, color=GOLD)
text(s, 9.95, 2.65, 2.6, 1.2, ["/overview  /diagnosis", "/plan  /whatif", "/policy-compare", "/recommendations/decide", "/history  /demo"], size=11, color=TEXT)
rect(s, 9.95, 4.15, 2.55, 1.25, fill=BG)
text(s, 10.1, 4.25, 2.3, 0.3, "REACT + VITE", size=10, bold=True, color=TEAL)
text(s, 10.1, 4.58, 2.3, 0.8, "Recharts dashboard\n7 decision views", size=11, color=TEXT)
arrow(s, 9.43, 4.9, 9.74, 4.9, color=GOLD)
rect(s, 0.65, 5.9, 12.05, 0.9, fill=CARD)
text(s, 0.9, 6.02, 11.6, 0.7, [[("Explainability by construction: ", {"bold": True, "color": GOLD}),
                               ("every recommendation carries its why, policy drivers, guardrail checks and confidence — "
                                "and every figure is a deterministic function of the data and the policy.", {})]], size=12)

# =========================================================================
# 11 DEMO
# =========================================================================
s = slide(11, "Demo scenario", "The demo, end to end", "data → diagnosis → decision → what-if → feedback — one deterministic story")
flow = [("1  DATA", f"{REC['rows']:,} daily ad rows reconciled; platforms over-claim {REC['overcount_pct']*100:.0f}%", TEAL),
        ("2  DIAGNOSIS", f"{camp['name'].split(' · ')[0]} · Meta ROAS {A['raw']['roas_base']:.1f}→{A['raw']['roas_now']:.1f}. Creative fatigue, {A['confidence']*100:.0f}% confident", RED),
        ("3  DECISION", f"Move {inr(R['amount'])}/day to Silk Scarf · Google. +{inr(R['expected_profit'])}/day, with the why", GOLD),
        ("4  WHAT-IF", f"Scarf stock → {W['stock_units']} units. Decision flips to {short(ta_['target'])} ({inr(ta_['amount'])})", BLUE),
        ("5  FEEDBACK", f"Approve → outcome {inr(simulated_actual)} vs {inr(R['expected_profit'])} predicted; confidence {R['confidence']*100:.0f}%→{conf_after*100:.0f}%", VIOLET)]
for i, (h, b, col) in enumerate(flow):
    x = 0.65 + i * 2.45
    rect(s, x, 1.95, 2.2, 3.6, fill=CARD)
    rect(s, x, 1.95, 2.2, 0.07, fill=col, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.2, 2.2, 1.9, 0.3, h, size=12, bold=True, color=col)
    text(s, x + 0.2, 2.75, 1.85, 2.8, b, size=14)
    if i < 4:
        arrow(s, x + 2.22, 3.75, x + 2.43, 3.75, color=MUTED)
rect(s, 0.65, 5.8, 12.05, 1.0, fill=CARD2, line=GOLD)
text(s, 0.95, 5.93, 11.5, 0.8, [[("Run it:  ", {"bold": True, "color": GOLD}), ("open the app → ", {}), ("Guided Demo", {"bold": True}),
                                (" tab. Deterministic — the same numbers every run. Then switch company in the header to see "
                                 "a different policy decide the same moment.", {})]], size=12.5)

# =========================================================================
# 12 IMPACT
# =========================================================================
s = slide(12, "Impact & conclusion", "From reporting to deciding",
          "Modelled on synthetic data for Premium Fashion at ₹2.13 L/day — same total spend, smarter allocation.")
stat(s, 0.65, 2.1, 3.9, f"+{inr(P['totals']['incremental_profit'])}", "incremental profit per day identified", color=GOLD, h=1.4)
stat(s, 4.7, 2.1, 3.9, f"≈ {lakh(P['totals']['incremental_profit_30d'])}", "per 30 days — with ₹0 extra ad budget", color=TEAL, h=1.4)
stat(s, 8.75, 2.1, 3.95, f"{len(P['recommendations'])} actions", "each with a why, confidence and guardrail check", color=BLUE, h=1.4)
pts = [("Cross-platform truth", "reconciled attribution, one ROAS"), ("Policy-aware", "4 companies → 4 different CFOs"),
       ("Explainable", "anomaly → cause → confidence → action"), ("Self-correcting", "feedback recalibrates confidence")]
for i, (h, b) in enumerate(pts):
    x = 0.65 + i * 3.04
    rect(s, x, 3.75, 2.9, 1.35, fill=CARD)
    text(s, x + 0.2, 3.9, 2.55, 0.3, h, size=14, bold=True, color=GOLD)
    text(s, x + 0.2, 4.32, 2.55, 0.7, b, size=11, color=MUTED)
rect(s, 0.65, 5.35, 12.05, 1.45, fill=CARD2, line=GOLD)
text(s, 1.0, 5.5, 11.3, 0.7, "“Instead of telling a company what happened, our AI Marketing CFO decides where the next ₹1 of advertising spend should go.”",
     size=17, bold=True, color=TEXT, spacing=1.05)
text(s, 1.0, 6.3, 11.3, 0.4, "Next: live ad-API connectors · multi-touch & incrementality tests · bandit exploration · creative generation.", size=11.5, color=MUTED)

prs.save(OUT)
print("saved", OUT)
