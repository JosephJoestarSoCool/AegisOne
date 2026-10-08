"""SQLite access helpers."""
from __future__ import annotations

import os
import sqlite3
import threading

import pandas as pd

from .config import DB_PATH


_BUILD_LOCK = threading.Lock()


def _build() -> None:
    """Build the deterministic demo DB next to its final path, then move it into place atomically, so no reader can ever
    see a half-written file. Caller holds _BUILD_LOCK."""
    from .datagen import build_database
    tmp = DB_PATH.with_name(f"{DB_PATH.name}.{os.getpid()}.building")
    try:
        build_database(tmp, write_csv=False)      # CSV exports are a dev convenience (`python -m app.datagen`)
        os.replace(tmp, DB_PATH)
    finally:
        tmp.unlink(missing_ok=True)


def ensure_db() -> None:
    """Concurrent first requests on a cold serverless instance must not race: the first builds, the rest wait."""
    if DB_PATH.exists():
        return
    with _BUILD_LOCK:
        if not DB_PATH.exists():
            _build()


def rebuild_db() -> None:
    """Regenerate the demo DB (used by POST /api/reset)."""
    with _BUILD_LOCK:
        _build()


def connect() -> sqlite3.Connection:
    ensure_db()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def read(con: sqlite3.Connection, sql: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(sql, con, params=params)
