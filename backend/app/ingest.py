"""Reproducible public-data ingestion.

Run:  python -m app.ingest            (from backend/)   [--refresh to re-download]

raw/        data/raw/        third-party files exactly as downloaded (git-ignored; re-downloaded on demand)
processed/  data/processed/  small, cleaned, schema-validated files the app reads (committed)

PROVENANCE RULE: every file below is a *third-party public dataset*. None is first-party
advertising data from Nike, Samsung, Lenovo, Louis Vuitton or Supreme, and none contains
ad spend / impressions / clicks / conversions for those brands. Each source's `contains`
and `does_not_contain` fields are written into processed/sources.json and shown in the UI.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import urllib.request
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from .config import DATA_DIR

RAW = DATA_DIR / "raw"
PROCESSED = DATA_DIR / "processed"
FX_INR = {"EUR": 90.0, "USD": 83.0}          # fixed demo conversion rates (assumption, not live FX)
N_SKU = 6
INGESTED_ON = date.today().isoformat()

KAGGLE = "https://www.kaggle.com/api/v1/datasets/download/{}"
SOURCES = {
    "marketing": dict(
        id="marketing", scope="Generic marketing data (not brand-specific; anonymised advertiser)", name="Sales Conversion Optimization (Facebook ad campaigns)",
        publisher="Kaggle (loveall) — anonymised ad data from an unnamed company 'xyz'",
        url="https://www.kaggle.com/datasets/loveall/clicks-conversion-tracking",
        download="https://huggingface.co/spaces/Fah/gradio-prediction-conversionrate/resolve/06769cab5b304abfa4ae061250216e1751eb9e97/KAG_conversion_data.csv",
        file="KAG_conversion_data.csv", license="Other (specified in the Kaggle dataset description)", type="Public ad-performance data",
        contains="Per-ad impressions, clicks, spend, enquiries and approved (purchase) conversions, with age/gender/interest segment.",
        does_not_contain="Any brand identity, product, price, margin, inventory, or revenue. Not from any of the five demo brands.",
        used_for="Training the conversion-propensity model (ML Lab).",
        limitations="1,143 ads from one advertiser, single quarter; weak-to-moderate signal; USD spend."),
    "nike": dict(
        id="nike", scope="Brand-specific public product data (third-party; not first-party brand data)", name="Adidas vs Nike (retail product listings)", publisher="Kaggle (kaushiksuresh147)",
        url="https://www.kaggle.com/datasets/kaushiksuresh147/adidas-vs-nike", download=KAGGLE.format("kaushiksuresh147/adidas-vs-nike"),
        file="adidas-vs-nike/Adidas Vs Nike.csv", license="CC0: Public Domain", type="Public product listing data",
        contains="Product names, INR sale prices, ratings and review counts for Nike listings, scraped 2020-04.",
        does_not_contain="Ad spend, impressions, clicks, conversions, unit costs, inventory or actual units sold.",
        used_for="Nike product names, prices, popularity signal (reviews/ratings).",
        limitations="Snapshot from 2020; discount field is zero throughout; review count is only a popularity proxy."),
    "samsung": dict(
        id="samsung", scope="Brand-specific public product data (third-party; not first-party brand data)", name="Flipkart Mobile Dataset", publisher="Kaggle (shubhambathwal)",
        url="https://www.kaggle.com/datasets/shubhambathwal/flipkart-mobile-dataset", download=KAGGLE.format("shubhambathwal/flipkart-mobile-dataset"),
        file="flipkart-mobile-dataset/Flipkart Mobile - 2.csv", license="CC0: Public Domain", type="Public marketplace listing data",
        contains="Smartphone models with RAM/ROM, INR sale price, discount %, ratings, rating counts and a relative sales index.",
        does_not_contain="Ad spend, impressions, clicks, conversions, unit costs or Samsung first-party sales.",
        used_for="Samsung phone names, prices, discounts, popularity signal.",
        limitations="Flipkart listing view only; 'sales' is an unexplained relative index."),
    "lenovo": dict(
        id="lenovo", scope="Brand-specific public product data (third-party; not first-party brand data)", name="Flipkart India Laptops under ₹75,000", publisher="Kaggle (arindamsingh)",
        url="https://www.kaggle.com/datasets/arindamsingh/flipkart-india-laptops-under-75000", download=KAGGLE.format("arindamsingh/flipkart-india-laptops-under-75000"),
        file="flipkart-india-laptops-under-75000/Flipkart_India_Laptops_under_75000.csv", license="CC0: Public Domain", type="Public marketplace listing data",
        contains="Laptop names, processor, RAM/SSD, INR price and Flipkart popularity rank.",
        does_not_contain="Ad spend, clicks, conversions, costs, inventory, or Lenovo first-party sales. Only laptops under ₹75,000.",
        used_for="Lenovo laptop names, prices, popularity signal (rank).",
        limitations="Single marketplace, price-capped range; no enterprise/ThinkPad-tier pricing."),
    "lv": dict(
        id="lv", scope="Brand-specific public product data (third-party; not first-party brand data)", name="Louis Vuitton product price list — France (Data Boutique)", publisher="DBQ / Data Boutique on Hugging Face",
        url="https://huggingface.co/datasets/DBQ/Louis.Vuitton.Product.prices.France",
        download="https://huggingface.co/datasets/DBQ/Louis.Vuitton.Product.prices.France/resolve/main/data/train-00000-of-00001-7dd58d9660ecce43.parquet",
        file="lv_fr.parquet", license="Unknown", type="Public web-scraped catalog",
        contains="Product titles, categories and EUR list prices from the French LV website (2023-11-17).",
        does_not_contain="Ad data, unit costs, sales, inventory. Prices converted at a fixed demo rate (1 EUR = ₹90).",
        used_for="LV product names, categories, price tiers.",
        limitations="Scraped catalog snapshot; the dataset card states the licence as unknown, so it is used only for product names/prices context; no sales or popularity signal."),
    "supreme": dict(
        id="supreme", scope="Brand-specific public product data (third-party; not first-party brand data)", name="Sneakers & Streetwear Sales (2022)", publisher="Kaggle (atharvasoundankar)",
        url="https://www.kaggle.com/datasets/atharvasoundankar/sneakers-and-streetwear-sales-2022", download=KAGGLE.format("atharvasoundankar/sneakers-and-streetwear-sales-2022"),
        file="sneakers-and-streetwear-sales-2022/sneakers_streetwear_sales_data.csv", license="Apache 2.0", type="Public transaction sample (provenance not documented by publisher)",
        contains="353 transactions across streetwear brands; only 32 Supreme rows, all one product type (hoodie), USD prices, 2022-01..08.",
        does_not_contain="Any Supreme product other than hoodies, ad data, costs or inventory. Cannot be verified as Supreme's own sales.",
        used_for="Supreme hoodie price/volume signal. Other Supreme SKUs are DEMO catalog assumptions (labelled).",
        limitations="Tiny sample; unverified origin. Remaining SKUs are illustrative, not sourced."),
}

# --------------------------------------------------------------------------- #

def _fetch(src: dict, refresh: bool):
    path = RAW / src["file"]
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {src['download']}")
    req = urllib.request.Request(src["download"], headers={"User-Agent": "aegisone-ingest"})
    blob = urllib.request.urlopen(req, timeout=120).read()
    if src["download"].startswith(KAGGLE.format("")):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            z.extractall(path.parent)
    else:
        path.write_bytes(blob)
    return path


def _need(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: schema changed, missing columns {missing}")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:28].strip("-")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).replace("�", "").replace("�", "")).strip()


def _pop01(x: pd.Series) -> pd.Series:
    r = x.rank(pct=True)
    return r.round(3)


def _sku_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df[["name", "category", "price_inr", "popularity", "source_rows"]]


# ---------------------------- per-brand selection --------------------------- #

def nike(raw) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(raw)
    _need(df, ["Product Name", "Sale Price", "Rating", "Reviews", "Brand", "Last Visited"], "nike")
    n = df[df.Brand == "Nike"].copy()
    n = n[n["Sale Price"] > 0].drop_duplicates("Product Name")

    def cat(t):
        t = t.lower()
        for k, v in (("jordan", "Jordan"), ("air max", "Air Max"), ("air force", "Lifestyle"), ("run", "Running"),
                     ("flyknit", "Running"), ("zoom", "Performance"), ("metcon", "Training")):
            if k in t:
                return v
        return "Lifestyle"
    n["category"] = n["Product Name"].map(cat)
    n["popularity"] = _pop01(n.Reviews)
    n["price_inr"] = n["Sale Price"].astype(float)
    pick = n[(n.price_inr >= 4000)].sort_values("Reviews", ascending=False).groupby("category").head(1).head(N_SKU)
    pick = pick.rename(columns={"Product Name": "name"})
    meta = dict(source_rows=int(len(df[df.Brand == "Nike"])), date_range=f"{n['Last Visited'].min()[:10]} (single scrape)")
    return pick.assign(source_rows=1)[["name", "category", "price_inr", "popularity", "source_rows"]], meta


def samsung(raw):
    df = pd.read_csv(raw)
    _need(df, ["brand", "model", "ROM", "RAM", "sales_price", "ratings", "num_of_ratings", "discount_percent", "sales"], "samsung")
    s = df[df.brand == "Samsung"].copy()
    g = s.groupby(["model", "RAM", "ROM"], as_index=False).agg(price=("sales_price", "median"), nr=("num_of_ratings", "sum"),
                                                                   sales=("sales", "sum"), n=("model", "size"))
    g["name"] = g.model + " " + g.RAM.astype(str) + "GB/" + g.ROM.astype(str) + "GB"
    g["category"] = np.where(g.price >= 40000, "Flagship", np.where(g.price >= 20000, "Mid-range", "Value"))
    g = g.sort_values("nr", ascending=False).drop_duplicates("model")      # one variant per model
    g["popularity"] = _pop01(g.nr)
    pick = g.sort_values("nr", ascending=False).groupby("category").head(2).sort_values("nr", ascending=False).head(N_SKU)
    pick = pick.rename(columns={"price": "price_inr", "n": "source_rows"})
    return pick[["name", "category", "price_inr", "popularity", "source_rows"]], dict(source_rows=int(len(s)), date_range="Flipkart snapshot (2021)")


def lenovo(raw):
    df = pd.read_csv(raw)
    _need(df, ["Laptop_Name", "Popularity_Rank", "Lenovo", "Price", "RAM Capacity (in GB)", "SSD (in GB)"], "lenovo")
    l = df[df.Lenovo == 1].copy()
    l["category"] = np.where(l.Price >= 55000, "Premium", np.where(l.Price >= 38000, "Mainstream", "Entry"))
    l["popularity"] = (1 - l.Popularity_Rank.rank(pct=True)).round(3)
    l["name"] = l.Laptop_Name.str.replace(r"\s+", " ", regex=True) + " " + l["RAM Capacity (in GB)"].astype(str) + "GB/" + l["SSD (in GB)"].astype(str) + "GB SSD"
    l = l.drop_duplicates("Laptop_Name")
    pick = l.sort_values("Popularity_Rank").groupby("category").head(2).sort_values("Popularity_Rank").head(N_SKU)
    pick = pick.assign(price_inr=pick.Price.astype(float), source_rows=1)
    return pick[["name", "category", "price_inr", "popularity", "source_rows"]], dict(source_rows=int(len(l)), date_range="Flipkart snapshot (2022)")


def lv(raw):
    df = pd.read_parquet(raw)
    _need(df, ["title", "category2_code", "price_eur", "competence_date"], "lv")
    df = df[df.price_eur > 0].copy()
    df["title"] = df.title.map(_clean)
    cats = {"SACS A MAIN": "Handbags", "SOULIERS": "Shoes", "PORTEFEUILLES ET PETITE MAROQUINERIE": "Small leather goods",
            "PRET A PORTER": "Ready-to-wear", "BIJOUX": "Jewelry", "ACCESSOIRES": "Accessories"}
    rows = []
    for k, label in cats.items():
        c = df[df.category2_code == k]
        c = c[c.price_eur <= c.price_eur.quantile(0.9)]
        med = c.price_eur.median()
        r = c.iloc[(c.price_eur - med).abs().argsort()[:1]].iloc[0]
        rows.append(dict(name=r.title, category=label, price_inr=float(r.price_eur) * FX_INR["EUR"], popularity=np.nan, source_rows=int(len(c))))
    return pd.DataFrame(rows), dict(source_rows=int(len(df)), date_range=f"{df.competence_date.min()} (single scrape)")


def supreme(raw):
    df = pd.read_csv(raw)
    _need(df, ["Brand", "Product Name", "Quantity", "Unit Price ($)", "Date"], "supreme")
    s = df[df.Brand == "Supreme"]
    hood = s["Unit Price ($)"].median() * FX_INR["USD"]
    # Only the hoodie is sourced. The rest are clearly-labelled demo catalog assumptions (prices ~ public retail tiers).
    demo = [("Box Logo T-Shirt (demo SKU)", "Tees", 4200), ("Skate Deck (demo SKU)", "Hardgoods", 7000),
            ("Six-Panel Cap (demo SKU)", "Headwear", 5800), ("Shoulder Bag (demo SKU)", "Accessories", 9500),
            ("Crewneck Sweatshirt (demo SKU)", "Sweats", 15500)]
    rows = [dict(name="Supreme Hoodie", category="Hoodies", price_inr=float(hood), popularity=0.9, source_rows=int(len(s)))]
    for i, (n, c, p) in enumerate(demo):
        rows.append(dict(name=n, category=c, price_inr=float(p), popularity=round(0.35 + 0.1 * i, 2), source_rows=0))
    meta = dict(source_rows=int(len(s)), date_range=f"{s.Date.min()} .. {s.Date.max()}")
    return pd.DataFrame(rows), meta


BRANDS = {"nike": nike, "samsung": samsung, "lenovo": lenovo, "lv": lv, "supreme": supreme}


def marketing(raw):
    df = pd.read_csv(raw)
    _need(df, ["ad_id", "xyz_campaign_id", "age", "gender", "interest", "Impressions", "Clicks", "Spent", "Total_Conversion", "Approved_Conversion"], "marketing")
    if (df[["Impressions", "Clicks", "Spent", "Approved_Conversion"]] < 0).any().any():
        raise ValueError("marketing: negative metrics")
    if (df.Clicks > df.Impressions).any():
        raise ValueError("marketing: clicks > impressions")
    return df[["ad_id", "xyz_campaign_id", "age", "gender", "interest", "Impressions", "Clicks", "Spent", "Total_Conversion", "Approved_Conversion"]], \
        dict(source_rows=int(len(df)), date_range="Not stated (single quarter, 2017 publication)")


def main(refresh: bool = False) -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid, fn in {**BRANDS, "marketing": marketing}.items():
        src = dict(SOURCES[sid])
        raw = _fetch(src, refresh)
        df, meta = fn(raw)
        fname = "ad_conversions.csv" if sid == "marketing" else f"catalog_{sid}.csv"
        if sid != "marketing":
            if len(df) != N_SKU:
                raise ValueError(f"{sid}: expected {N_SKU} SKUs, got {len(df)}")
            df = df.assign(sku_key=df.name.map(_slug)).drop_duplicates("sku_key")
            df["popularity"] = df.popularity.fillna(0.5)
            df["price_inr"] = df.price_inr.round(0)
        df.to_csv(PROCESSED / fname, index=False)
        src.update(meta, processed_file=fname, processed_rows=int(len(df)), ingested=INGESTED_ON,
                   notes=("Cleaned (null/neg/click>impression checks); rate features added at training time." if sid == "marketing" else
                          "Filtered to brand, de-duplicated, one representative SKU per category chosen deterministically by public popularity; "
                          "prices in INR; popularity = percentile rank of the public popularity field."))
        out[sid] = src
        print(f"  {sid:10s} -> processed/{fname} ({len(df)} rows from {meta['source_rows']} source rows)")
    (PROCESSED / "sources.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    main(ap.parse_args().refresh)
