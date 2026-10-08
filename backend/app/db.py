"""SQLite access helpers."""
from __future__ import annotations

import sqlite3

import pandas as pd

from .config import DB_PATH


def ensure_db() -> None:
    if not DB_PATH.exists():
        from .datagen import build_database
        build_database(write_csv=False)      # CSV exports are a dev convenience (`python -m app.datagen`)


def connect() -> sqlite3.Connection:
    ensure_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def read(con: sqlite3.Connection, sql: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, con, params=params)
