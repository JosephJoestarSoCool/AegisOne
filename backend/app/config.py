"""Paths and global constants.

Everything the API needs at runtime lives under backend/ so the backend can be deployed on its own
(e.g. a Vercel project with Root Directory = backend):

  backend/data/processed   public catalogs + training data (committed, read-only at runtime)
  backend/data/models      trained model artifact + model card (committed, read-only at runtime)
  <DB_PATH>                SQLite demo database, built deterministically on first start

Serverless platforms mount the deployment read-only; only the temp directory is writable. On Vercel (VERCEL=1) the
SQLite file therefore defaults to <tmp>/aegis.db and is rebuilt (deterministically) whenever an instance cold-starts.
"""
import os
import tempfile
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ["AEGIS_DATA_DIR"]) if os.environ.get("AEGIS_DATA_DIR") else BACKEND_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
SERVERLESS = bool(os.environ.get("VERCEL"))
if os.environ.get("AEGIS_DB"):
    DB_PATH = Path(os.environ["AEGIS_DB"])
elif SERVERLESS:
    DB_PATH = Path(tempfile.gettempdir()) / "aegis.db"
else:
    DB_PATH = DATA_DIR / "aegis.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

AS_OF = date(2026, 10, 6)       # last day of synthetic data ("today" for the engine)
HISTORY_DAYS = 60
SEED = 42

RECENT_DAYS = 5                 # "current" performance window
BASELINE_START = 33             # days back from AS_OF where the baseline window starts
BASELINE_END = 8                # ... and ends (exclusive of the recent/anomaly window)
