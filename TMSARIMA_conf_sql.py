import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "intDB_TMSARIMA.db")


def _execute(query, params=None):
    if params is None:
        params = ()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()


def _fetch(query, params=None):
    if params is None:
        params = ()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def init_db():
    _execute(
        """
        CREATE TABLE IF NOT EXISTS efd_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            measurement TEXT NOT NULL,
            field TEXT NOT NULL,
            salIndex INTEGER,
            value REAL NOT NULL,
            resolution TEXT NOT NULL,
            UNIQUE (timestamp_utc, measurement, field, salIndex, resolution)
        )
        """
    )


def insert_efd_point(
    measurement: str,
    field: str,
    salIndex: Optional[int],
    timestamp_utc: datetime,
    value: float,
    resolution: str = "1h",
):
    _execute(
        """
        INSERT OR IGNORE INTO efd_series
        (timestamp_utc, measurement, field, salIndex, value, resolution)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp_utc.isoformat(),
            measurement,
            field,
            salIndex,
            value,
            resolution,
        ),
    )


def list_signals() -> List[Tuple[str, str, Optional[int]]]:
    rows = _fetch(
        """
        SELECT DISTINCT measurement, field, salIndex
        FROM efd_series
        ORDER BY measurement, field, salIndex
        """
    )
    return [(r[0], r[1], r[2]) for r in rows]


def fetch_series(
    measurement: str,
    field: str,
    salIndex: Optional[int],
    resolution: str = "1h",
) -> List[Tuple[datetime, float]]:
    rows = _fetch(
        """
        SELECT timestamp_utc, value
        FROM efd_series
        WHERE measurement = ?
          AND field = ?
          AND resolution = ?
          AND (salIndex IS ? OR salIndex = ?)
        ORDER BY timestamp_utc ASC
        """,
        (measurement, field, resolution, salIndex, salIndex),
    )
    return [(datetime.fromisoformat(r[0]), float(r[1])) for r in rows]
