# AegisOne — Autonomous Marketing CFO

**DataQuest 3.0 · Next-generation autonomous D2C advertising intelligence & decision engine**

> Instead of telling a company *what happened*, our AI Marketing CFO decides **where the company's next ₹1 of advertising spend should go.**

Different companies get different decisions: the same campaign data is judged against each company's objectives, margins, inventory, CAC, ROAS and risk tolerance.

```
Synthetic / platform data → Ingestion & reconciliation → Unified business data → AI diagnosis
   → Business Policy Engine → Decision optimizer → What-if simulator → Recommendation / approval
   → Outcome feedback ↺
```

## Repository map

| Path | What it is |
| --- | --- |
| `docs/AegisOne_Autonomous_Marketing_CFO.pptx` | The 12-slide hackathon deck (built from live engine numbers by `docs/build_deck.py`) |
| `backend/app/schema.sql` | SQLite schema (15 tables) |
| `backend/app/datagen.py` | Deterministic synthetic data generator (4 companies · 47 campaigns · 60 days) |
| `backend/app/metrics.py` | Ingestion, cross-platform reconciliation, elasticity fit, unified metrics |
| `backend/app/diagnosis.py` | Anomaly detection + root-cause hypotheses with confidence |
| `backend/app/policy.py` | Business Policy Engine (weights + guardrails) |
| `backend/app/optimizer.py` | Policy-weighted incremental-profit budget optimizer |
| `backend/app/service.py` | Plans, recommendations, what-if, cross-policy comparison |
| `backend/app/feedback.py` | Approve → simulated outcome → error → updated confidence |
| `backend/app/demo.py` | The deterministic judge demo |
| `backend/app/main.py` | FastAPI app |
| `backend/tests/` | pytest suite (37 tests) |
| `frontend/` | React + Vite + Recharts dashboard |

## Setup

Requirements: Python 3.11+ and Node 20+. No paid APIs, no ad-platform credentials.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m app.datagen                           # writes data/aegis.db + data/csv/*.csv
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                                                   # http://localhost:5173 (proxies /api → :8000)
```

The API auto-generates the database on first start if `data/aegis.db` is missing. `POST /api/reset` (or the **Reset demo** button) regenerates it and clears learned feedback.

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

### Frontend tests (Playwright + axe)

Uses the real backend and dev server (resets the demo DB first). Needs Google Chrome installed.

```bash
cd frontend
npx playwright test        # brand switching, next-₹1, ROAS trap, why-not, what-if, approve→history, a11y, overflow
```

### Rebuild the deck

```bash
backend/.venv/Scripts/python docs/build_deck.py     # requires python-pptx (in requirements.txt)
```

## The demo (open **Guided Demo** in the app)

1. **Data** — 720 daily ad rows for Premium Fashion are reconciled against the sales ledger: platforms over-claim orders by ~21%, so reported ROAS 5.50 → reconciled 4.56.
2. **Diagnosis** — *Linen Blazer · Meta · Lookalike 1%* ROAS falls 6.0 → 3.0. CTR −48%, CPC +111%, conversion flat, frequency +155%, 49-day-old creative → **creative fatigue, 95% confidence**.
3. **Decision** — move **₹12,000/day** to *Silk Scarf · Google* (marginal ROAS 5.7 vs 2.1, 67% margin, healthy stock): **+₹28,513/day**, with the *why*, policy drivers and guardrail checks.
4. **What-if** — supplier delay: only 200 scarves on hand. The recommendation **changes** (₹6,000 goes to Selvedge Denim · Google instead) because scaling the scarf would stock out.
5. **Feedback** — approve; the system simulates the outcome (≈ +₹24,952/day), stores prediction → action → actual → error (−12.5%) → updated confidence, and recalibrates future "move budget" calls.

Then switch company in the header (or open **Company Profile**) to see four policies decide the same campaigns differently — e.g. Consumer Electronics' 5.0× ROAS bar pauses *Selvedge Denim · Meta* outright while the Startup keeps funding prospecting.

## How it works

**Reconciliation.** Platforms over-count orders. Per SKU we regress real units sold on platform-reported orders (`units = organic + β · platform_orders`, scikit-learn). β (clipped 0.55–1.0) is the haircut applied to every platform number; the intercept is the organic baseline. All ROAS/CAC/profit figures use reconciled orders.

**Metrics.** ROAS, CAC (cost per acquired order), CTR, CPC, conversion rate, profit (reconciled revenue × unit margin − spend), margin, inventory days, stockout risk (`clip((1.5·lead − days_cover)/lead, 0, 1)`), opportunity score (policy-adjusted marginal return, 0–100).

**Diagnosis.** Recent 5 days vs a clean 25-day baseline; robust z-score (median/MAD) plus a minimum relative change flags ROAS drops, CPC spikes, CTR/conversion drops. Each hypothesis (creative fatigue, auction pressure, competitor price pressure, post-click issue) is scored from independent signals — CTR, CPC, CVR, frequency, creative age, competitor price ratio, platform peers. SKU-level checks cover margin squeeze, stockout, overstock/spoilage and competitor price pressure. Every anomaly returns *what happened → probable cause → confidence → recommended action* plus rival hypotheses.

**Policy.** Six weights (profitability, growth, revenue, inventory, CAC, risk; sum to 1) and four guardrails (min margin, max CAC, min ROAS, inventory target days) per company.

**Optimizer.** Per campaign, orders follow a fitted spend elasticity `orders(b) = orders₀·(b/b₀)^e` (log-log regression shrunk to a platform prior → diminishing returns). Utility = `Σ 6·wᵢ·termᵢ` over profit, revenue, new-customer LTV, inventory pressure, CAC/ROAS penalties and risk. Utilities are concave, so a greedy loop that moves one ₹-step from the lowest to the highest marginal utility is optimal; guardrails gate every increase, stock caps are shared per SKU, and caps limit per-source cuts (30%) and total turnover (15%). Outputs: increase / decrease / move between platforms / promote another SKU / change audience allocation / pause / replace creative.

**What-if.** Total budget, per-SKU inventory, price, unit cost/margin, company priorities and guardrails can all be overridden; the full pipeline re-solves and returns a baseline-vs-scenario diff.

**Feedback.** Approval stores the recommendation, simulates a deterministic outcome, records error and confidence update (`conf' = conf + 0.3·(accuracy − conf)`), and updates a per-type calibration that scales the confidence of future recommendations.

## API

`GET /api/companies · /overview · /plan · /diagnosis · /campaign-series · /policy-compare · /history · /demo` and `POST /api/whatif · /recommendations/decide · /reset`. Interactive docs at `http://localhost:8000/docs`.

## Notes & honesty

* All data is synthetic and generated with a fixed seed; the generator knows ground truth, the engine never reads it. Dollar impacts are **model estimates on synthetic data**, not measured results.
* Outcomes in the feedback loop are simulated (deterministic hash-based noise around a mildly optimistic model), standing in for real post-decision measurement.
* The deck was built from the problem framing in the brief; no template or problem-statement file was present in the repository, so slides use a fresh dark theme.
