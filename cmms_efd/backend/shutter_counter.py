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


import sqlite3
from datetime import datetime, timedelta
import pytz
import pandas as pd
from influx_query import EfdQueryClient
from logger_setup import logger, LOG_TIME_FORMAT 

CHILE_TZ = pytz.timezone("America/Santiago")
DB_PATH = "intDB.db"


def get_shutter_activations(
    site: str, db_name: str, measurement: str, time_interval: str = "24h"
) -> int:
    """
    Count shutter activations where
    positionActual0 or positionActual1 exceeds 90%
    within the specified time interval.
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
            logger.debug(f"{LOG_TIME_FORMAT()} - No shutter data found in the last {time_interval}.")
            return 0

        activity = (result["positionActual0"] > 90) | (result["positionActual1"] > 90)
        activations = activity & (~activity.shift(1).fillna(False))
        count_activations = int(activations.sum())

        logger.debug(f"{
            LOG_TIME_FORMAT()} - Shutter activations >90% in last {time_interval}: {count_activations}")
        return count_activations

    except Exception as err:
        logger.error(f"{LOG_TIME_FORMAT()} - Failed to query or process shutter data: {err}")
        return 0


def load_last_activation(asset_id: str) -> tuple[int, datetime | None]:
    """
    Load the last saved shutter activation
    count and timestamp from the database.
    Returns (last_count, last_update_datetime)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_activations, last_update FROM shutter_activations WHERE asset_id = ?", (asset_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            last_count = int(row[0])
            last_update = datetime.fromisoformat(row[1])
            return last_count, last_update
        else:
            return 0, None

    except Exception as err:
        logger.error(f"{LOG_TIME_FORMAT()} - Failed to load activation count: {err}")
        return 0, None


def save_last_activation(asset_id: str, count: int) -> None:
    """
    Save the current shutter activation count and timestamp into the database.
    Uses INSERT OR REPLACE to avoid duplicates.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = LOG_TIME_FORMAT()

        cursor.execute(
            """
            INSERT INTO shutter_activations (asset_id, last_update, last_activations)
            VALUES (?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                last_update=excluded.last_update,
                last_activations=excluded.last_activations
            """,
            (asset_id, now_str, count),
        )

        conn.commit()
        conn.close()
        logger.debug(f"{LOG_TIME_FORMAT()} - Saved shutter activations for asset {asset_id}: {count}")

    except Exception as err:
        logger.error(f"{LOG_TIME_FORMAT()} - Failed to save activation count: {err}")


def should_update(asset_id: str, hours: int = 24) -> bool:
    """
    Check if enough time has passed since
    the last update to perform a new update.
    """
    _, last_update = load_last_activation(asset_id)
    if not last_update:
        return True
    now = datetime.now(CHILE_TZ)
    elapsed = now - last_update
    return elapsed >= timedelta(hours=hours)
