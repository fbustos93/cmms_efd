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
from typing import Optional, Tuple

import pytz
import pandas as pd

from influx_query import EfdQueryClient
from backend.logger_setup import logger, LOG_TIME_FORMAT

CHILE_TZ = pytz.timezone("America/Santiago")
DB_PATH = "intDB.db"


def _console(msg: str) -> None:
    """Mirror logs to stdout for visibility when executed inside Jupyter notebooks."""
    print(msg)


def get_shutter_activations(
    site: str,
    db_name: str,
    measurement: str,
    time_interval: str = "24h",
) -> int:
    """
    Count the number of shutter activation events.

    An activation is defined as a transition from <= 90% to > 90% in either actuator.

    Parameters
    ----------
    site : str
        EFD site reference.
    db_name : str
        InfluxDB database name.
    measurement : str
        Measurement table name in InfluxDB.
    time_interval : str, default "24h"
        Lookback interval.

    Returns
    -------
    int
        Number of detected activations.
    """
    try:
        client = EfdQueryClient(site=site, db_name=db_name)

        query = (
            f'SELECT "positionActual0", "positionActual1" '
            f'FROM "{measurement}" '
            f'WHERE time > now() - {time_interval} '
            f'ORDER BY time ASC'
        )

        result: pd.DataFrame = client.query(query)
        if result.empty:
            _console("[SHUTTER] No telemetry data available")
            return 0

        active = (result["positionActual0"] > 90) | (result["positionActual1"] > 90)
        activations = active & (~active.shift(1).fillna(False))
        count = int(activations.sum())

        logger.debug(f"{LOG_TIME_FORMAT()} Shutter activations detected: {count}")
        _console(f"[SHUTTER] Activations detected: {count}")

        return count

    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Failed to evaluate shutter activations: {exc}")
        _console(f"[SHUTTER ERROR] {exc}")
        return 0


def load_last_activation(asset_id: str) -> Tuple[int, Optional[datetime]]:
    """
    Load the last stored activation count for an asset.

    Parameters
    ----------
    asset_id : str
        Asset reference.

    Returns
    -------
    (int, datetime or None)
        Last activation count and timestamp.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT last_activations, last_update FROM shutter_activations WHERE asset_id = ?",
            (asset_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            count = int(row[0])
            timestamp = datetime.fromisoformat(row[1])
            return count, timestamp

        return 0, None

    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Failed to load shutter activation state: {exc}")
        _console(f"[SHUTTER LOAD ERROR] {exc}")
        return 0, None


def save_last_activation(asset_id: str, count: int) -> None:
    """
    Save the current shutter activation state.

    Parameters
    ----------
    asset_id : str
        Asset reference.
    count : int
        Count to store.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        timestamp = datetime.now(CHILE_TZ).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO shutter_activations (asset_id, last_update, last_activations)
            VALUES (?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                last_update=excluded.last_update,
                last_activations=excluded.last_activations
            """,
            (asset_id, timestamp, count),
        )

        conn.commit()
        conn.close()

        logger.debug(f"{LOG_TIME_FORMAT()} Saved shutter activation for asset {asset_id}: {count}")
        _console(f"[SHUTTER SAVE] asset={asset_id}, count={count}")

    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Failed to store shutter activation state: {exc}")
        _console(f"[SHUTTER SAVE ERROR] {exc}")


def should_update(asset_id: str, hours: int = 24) -> bool:
    """
    Determine whether enough time has passed to update the shutter activation count.

    Parameters
    ----------
    asset_id : str
        Asset reference.
    hours : int, default 24
        Minimum required hours.

    Returns
    -------
    bool
        True if update should run, False otherwise.
    """
    _, last_update = load_last_activation(asset_id)
    if not last_update:
        return True

    now = datetime.now(CHILE_TZ)
    return (now - last_update) >= timedelta(hours=hours)
