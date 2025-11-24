# This file is part of {{ fourbad123.CDIAT_PROYECT }}.
#
# Developed for the LSST System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
import pytz
import logging
import os
from typing import Any, Iterable, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, "intDB.db")
CHILE_TZ = pytz.timezone("America/Santiago")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)

def _execute_query(query: str, params: Iterable[Any] | None = None,
                   db_path: str = DB_PATH) -> None:
    """Execute a write query (INSERT, UPDATE, DELETE)."""
    params = params or ()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(query, params)
            conn.commit()
    except Exception as exc:
        logger.error(f"DB write failed: {exc}")


def _execute_fetch(query: str, params: Iterable[Any] | None = None,
                   db_path: str = DB_PATH) -> list[tuple]:
    """Execute a SELECT query and return all rows."""
    params = params or ()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(query, params)
            return cur.fetchall()
    except Exception as exc:
        logger.error(f"DB fetch failed: {exc}")
        return []

def read_config_from_db(db_path: str = DB_PATH) -> list[dict]:
    """
    Read all configuration entries from `config_interval`.

    Returns
    -------
    list of dict
        Each dictionary contains the configuration fields.
    """
    rows = _execute_fetch(
        """
        SELECT id, name, measurement, field, asset_id, attribute,
               db_name, time_interval, salIndex, type_telemetry
        FROM config_interval
        """,
        db_path=db_path,
    )

    return [
        {
            "id": r[0],
            "name": r[1],
            "measurement": r[2],
            "field": r[3],
            "asset_id": r[4],
            "attribute": r[5],
            "db_name": r[6],
            "time_interval": r[7],
            "salIndex": r[8],
            "type_telemetry": r[9],
        }
        for r in rows
    ]


def insert_config(entry: dict, db_path: str = DB_PATH) -> None:
    """
    Insert a new configuration entry into `config_interval`.
    """
    _execute_query(
        """
        INSERT INTO config_interval
        (name, measurement, field, asset_id, attribute, db_name,
         time_interval, salIndex, type_telemetry)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["name"],
            entry["measurement"],
            entry["field"],
            entry["asset_id"],
            entry["attribute"],
            entry["db_name"],
            entry.get("time_interval", "24h"),
            entry.get("salIndex"),
            entry.get("type_telemetry"),
        ),
        db_path=db_path,
    )
    logger.debug(f"Inserted config: {entry['name']}")


def update_config(entry: dict, db_path: str = DB_PATH) -> None:
    """
    Update an existing configuration entry.
    """
    if "id" not in entry:
        raise ValueError("Configuration update requires 'id' field.")

    _execute_query(
        """
        UPDATE config_interval
        SET name = ?, measurement = ?, field = ?, asset_id = ?, attribute = ?,
            db_name = ?, time_interval = ?, salIndex = ?, type_telemetry = ?
        WHERE id = ?
        """,
        (
            entry["name"],
            entry["measurement"],
            entry["field"],
            entry["asset_id"],
            entry["attribute"],
            entry["db_name"],
            entry.get("time_interval", "24h"),
            entry.get("salIndex"),
            entry.get("type_telemetry"),
            entry["id"],
        ),
        db_path=db_path,
    )
    logger.debug(f"Updated configuration: {entry['id']}")

def has_24h_passed_since_last_run(db_path: str = DB_PATH) -> bool:
    """
    Determine whether 24 hours have elapsed since the last run.
    """
    rows = _execute_fetch(
        """SELECT last_run FROM shutter_schedule WHERE id = 1""",
        db_path=db_path,
    )

    if not rows:
        return True

    try:
        last_run = datetime.strptime(rows[0][0], "%Y-%m-%dT%H:%M:%S")
        last_run = CHILE_TZ.localize(last_run)
        now = datetime.now(CHILE_TZ)
        return (now - last_run) >= timedelta(hours=24)
    except Exception:
        return True


def save_shutter_activation_to_db(db_path: str, asset_id: str,
                                  num_activations: int) -> None:
    """
    Record shutter activation count.
    """
    timestamp = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
    _execute_query(
        """
        INSERT INTO shutter_activations (asset_id, last_update, last_activations)
        VALUES (?, ?, ?)
        """,
        (asset_id, timestamp, num_activations),
        db_path=db_path,
    )


def update_last_run_timestamp(db_path: str = DB_PATH) -> None:
    """
    Update shutter last-run timestamp.
    """
    now = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
    _execute_query(
        """
        INSERT INTO shutter_schedule (id, last_run)
        VALUES (1, ?)
        ON CONFLICT(id)
        DO UPDATE SET last_run=excluded.last_run
        """,
        (now,),
        db_path=db_path,
    )


def get_last_run_timestamp(db_path: str = DB_PATH) -> Optional[datetime]:
    """
    Retrieve the last shutter run timestamp.
    """
    rows = _execute_fetch(
        "SELECT last_run FROM shutter_schedule WHERE id = 1",
        db_path=db_path,
    )

    if rows and rows[0][0]:
        try:
            naive_dt = datetime.strptime(rows[0][0], "%Y-%m-%dT%H:%M:%S")
            return CHILE_TZ.localize(naive_dt)
        except Exception:
            return None

    return None

def save_efd_history(timestamp: str, measurement: str, field: str,
                     value: float, asset_id: str,
                     db_path: str = DB_PATH) -> None:
    """
    Save EFD data into history (skips duplicates).
    """
    exists = _execute_fetch(
        """
        SELECT 1 FROM efd_history
        WHERE timestamp = ? AND measurement = ? AND field = ? AND value = ?
        """,
        (timestamp, measurement, field, value),
        db_path=db_path,
    )

    if exists:
        return

    _execute_query(
        """
        INSERT INTO efd_history (timestamp, measurement, field, value, asset_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp, measurement, field, value, asset_id),
        db_path=db_path,
    )

def save_trigger_event(config_id: str, frequency: int, frequency_um: str,
                       db_path: str = DB_PATH) -> None:
    """
    Save or update trigger events in `trigger_log`.
    """
    ts = datetime.now().isoformat()
    _execute_query(
        """
        INSERT INTO trigger_log (config_id, last_trigger_time, frequency, frequencyUM)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(config_id)
        DO UPDATE SET
            last_trigger_time = excluded.last_trigger_time,
            frequency = excluded.frequency,
            frequencyUM = excluded.frequencyUM
        """,
        (config_id, ts, frequency, frequency_um),
        db_path=db_path,
    )


def get_last_trigger_info(config_id: str, db_path: str = DB_PATH
                          ) -> tuple[Optional[datetime], Optional[int], Optional[str]]:
    """
    Retrieve trigger log metadata.
    """
    rows = _execute_fetch(
        """
        SELECT last_trigger_time, frequency, frequencyUM
        FROM trigger_log
        WHERE config_id = ?
        """,
        (config_id,),
        db_path=db_path,
    )

    if not rows:
        return None, None, None

    ts, freq, freq_um = rows[0]

    try:
        ts = datetime.fromisoformat(ts)
    except Exception:
        ts = None

    return ts, freq, freq_um

def init_ml_storage(db_path: str = DB_PATH) -> None:
    """
    Create ML model table if it does not exist.
    """
    _execute_query(
        """
        CREATE TABLE IF NOT EXISTS ml_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement TEXT NOT NULL,
            field TEXT NOT NULL,
            slope REAL NOT NULL,
            intercept REAL NOT NULL,
            trained_at TEXT NOT NULL
        )
        """,
        db_path=db_path,
    )


def save_ml_linear_model(measurement: str, field: str,
                         slope: float, intercept: float,
                         db_path: str = DB_PATH) -> None:
    """
    Persist a trained linear regression model.
    """
    ts = datetime.now(CHILE_TZ).isoformat()
    _execute_query(
        """
        INSERT INTO ml_models (measurement, field, slope, intercept, trained_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (measurement, field, slope, intercept, ts),
        db_path=db_path,
    )


def load_latest_ml_linear_model(
    measurement: str, field: str,
    db_path: str = DB_PATH,
) -> Optional[tuple[float, float]]:
    """
    Load the newest model parameters.
    """
    rows = _execute_fetch(
        """
        SELECT slope, intercept
        FROM ml_models
        WHERE measurement = ? AND field = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (measurement, field),
        db_path=db_path,
    )

    if not rows:
        return None

    slope, intercept = rows[0]
    return float(slope), float(intercept)
