-- AegisOne / Autonomous Marketing CFO — SQLite schema
-- Relationship spine:
--   company -> campaigns -> SKU -> platform / audience / creative -> daily ad_metrics
--   SKU -> sales + pricing (margin) + inventory + competitor_prices

PRAGMA foreign_keys = ON;

CREATE TABLE companies (
    company_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    vertical     TEXT NOT NULL,
    description  TEXT
);

-- Business Policy: objective weights (sum to 1) + hard guardrails
CREATE TABLE company_profiles (
    company_id            TEXT PRIMARY KEY REFERENCES companies(company_id),
    w_profitability       REAL NOT NULL,
    w_growth              REAL NOT NULL,
    w_revenue             REAL NOT NULL,
    w_inventory           REAL NOT NULL,
    w_cac                 REAL NOT NULL,
    w_risk                REAL NOT NULL,
    min_margin            REAL NOT NULL,   -- fraction, e.g. 0.30
    max_cac               REAL NOT NULL,   -- INR per acquired order
    min_roas              REAL NOT NULL,
    inventory_target_days REAL NOT NULL,
    ltv_per_customer      REAL NOT NULL,   -- INR expected future profit per new customer
    price_elasticity      REAL NOT NULL,   -- demand elasticity to price
    risk_label            TEXT NOT NULL
);

CREATE TABLE platforms (
    platform_id      TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    elasticity_prior REAL NOT NULL          -- prior for spend -> revenue elasticity
);

CREATE TABLE audiences (
    audience_id        TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    audience_type      TEXT NOT NULL,       -- prospecting | retargeting
    new_customer_share REAL NOT NULL
);

CREATE TABLE products (
    sku_id          TEXT PRIMARY KEY,
    company_id      TEXT NOT NULL REFERENCES companies(company_id),
    name            TEXT NOT NULL,
    category        TEXT NOT NULL,
    shelf_life_days INTEGER NOT NULL,
    organic_units_per_day REAL NOT NULL     -- generator ground truth is NOT used by models
);

CREATE TABLE pricing (
    sku_id       TEXT NOT NULL REFERENCES products(sku_id),
    date         TEXT NOT NULL,
    list_price   REAL NOT NULL,
    discount_pct REAL NOT NULL,
    unit_cost    REAL NOT NULL,             -- landed + fulfilment cost per unit
    PRIMARY KEY (sku_id, date)
);

CREATE TABLE competitor_prices (
    sku_id           TEXT NOT NULL REFERENCES products(sku_id),
    date             TEXT NOT NULL,
    competitor_price REAL NOT NULL,
    PRIMARY KEY (sku_id, date)
);

CREATE TABLE inventory (
    sku_id         TEXT PRIMARY KEY REFERENCES products(sku_id),
    on_hand_units  REAL NOT NULL,
    lead_time_days REAL NOT NULL,
    as_of          TEXT NOT NULL
);

CREATE TABLE sales (
    sku_id  TEXT NOT NULL REFERENCES products(sku_id),
    date    TEXT NOT NULL,
    units   INTEGER NOT NULL,               -- all channels (ads + organic)
    revenue REAL NOT NULL,
    cogs    REAL NOT NULL,
    PRIMARY KEY (sku_id, date)
);

CREATE TABLE creatives (
    creative_id TEXT PRIMARY KEY,
    sku_id      TEXT NOT NULL REFERENCES products(sku_id),
    name        TEXT NOT NULL,
    format      TEXT NOT NULL,
    launch_date TEXT NOT NULL
);

CREATE TABLE campaigns (
    campaign_id  TEXT PRIMARY KEY,
    company_id   TEXT NOT NULL REFERENCES companies(company_id),
    sku_id       TEXT NOT NULL REFERENCES products(sku_id),
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    audience_id  TEXT NOT NULL REFERENCES audiences(audience_id),
    creative_id  TEXT NOT NULL REFERENCES creatives(creative_id),
    name         TEXT NOT NULL,
    daily_budget REAL NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active'
);

-- Platform-reported numbers (orders/revenue are over-counted vs. real sales:
-- the reconciliation layer corrects them using the sales table).
CREATE TABLE ad_metrics (
    campaign_id      TEXT NOT NULL REFERENCES campaigns(campaign_id),
    date             TEXT NOT NULL,
    impressions      INTEGER NOT NULL,
    reach            INTEGER NOT NULL,
    clicks           INTEGER NOT NULL,
    spend            REAL NOT NULL,
    platform_orders  INTEGER NOT NULL,
    platform_revenue REAL NOT NULL,
    PRIMARY KEY (campaign_id, date)
);

CREATE TABLE recommendations (
    rec_id             TEXT PRIMARY KEY,
    company_id         TEXT NOT NULL REFERENCES companies(company_id),
    policy_id          TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    rec_type           TEXT NOT NULL,
    title              TEXT NOT NULL,
    source_campaign_id TEXT,
    target_campaign_id TEXT,
    amount             REAL,
    expected_profit    REAL NOT NULL,       -- INR / day
    confidence         REAL NOT NULL,
    why                TEXT NOT NULL,
    payload            TEXT NOT NULL,       -- full JSON of the recommendation
    status             TEXT NOT NULL        -- pending | approved | rejected
);

-- prediction -> action -> actual outcome -> error -> updated confidence
CREATE TABLE feedback (
    rec_id            TEXT PRIMARY KEY REFERENCES recommendations(rec_id),
    company_id        TEXT NOT NULL,
    predicted_profit  REAL NOT NULL,
    action            TEXT NOT NULL,
    actual_profit     REAL NOT NULL,
    error             REAL NOT NULL,        -- actual - predicted
    error_pct         REAL NOT NULL,
    confidence_before REAL NOT NULL,
    confidence_after  REAL NOT NULL,
    recorded_at       TEXT NOT NULL
);

CREATE TABLE calibration (
    company_id TEXT NOT NULL,
    rec_type   TEXT NOT NULL,
    accuracy   REAL NOT NULL,               -- EMA of 1 - |error_pct|
    n          INTEGER NOT NULL,
    PRIMARY KEY (company_id, rec_type)
);

CREATE INDEX idx_ad_metrics_date ON ad_metrics(date);
CREATE INDEX idx_campaigns_company ON campaigns(company_id);
CREATE INDEX idx_sales_sku ON sales(sku_id);
