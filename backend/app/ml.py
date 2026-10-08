"""Conversion-propensity model (ML layer). It PREDICTS; the deterministic CFO engine DECIDES.

Run:  python -m app.ml            (from backend/)  -> trains, writes backend/data/models/{conversion_model.joblib,model_card.json}

Training data : a real public Facebook-ad dataset (backend/data/processed/ad_conversions.csv, 1,143 ads).
Target        : approved (purchase) conversions per click, a rate, fitted with click weights.
Features      : scale-free funnel features available both in the training data and in the app's
                campaign state: log CTR, log CPC index, log CPM index, impression-volume index.
                (Indices are relative to the portfolio median, so USD training data transfers to any brand.)
Selection     : 3 candidate models compared by 5-fold CV weighted binomial deviance; best is refit on all data.
Use in engine : each campaign's predicted rate vs the brand's click-weighted mean becomes a bounded
                multiplier on the campaign's expected orders (ML_WEIGHT, clipped). The optimizer, policy
                and guardrails then run unchanged on the adjusted response curve.
"""
from __future__ import annotations

import json
from datetime import date

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import DATA_DIR

PROCESSED = DATA_DIR / "processed"
MODEL_DIR = DATA_DIR / "models"
MODEL_PATH = MODEL_DIR / "conversion_model.joblib"
CARD_PATH = MODEL_DIR / "model_card.json"
MODEL_VERSION = "v1.0"
ML_WEIGHT = 0.35            # how much of the model's relative signal enters the engine
ML_CLIP = (0.85, 1.15)      # hard bounds on the multiplier: the model can nudge, never dominate
FEATURES = ["log_ctr", "log_cpc_idx", "log_cpm_idx", "imp_idx"]

FEATURE_DOC = {
    "log_ctr": dict(label="Click-through rate (log)", what="Share of impressions that become clicks, on a log scale.",
                    why="A creative that attracts clicks is relevant to its audience; relevance travels with purchase intent.",
                    effect="Read from the trained model: see direction in the card."),
    "log_cpc_idx": dict(label="Cost per click vs portfolio median (log)", what="How expensive a click is relative to the median ad in the same portfolio.",
                        why="Expensive clicks come from competitive, high-intent auctions; very cheap clicks are often low-intent traffic.",
                        effect="Read from the trained model: see direction in the card."),
    "log_cpm_idx": dict(label="Cost per 1,000 impressions vs median (log)", what="Auction price of reach relative to the portfolio median.",
                        why="Signals audience scarcity/quality and platform competition.",
                        effect="Read from the trained model: see direction in the card."),
    "imp_idx": dict(label="Impression volume vs median", what="Delivery scale relative to the median ad.",
                    why="Heavily-delivered ads reach colder audiences; small ads are usually tightly targeted.",
                    effect="Read from the trained model: see direction in the card."),
}


def _dev(y, p, w) -> float:
    p = np.clip(p, 1e-4, 0.99)
    y = np.clip(y, 0, 1)
    return float(-np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p))) / np.sum(w))


def features_frame(ctr, cpc, cpm, imps) -> pd.DataFrame:
    """Build model features from raw funnel values (arrays). Indices use the median of the passed set."""
    ctr, cpc, cpm, imps = (np.asarray(x, float) for x in (ctr, cpc, cpm, imps))
    med = lambda a: float(np.median(a[a > 0])) if (a > 0).any() else 1.0   # noqa: E731
    return pd.DataFrame(dict(
        log_ctr=np.log(np.clip(ctr, 1e-6, None)),
        log_cpc_idx=np.log(np.clip(cpc / med(cpc), 1e-3, None)),
        log_cpm_idx=np.log(np.clip(cpm / med(cpm), 1e-3, None)),
        imp_idx=imps / med(imps)))


def training_frame() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "ad_conversions.csv")
    df = df[(df.Clicks > 0) & (df.Impressions > 0)].copy()
    X = features_frame(df.Clicks / df.Impressions, df.Spent / df.Clicks, df.Spent / df.Impressions * 1000, df.Impressions)
    X["rate"] = (df.Approved_Conversion / df.Clicks).to_numpy()
    X["clicks"] = df.Clicks.to_numpy()
    X["approved"] = df.Approved_Conversion.to_numpy()
    return X


def _candidates():
    return {
        "Poisson GLM (linear, interpretable)": lambda: make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.0)),
        "HistGradientBoosting (Poisson, depth 2)": lambda: HistGradientBoostingRegressor(
            loss="poisson", max_depth=2, max_iter=60, learning_rate=0.05, random_state=0),
    }


def _fit(make, X, y, w):
    m = make()
    if isinstance(m, HistGradientBoostingRegressor):
        m.fit(X, y, sample_weight=w)
    else:
        m.fit(X, y, poissonregressor__sample_weight=w)
    return m


def train() -> dict:
    df = training_frame()
    X, y, w = df[FEATURES], df.rate.to_numpy(), df.clicks.to_numpy()
    kf = KFold(5, shuffle=True, random_state=0)
    results, oof_best = {}, {}
    for name, make in _candidates().items():
        oof = np.zeros(len(df))
        for tr, te in kf.split(X):
            oof[te] = _fit(make, X.iloc[tr], y[tr], w[tr]).predict(X.iloc[te])
        results[name] = dict(cv_deviance=_dev(y, oof, w))
        oof_best[name] = oof
    base = float(np.full(len(df), (df.approved.sum() / df.clicks.sum())) @ np.ones(len(df)) / len(df))
    base_dev = _dev(y, np.full(len(df), base), w)
    for r in results.values():
        r["deviance_reduction_pct"] = round(100 * (base_dev - r["cv_deviance"]) / base_dev, 2)
    best = min(results, key=lambda k: results[k]["cv_deviance"])
    oof = oof_best[best]

    # out-of-fold permutation importance: deviance increase when a feature is shuffled in held-out data
    rng = np.random.default_rng(0)
    make = _candidates()[best]
    imp = {f: [] for f in FEATURES}
    direction = {}
    for tr, te in kf.split(X):
        m = _fit(make, X.iloc[tr], y[tr], w[tr])
        base_te = _dev(y[te], m.predict(X.iloc[te]), w[te])
        for f in FEATURES:
            for _ in range(5):
                Xp = X.iloc[te].copy()
                Xp[f] = rng.permutation(Xp[f].to_numpy())
                imp[f].append(_dev(y[te], m.predict(Xp), w[te]) - base_te)
    final = _fit(make, X, y, w)
    for f in FEATURES:                      # direction: predicted-rate change moving feature p25 -> p75
        lo, hi = X.copy(), X.copy()
        lo[f], hi[f] = X[f].quantile(0.25), X[f].quantile(0.75)
        direction[f] = float(np.average(final.predict(hi) - final.predict(lo), weights=w))
    tot = sum(max(np.mean(v), 0) for v in imp.values()) or 1.0
    features = []
    for f in FEATURES:
        v = max(float(np.mean(imp[f])), 0.0)
        d = direction[f]
        features.append(dict(
            feature=f, importance=round(v / tot, 4), raw_importance=round(v, 6), **{k: FEATURE_DOC[f][k] for k in ("label", "what", "why")},
            direction="raises" if d > 0 else "lowers", effect=(
                f"Moving from a low (25th pct) to a high (75th pct) value {'raises' if d > 0 else 'lowers'} the predicted conversion rate "
                f"by {abs(d) * 1000:.2f} approved purchases per 1,000 clicks, on average.")))
    features.sort(key=lambda r: -r["importance"])

    q = pd.qcut(pd.Series(oof).rank(method="first"), 4, labels=False)
    quart = [dict(quartile=int(i) + 1, predicted=float(np.average(oof[q == i], weights=w[q == i])),
                  actual=float(df.approved[q == i].sum() / df.clicks[q == i].sum()), n=int((q == i).sum())) for i in range(4)]
    spearman = float(pd.Series(oof).corr(pd.Series(y), method="spearman"))
    card = dict(
        name="Conversion Propensity Model", version=MODEL_VERSION, trained_on=date.today().isoformat(),
        task="Predict approved purchases per click from ad-funnel signals",
        target="approved_conversions / clicks (click-weighted)", model_type=best, candidates=results,
        n_records=int(len(df)), n_clicks=int(df.clicks.sum()), n_features=len(FEATURES), features=features,
        validation=dict(method="5-fold cross-validation, out-of-fold predictions", cv_deviance=round(results[best]["cv_deviance"], 5),
                        baseline_deviance=round(base_dev, 5), deviance_reduction_pct=results[best]["deviance_reduction_pct"],
                        spearman_rank_corr=round(spearman, 3),
                        calibration_ratio=round(float(np.average(oof, weights=w) / (df.approved.sum() / df.clicks.sum())), 3)),
        quartile_lift=quart,
        honest_reading=(f"Weak but measurable: out-of-fold deviance is {results[best]['deviance_reduction_pct']}% below a constant-rate baseline "
                        f"(rank correlation {spearman:.2f}). {features[0]['label']} carries {features[0]['importance'] * 100:.0f}% of the importance, "
                        "so most of the signal is one feature. Public data for some brands is thin. That is why the engine takes only "
                        f"{int(ML_WEIGHT * 100)}% of the relative signal, clipped to {ML_CLIP[0]}–{ML_CLIP[1]}×, and the deterministic CFO still decides."),
        engine_link=dict(weight=ML_WEIGHT, clip=list(ML_CLIP)),
        data_source="marketing")
    global _MODEL, _CARD
    _MODEL, _CARD = dict(model=final, features=FEATURES, version=MODEL_VERSION), card
    try:                                   # best effort: a read-only deployment keeps the fresh model in memory only
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(_MODEL, MODEL_PATH)
        CARD_PATH.write_text(json.dumps(card, indent=2), encoding="utf-8")
    except OSError:
        pass
    return card


_MODEL = None
_CARD = None


def load():
    global _MODEL
    if _MODEL is None:
        try:
            if not MODEL_PATH.exists() or not CARD_PATH.exists():
                raise FileNotFoundError(MODEL_PATH)
            _MODEL = joblib.load(MODEL_PATH)
        except Exception:    # missing artifact, or one pickled by another scikit-learn version: retrain deterministically
            train()          # (sets _MODEL / _CARD in memory even when the artifact cannot be written)
    return _MODEL


def card() -> dict:
    load()
    if _CARD is not None:
        return _CARD
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def predict_frame(X: pd.DataFrame) -> np.ndarray:
    return load()["model"].predict(X[FEATURES])


def annotate(states: list[dict], enabled: bool = True) -> list[dict]:
    """Attach ML predictions to campaign states and (if enabled) scale expected orders by the bounded ML multiplier."""
    live = [s for s in states if s["impressions"] > 0 and s["clicks"] > 0]
    if not live:
        return states
    X = features_frame([s["ctr"] for s in live], [s["cpc"] for s in live],
                       [s["spend"] / s["impressions"] * 1000 for s in live], [s["impressions"] for s in live])
    p = predict_frame(X)
    w = np.array([s["clicks"] for s in live])
    p_ref = float(np.average(p, weights=w))
    for s, pi, (_, row) in zip(live, p, X.iterrows()):
        lift = float(np.clip(1.0 + ML_WEIGHT * (pi / p_ref - 1.0), *ML_CLIP))
        s["ml"] = dict(conv_rate_per_click=float(pi), portfolio_ref=p_ref, relative=float(pi / p_ref), lift=lift,
                       applied=bool(enabled), features={k: float(row[k]) for k in FEATURES},
                       version=load()["version"])
        if enabled:
            s["orders0_pre_ml"] = s["orders0"]
            s["orders0"] = s["orders0"] * lift
    return states


if __name__ == "__main__":
    c = train()
    print(json.dumps({k: c[k] for k in ("model_type", "n_records", "validation", "quartile_lift")}, indent=2))
    for f in c["features"]:
        print(f"  {f['feature']:14s} {f['importance']:.2%} {f['direction']}")
