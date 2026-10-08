# AegisOne — Autonomous Marketing CFO

**DataQuest 3.0 · Next-generation autonomous D2C advertising intelligence & decision engine**

> Instead of telling a company *what happened*, our AI Marketing CFO decides **where the company's next ₹1 of advertising spend should go.**

Five demo brands — **Nike, Samsung, Lenovo, Louis Vuitton, Supreme** — are judged against different demo business policies (objectives, margins, inventory, CAC, ROAS, risk tolerance). Switching brand changes products, prices, campaigns, policy, ML signal, portfolio ranking and the next-₹1 decision.

## Architecture

```
PUBLIC DATA → DATA INGESTION / NORMALIZATION → ML PREDICTION → BUSINESS POLICY ENGINE
  → FINANCIAL GUARDRAILS → PRODUCT × CAMPAIGN PORTFOLIO OPTIMIZATION → NEXT ₹1 DECISION
  → SIMULATION (what-if) → HUMAN APPROVAL → FEEDBACK / LEARNING ↺
```

**ML predicts; the CFO layer decides.**

* The model predicts an order/conversion signal (approved purchases per click) per campaign. It does **not** allocate budget.
* Its output is a **bounded input**: a multiplier on a campaign's expected orders, 35% weight of the model's relative signal, clipped to 0.85–1.15×.
* The **deterministic CFO engine** (policy weights, guardrails, concave-utility optimizer) is the final decision authority and is unchanged by the ML layer.
* Margin, inventory, CAC, ROAS, risk, policy and budget constraints can **override** the raw model signal: a gated campaign stays gated whatever the model says (covered by `test_ml_cannot_override_guardrails`).
* The system optimises **incremental contribution profit per ₹1**, not raw ROAS (see the *ROAS trap* panel).

## Repository map

| Path | What it is |
| --- | --- |
| `docs/AegisOne_Autonomous_Marketing_CFO.pptx` | The 13-slide deck, rebuilt from live engine output, model card and source metadata by `docs/build_deck.py` |
| `backend/app/schema.sql` | SQLite schema (15 tables) |
| `backend/app/ingest.py` | Reproducible public-data ingestion (`python -m app.ingest`): `data/raw/` → `data/processed/` + `sources.json` provenance |
| `backend/app/brands.py` | Brand data layer: Nike, Samsung, Lenovo, Louis Vuitton, Supreme (public catalog + demo policy/assumptions) |
| `backend/app/ml.py` | Conversion-propensity model (train / card / predict / bounded engine hook) |
| `backend/app/datagen.py` | Deterministic simulator (5 brands · 60 campaigns · 60 days) of marketing performance |
| `backend/app/metrics.py` | Ingestion, cross-platform reconciliation, elasticity fit, unified metrics |
| `backend/app/diagnosis.py` | Anomaly detection + root-cause hypotheses with confidence |
| `backend/app/policy.py` | Business Policy Engine (weights + guardrails) |
| `backend/app/optimizer.py` | Policy-weighted incremental-profit budget optimizer |
| `backend/app/service.py` | Plans, recommendations, what-if, cross-policy comparison |
| `backend/app/feedback.py` | Approve → simulated outcome → error → updated confidence |
| `backend/app/demo.py` | The deterministic judge demo |
| `backend/app/main.py` | FastAPI app |
| `backend/tests/` | pytest suite (69 tests: engine, API, data provenance, model, ML→optimizer) |
| `frontend/` | React + Vite + Recharts dashboard |

## Setup

Requirements: Python 3.11+ and Node 20+. No paid APIs, no ad-platform credentials.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt  # macOS/Linux: .venv/bin/python  (runtime-only deps: requirements.txt)
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

Starts its **own** isolated stack (backend :8101 with `data/e2e.db`, Vite :5183) and never reuses a process already on those ports, so it cannot test a stale backend; `e2e/global-setup.js` verifies the backend is healthy and is the current five-brand build before any browser test runs. Needs Google Chrome installed.

```bash
cd frontend
npx playwright test        # brand switching, next-₹1, ROAS trap, why-not, what-if, approve→history, ML Lab, Data Sources, a11y, overflow, 1440/820/390 responsive sweep
```

### Rebuild the deck

```bash
backend/.venv/Scripts/python docs/build_deck.py     # requires python-pptx (in backend/requirements-dev.txt)
```

## Data provenance (read this first)

No brand ad-account data is used or claimed. Four classes are kept apart in the code and the UI:

| Class | What | Source |
| --- | --- | --- |
| **Public data** | Product names, categories, INR prices, popularity signal | Nike: Kaggle *Adidas vs Nike* (CC0) · Samsung: Kaggle *Flipkart Mobile* (CC0) · Lenovo: Kaggle *Flipkart Laptops <₹75k* (CC0) · Louis Vuitton: Data Boutique FR price list (License: Unknown) · Supreme: Kaggle *Sneakers & Streetwear Sales 2022* (Apache-2.0; only 32 hoodie rows, other Supreme SKUs are **labelled demo SKUs**) |
| **Demo policy** | Weights, guardrails, unit-cost ratios, stock cover, lead times, scripted anomalies | Assumptions in `brands.py`; not the companies' real strategy or books |
| **Model prediction** | Approved purchases per click | Trained on the public Kaggle *Sales Conversion Optimization* Facebook-ad dataset (1,143 ads, anonymised, licence "other") |
| **Simulated** | Spend, impressions, clicks, orders, ROAS, CAC | *Simulated marketing performance derived from public product/sales signals* |

```bash
cd backend
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m app.ingest          # downloads data/raw/*, writes data/processed/* + sources.json  (--refresh to re-download)
.venv/Scripts/python -m app.ml              # trains the model, writes data/models/{conversion_model.joblib,model_card.json}
.venv/Scripts/python -m app.datagen         # simulates marketing performance and rebuilds data/aegis.db
```

`data/raw/` is git-ignored (re-downloaded on demand); `data/processed/` and `data/models/` are small and committed.

**ML layer.** A Poisson gradient-boosted model (selected over a Poisson GLM by 5-fold CV deviance) predicts approved purchases per click from four scale-free funnel features (log CTR, CPC and CPM indices, impression index). The signal is modest (see the **ML Lab** page for the real metrics and an honest reading), so the engine takes only 35% of the relative prediction, clipped to 0.85–1.15×, as a multiplier on a campaign's expected orders. Policy, guardrails and the optimizer are unchanged and remain the source of truth: **ML predicts, the CFO layer decides.**

**Product imagery (Budget Optimizer).** The product-art panel shows photographs supplied locally and stored in `frontend/public/products/<brand>/` (Nike 5, Samsung 4, Lenovo 3, Louis Vuitton 4, Supreme 4). They are brand-owned images used only as visual context in the demo: they are not part of any dataset above, are not matched to catalog SKUs, and imply no affiliation or endorsement. Confirm you have the right to use and redistribute them before publishing the repository or deployment. The gallery is strictly brand-scoped (manifest: `frontend/src/productGallery.js`), rotates in a fixed order, and makes no external image requests.

## The demo (open **Guided Demo** in the app)

The numbers below are computed live by the engine for the default brand (Nike); nothing is hard-coded. Pick any of the five brands in the top-left switcher to see a different context and decision.

1. **Data** — daily ad rows are reconciled against the sales ledger: platforms over-claim orders, so reported ROAS drops to a reconciled ROAS.
2. **Diagnosis** — a Meta lookalike campaign loses half its CTR while frequency climbs and its creative is ~7 weeks old → **creative fatigue**, with confidence and rival hypotheses.
3. **Decision** — move budget to the product × campaign × platform with the best policy-weighted marginal profit per ₹1, with the *why*, the ROAS trap, why the runner-up lost, policy drivers and guardrail checks.
4. **What-if** — a supplier delay leaves the winning product short of stock. The next-₹1 winner **changes** because scaling it would stock out.
5. **Feedback** — approve; the system simulates the outcome stores prediction → action → actual → error → updated confidence, and recalibrates future "move budget" calls.

Then open **ML Lab** (training data, features, validation, prediction trace) and **Data Sources**, and switch brand (or open **Company Profile**) to see five demo policies decide the same kinds of campaigns differently.

## Production Deployment

**Architecture (what is hosted where)**

```
USER (browser)
 ↓  HTTPS
VERCEL — static React/Vite frontend            (frontend/, built to frontend/dist)
 ↓  HTTPS, CORS-restricted, VITE_API_BASE_URL
DOCKER HOST — FastAPI backend                  (backend/Dockerfile: Render, Railway, Fly.io, Cloud Run, a VM, ...)
 ↓
DATA + ML — baked SQLite demo DB, data/processed CSVs, data/models/*.joblib
 ↓
DETERMINISTIC CFO DECISION ENGINE              (policy → guardrails → optimizer → next ₹1)
```

The backend is deliberately **not** run as Vercel serverless functions: it needs scikit-learn/pandas (a large Python bundle), a
SQLite file that the approve → feedback loop writes to, and a loaded model. A stateless function filesystem would silently drop
those writes and make cold starts slow, so the API stays a normal long-running service. The frontend is a static bundle and fits
Vercel as-is. Nothing here has been deployed from this repository yet; the steps below are the exact manual path.

**1. Backend (any Docker host)**

```bash
docker build -f backend/Dockerfile -t aegisone-api .      # run from the repository root
docker run -p 8000:8000 -e AEGIS_CORS_ORIGINS=https://<your-frontend>.vercel.app aegisone-api
curl http://localhost:8000/api/health                      # {"status":"ok"}
```

The image installs `backend/requirements.txt`, copies `backend/app`, `data/processed` and `data/models`, and **bakes the
deterministic demo database** (`python -m app.datagen`) so every cold start is identical. On a Docker host set the health check
to `/api/health` and the start command is already in the image (`uvicorn … --port ${PORT:-8000}`). The Dockerfile has not been
built in this repository's development environment (no Docker available); the same install and start sequence was verified in a
clean virtual environment (see QA below).

**2. Frontend (Vercel)**

* Import the repository, set **Root Directory = `frontend`**. Vercel detects Vite: build `npm run build`, output `dist`. No `vercel.json` is needed (the app has no URL routes; navigation is in-app state, so there is nothing to rewrite).
* Add the environment variable **`VITE_API_BASE_URL`** = the backend's public `https://` origin (no trailing slash) for **Production** and **Preview** (and optionally Development).
* Redeploy after changing it: Vite inlines it at build time.

**3. Environment variables (all non-secret)**

| Variable | Where | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Vercel (build time, **public**) | Backend origin. Unset in development → Vite proxies `/api` to `127.0.0.1:8000`. |
| `AEGIS_CORS_ORIGINS` | Backend host | Comma-separated frontend origins allowed by CORS. Required in production. No wildcard is used. |
| `AEGIS_DB` | Backend host (optional) | SQLite path. Point at a persistent disk to keep approvals across restarts. |
| `AEGIS_ENABLE_RESET` | Backend host (optional) | `0` disables `POST /api/reset` (the demo's Reset button). Default `1`. |
| `PORT` | Backend host | Provided by most hosts; defaults to 8000. |

There are **no server secrets** in this application (no API keys, tokens or credentials). Copy `frontend/.env.example` and
`backend/.env.example` as references; real `.env*` files are git-ignored. Never put secrets in `VITE_*` variables: they are
bundled into public JavaScript.

**4. Database and data assumptions**

* SQLite holds the deterministic **demo** data (simulated marketing performance on public product data) plus the decisions you approve. It is rebuilt identically by `python -m app.datagen`; the image ships it pre-built.
* Approvals/feedback are written to that file. On a host **without** a persistent disk they are lost on redeploy or restart, and the demo returns to its seeded state, which is the intended judging behaviour. This is not a production multi-user database; moving to Postgres is out of scope and not implied.
* One API process is assumed (SQLite writes + in-process caches). Do not scale horizontally.
* `POST /api/reset` regenerates the DB for everyone. Set `AEGIS_ENABLE_RESET=0` on a public deployment you do not want visitors to reset.

**5. ML model and data requirements**

* Shipped in git and copied into the image: `data/processed/*` (catalogs, ad-conversion training data, `sources.json`) and `data/models/{conversion_model.joblib,model_card.json}`. Raw datasets (`data/raw/`) are git-ignored and **not needed** at runtime.
* The model is **loaded at startup** (no per-request training). If the artifact cannot be unpickled (different scikit-learn), the API retrains it deterministically at startup (a few seconds). `backend/requirements.txt` pins the versions the artifact was built with.
* Measured in a clean virtual environment (Python 3.14, runtime requirements only): datagen 4 s; API ready ≈ 10 s after process start; typical API responses 0.2 s warm, up to ≈ 1 s for plan/ML-trace endpoints.

**6. Local development**

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000     # API
cd frontend && npm run dev                                                    # UI on :5173, proxies /api → :8000
```

**7. Production-style verification**

```bash
cd frontend && npm run test:prod
```

builds the frontend with `VITE_API_BASE_URL` pointing at a **separate** backend origin, starts that backend from a missing database
with CORS restricted to the preview origin, and checks: every page and all five brands, approve → history, the ML Lab trace, CORS
(allowed origin accepted, other origins refused), a friendly error + working "Try again" when the API is unreachable, no leaked
server internals in error messages, and the static-host fallback.

## How it works

**Reconciliation.** Platforms over-count orders. Per SKU we regress real units sold on platform-reported orders (`units = organic + β · platform_orders`, scikit-learn). β (clipped 0.55–1.0) is the haircut applied to every platform number; the intercept is the organic baseline. All ROAS/CAC/profit figures use reconciled orders.

**Metrics.** ROAS, CAC (cost per acquired order), CTR, CPC, conversion rate, profit (reconciled revenue × unit margin − spend), margin, inventory days, stockout risk (`clip((1.5·lead − days_cover)/lead, 0, 1)`), opportunity score (policy-adjusted marginal return, 0–100).

**Diagnosis.** Recent 5 days vs a clean 25-day baseline; robust z-score (median/MAD) plus a minimum relative change flags ROAS drops, CPC spikes, CTR/conversion drops. Each hypothesis (creative fatigue, auction pressure, competitor price pressure, post-click issue) is scored from independent signals — CTR, CPC, CVR, frequency, creative age, competitor price ratio, platform peers. SKU-level checks cover margin squeeze, stockout, overstock/spoilage and competitor price pressure. Every anomaly returns *what happened → probable cause → confidence → recommended action* plus rival hypotheses.

**Policy.** Six weights (profitability, growth, revenue, inventory, CAC, risk; sum to 1) and four guardrails (min margin, max CAC, min ROAS, inventory target days) per company.

**Optimizer.** Per campaign, orders follow a fitted spend elasticity `orders(b) = orders₀·(b/b₀)^e` (log-log regression shrunk to a platform prior → diminishing returns). Utility = `Σ 6·wᵢ·termᵢ` over profit, revenue, new-customer LTV, inventory pressure, CAC/ROAS penalties and risk. Utilities are concave, so a greedy loop that moves one ₹-step from the lowest to the highest marginal utility is optimal; guardrails gate every increase, stock caps are shared per SKU, and caps limit per-source cuts (30%) and total turnover (15%). Outputs: increase / decrease / move between platforms / promote another SKU / change audience allocation / pause / replace creative.

**What-if.** Total budget, per-SKU inventory, price, unit cost/margin, company priorities and guardrails can all be overridden; the full pipeline re-solves and returns a baseline-vs-scenario diff.

**Feedback.** Approval stores the recommendation, simulates a deterministic outcome, records error and confidence update (`conf' = conf + 0.3·(accuracy − conf)`), and updates a per-type calibration that scales the confidence of future recommendations.

## API

`GET /api/brands · /data-sources · /ml/card · /ml/trace · /companies · /overview · /plan · /diagnosis · /campaign-series · /policy-compare · /history · /demo` and `POST /api/whatif · /recommendations/decide · /reset`. Interactive docs at `http://localhost:8000/docs`.

## Notes & honesty

* Marketing performance is simulated with a fixed seed; the generator knows ground truth, the engine never reads it. Rupee impacts are **model estimates on simulated data**, not measured results and not any brand's results.
* The deck was regenerated for the five-brand build (`python docs/build_deck.py`); its slides were not visually proofread in a slide renderer, so check layout before presenting.
* Outcomes in the feedback loop are simulated (deterministic hash-based noise around a mildly optimistic model), standing in for real post-decision measurement.
* The deck was built from the problem framing in the brief; no template or problem-statement file was present in the repository, so slides use a fresh dark theme.
