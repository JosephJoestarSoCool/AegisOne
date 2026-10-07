"""Paths and global constants."""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CSV_DIR = DATA_DIR / "csv"
DB_PATH = Path(os.environ["AEGIS_DB"]) if os.environ.get("AEGIS_DB") else DATA_DIR / "aegis.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

AS_OF = date(2026, 10, 6)       # last day of synthetic data ("today" for the engine)
HISTORY_DAYS = 60
SEED = 42

RECENT_DAYS = 5                 # "current" performance window
BASELINE_START = 33             # days back from AS_OF where the baseline window starts
BASELINE_END = 8                # ... and ends (exclusive of the recent/anomaly window)
