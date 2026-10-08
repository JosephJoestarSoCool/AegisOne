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
| `backend/app/ingest.py` | Reproducible public-data ingestion (`python -m app.ingest`): `backend/data/raw/` → `backend/data/processed/` + `sources.json` provenance |
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
| `backend/tests/` | pytest suite (74 tests: engine, API, data provenance, model, ML→optimizer, deployment readiness) |
| `frontend/` | React + Vite + Recharts dashboard |

## Setup

Requirements: Python 3.11+ and Node 20+. No paid APIs, no ad-platform credentials.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt  # macOS/Linux: .venv/bin/python  (runtime-only deps: requirements.txt)
.venv/Scripts/python -m app.datagen                           # writes backend/data/aegis.db + backend/data/csv/*.csv
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                                                   # http://localhost:5173 (proxies /api → :8000)
```

The API auto-generates the database on first start if `backend/data/aegis.db` is missing. `POST /api/reset` (or the **Reset demo** button) regenerates it and clears learned feedback.

### Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

### Frontend tests (Playwright + axe)

Starts its **own** isolated stack (backend :8101 with `backend/data/e2e.db`, Vite :5183) and never reuses a process already on those ports, so it cannot test a stale backend; `e2e/global-setup.js` verifies the backend is healthy and is the current five-brand build before any browser test runs. Needs Google Chrome installed.

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
.venv/Scripts/python -m app.ingest          # downloads backend/data/raw/*, writes backend/data/processed/* + sources.json  (--refresh to re-download)
.venv/Scripts/python -m app.ml              # trains the model, writes backend/data/models/{conversion_model.joblib,model_card.json}
.venv/Scripts/python -m app.datagen         # simulates marketing performance and rebuilds backend/data/aegis.db
```

`backend/data/raw/` is git-ignored (re-downloaded on demand); `backend/data/processed/` and `backend/data/models/` are small and committed.

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

Two separate Vercel projects from this one GitHub repository (`JosephJoestarSoCool/AegisOne`), plus a Docker alternative for the API.

```
USER (browser)
 ↓  HTTPS
VERCEL PROJECT 1 — static React/Vite frontend          Root Directory: frontend
 ↓  HTTPS, CORS-restricted, VITE_API_URL
VERCEL PROJECT 2 — FastAPI backend (Python function)   Root Directory: backend
 ↓
DATA + ML — backend/data/processed, backend/data/models (bundled, read-only) + SQLite in the function's temp dir
 ↓
DETERMINISTIC CFO DECISION ENGINE                      (policy → guardrails → optimizer → next ₹1)
```

### 1. Backend project (FastAPI on Vercel)

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Framework Preset | FastAPI (auto-detected) |
| Entrypoint | `app.main:app`, declared in `backend/pyproject.toml` (`[tool.vercel] entrypoint`) |
| Python | 3.14 (`backend/.python-version`; Vercel supports 3.12 / 3.13 / 3.14) |
| Dependencies | `backend/pyproject.toml` (identical to `requirements.txt`; a test enforces it) |
| Build / Install / Output | leave defaults |
| Function config | `backend/vercel.json`: `maxDuration` 60, tests/raw data/Dockerfile excluded from the bundle |

Everything the API reads at runtime is inside `backend/`: `backend/data/processed` (public catalogs, training data, `sources.json`) and `backend/data/models` (trained model + card). `backend/data/raw` is git-ignored and not needed. All paths are relative to the package, never absolute machine paths.

**Environment variables (Vercel → Project → Settings → Environment Variables):**

| Variable | Required | Meaning |
| --- | --- | --- |
| `AEGIS_CORS_ORIGINS` | **yes** | Comma-separated frontend origins allowed by CORS, e.g. `https://aegisone.vercel.app`. Replaces the dev default; `http://localhost:5173` is only allowed when this is unset. No wildcard. |
| `AEGIS_CORS_ORIGIN_REGEX` | optional | Regex for Vercel preview URLs of the frontend project, e.g. `https://aegisone-.*\.vercel\.app` |
| `AEGIS_ENABLE_RESET` | optional | `0` disables `POST /api/reset` (the demo's Reset button). Default `1`. |

There are no secrets. `VERCEL=1` is set by the platform and switches the SQLite file to the temp directory.

Check after deploying: `https://<api-project>.vercel.app/api/health` → `{"status":"ok"}` and `/api/companies` lists 5 brands.

### 2. Frontend project (Vite on Vercel)

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| `frontend/vercel.json` | one rewrite `/(.*)` → `/index.html` so `/optimizer`, `/simulator`, `/history`, `/profile`, `/ml-lab`, `/data-sources`, `/guided-demo`, `/command-center`, `/diagnosis` open (and reload) directly. Static files (`/assets`, `/products`) are served first. |

| Variable | Scope | Meaning |
| --- | --- | --- |
| `VITE_API_URL` | Production **and** Preview | The deployed API origin, e.g. `https://aegisone-api.vercel.app` (no trailing slash). Public value, inlined at build time: **redeploy after changing it**. |

URL paths map to the in-app pages (`frontend/src/App.jsx`), so the address bar follows navigation and Back/Forward work; no router library was added. If `VITE_API_URL` is missing, the app shows its "couldn't reach the API" state and never invents data. A render crash shows a recoverable message (error boundary) instead of a blank page. Product images live in `frontend/public/products/` and are served by the frontend project.

### 3. SQLite on serverless: a demo limitation

* The deployment is read-only except the temp directory, so on Vercel the SQLite file lives at `<tmp>/aegis.db` and is **rebuilt deterministically at every cold start** (~4 s, in the app's startup).
* **Approvals/feedback are not durable.** Each function instance has its own database, and an instance can be recycled at any time, so history can differ between requests or reset. This is acceptable for a deterministic judging demo; it is **not** a production data store.
* For real persistence, move the decision/feedback tables to **managed Postgres** (or another persistent database) and keep the generated demo data read-only. That migration is intentionally out of scope here.
* The trained model is loaded from `backend/data/models`; if that artifact can't be loaded (different scikit-learn) the API retrains it deterministically in memory. `pyproject.toml`/`requirements.txt` pin the versions the artifact was built with.
* Bundle size: pandas + numpy + scikit-learn + SciPy are the bulk of the Python bundle (limit 500 MB uncompressed); runtime dependencies only (no pytest, pptx, pyarrow).

### 4. Docker alternative (any container host)

```bash
docker build -t aegisone-api backend                 # build context is backend/; bakes the demo DB into the image
docker run -p 8000:8000 -e AEGIS_CORS_ORIGINS=https://<frontend-origin> aegisone-api
```

The Dockerfile has not been built in this repository's development environment (no Docker available). On a host with a persistent disk, set `AEGIS_DB` to a path on it to keep approvals across restarts.

### 5. Local development

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000        # API on http://localhost:8000
cd frontend && cp .env.example .env.local   # optional: VITE_API_URL=http://localhost:8000 (CORS allows http://localhost:5173)
cd frontend && npm run dev                  # UI on http://localhost:5173 (without VITE_API_URL it proxies /api to :8000)
```

### 6. Verification that exists in the repo

* `backend/tests/test_deploy.py`: serverless start writes only to the temp dir (nothing under `backend/data`), model-artifact fallback, environment-driven CORS (no wildcard, dev default still works), `pyproject.toml` ⇄ `requirements.txt` parity, no machine-specific paths.
* `e2e/app.spec.js`: direct URLs and reloads for every page, Back/Forward, unknown paths fall back to the app.
* `cd frontend && npm run test:prod`: builds the frontend with `VITE_API_URL` pointing at a **separate** backend origin, starts that backend from a missing database with restricted CORS, and checks every page and brand, approve → history, CORS, outage → friendly error → "Try again", no leaked server internals, deep links, and that the built bundle contains no `localhost:8000` URL.

Not verified here: an actual Vercel deployment (no Vercel account or CLI in this environment).

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
