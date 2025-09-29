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
import logging
import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, "intDB.db")

CHILE_TZ = pytz.timezone("America/Santiago")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def read_config_from_db(db_path=DB_PATH) -> list[dict]:
    """Read all configurations from the config_interval table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT name, measurement, field, asset_id, attribute, db_name, time_interval, salIndex, type_telemetry
        FROM config_interval
        """
    )
    rows = cursor.fetchall()
    conn.close()

    configs = [
        {
            "name": row[0],
            "measurement": row[1],
            "field": row[2],
            "asset_id": row[3],
            "attribute": row[4],
            "db_name": row[5],
            "time_interval": row[6],
            "salIndex": row[7],
            "type_telemetry": row[8],
        }
        for row in rows
    ]
    return configs


def insert_config(entry: dict, db_path=DB_PATH) -> None:
    """Insert a new configuration record into config_interval."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO config_interval
        (name, measurement, field, asset_id, attribute, db_name, time_interval, salIndex, type_telemetry)
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
    )

    conn.commit()
    conn.close()
    logger.debug(f"Inserted new configuration: {entry['name']}")


def update_config(entry: dict, db_path=DB_PATH) -> None:
    """Update an existing configuration record in config_interval."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE config_interval
        SET measurement = ?,
            field = ?,
            asset_id = ?,
            attribute = ?,
            db_name = ?,
            time_interval = ?,
            salIndex = ?,
            type_telemetry = ?
        WHERE name = ?
        """,
        (
            entry["measurement"],
            entry["field"],
            entry["asset_id"],
            entry["attribute"],
            entry["db_name"],
            entry.get("time_interval", "24h"),
            entry.get("salIndex"),
            entry.get("type_telemetry"),
            entry["name"],
        ),
    )

    conn.commit()
    conn.close()
    logger.debug(f"Updated configuration: {entry['name']}")


def has_24h_passed_since_last_run(db_path=DB_PATH) -> bool:
    """Check if 24 hours have passed since the last recorded run."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT last_run FROM shutter_schedule WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return True

    try:
        last_run = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=CHILE_TZ)
        now = datetime.now(CHILE_TZ)
        return (now - last_run) >= timedelta(hours=24)
    except Exception as err:
        logger.error(f"Failed to parse last_run timestamp: {err}")
        return True


def save_shutter_activation_to_db(db_path: str, asset_id: str, num_activations: int) -> None:
    """Save a shutter activation record in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    current_time = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")

    cursor.execute(
        """
        INSERT INTO shutter_activations (asset_id, last_update, last_activations)
        VALUES (?, ?, ?)
        """,
        (asset_id, current_time, num_activations),
    )

    conn.commit()
    conn.close()
    logger.debug(f"Saved shutter activation for asset {asset_id}: {num_activations}")


def update_last_run_timestamp(db_path=DB_PATH) -> None:
    """Update the last run timestamp to the current time
      in shutter_schedule table."""
    now = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO shutter_schedule (id, last_run)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET last_run=excluded.last_run
        """,
        (now,),
    )

    conn.commit()
    conn.close()
    logger.debug("Updated last run timestamp in shutter_schedule")


def get_last_run_timestamp(db_path=DB_PATH) -> datetime | None:
    """Get the last run timestamp from shutter_schedule
      as timezone-aware datetime."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT last_run FROM shutter_schedule WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        try:
            naive_dt = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%S")
            return CHILE_TZ.localize(naive_dt)
        except Exception as err:
            logger.error(f"Could not parse last_run timestamp: {err}")
            return None

    return None


def save_efd_history(timestamp: str,
                     measurement: str,
                     field: str,
                     value: float,
                     asset_id: str,
                     db_path=DB_PATH) -> None:
    """Save a telemetry history record if not duplicate."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1 FROM efd_history
        WHERE timestamp = ? AND measurement = ? AND field = ? AND value = ?
        """,
        (timestamp, measurement, field, value),
    )
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(
            """
            INSERT INTO efd_history (timestamp, measurement, field, value, asset_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, measurement, field, value, asset_id),
        )
        logger.debug(f"Inserted historical EFD value: {measurement}.{field} = {value} @ {timestamp}")
    else:
        logger.debug(f"Duplicate historical EFD entry skipped: {measurement}.{field} @ {timestamp}")

    conn.commit()
    conn.close()


def load_last_activation(asset_id: str) -> int:
    """Load the last saved shutter activation count from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT last_activations FROM shutter_activations WHERE asset_id = ?", (asset_id,)
        )
        row = cursor.fetchone()
        conn.close()

        return int(row[0]) if row else 0
    except Exception as err:
        logger.error(f"Failed to load activation count: {err}")
        return 0


def save_last_activation(asset_id: str, count: int) -> None:
    """Save the current shutter activation count
    and timestamp into the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now_str = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")

        cursor.execute(
            """
            INSERT INTO shutter_activations (asset_id, last_update, last_activations)
            VALUES (?, ?, ?)
            """,
            (asset_id, now_str, count),
        )

        conn.commit()
        conn.close()
        logger.debug(f"Saved last activation for asset {asset_id}: {count}")
    except Exception as err:
        logger.error(f"Failed to save activation count: {err}")


def save_trigger_event(config_id: str, frequency: int, frequency_um: str, db_path: str = "intDB.db") -> None:
    """Save or update a trigger event in the trigger_log table."""
    now = datetime.now().isoformat()
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO trigger_log (config_id, last_trigger_time, frequency, frequencyUM)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(config_id) DO UPDATE SET
                    last_trigger_time = excluded.last_trigger_time,
                    frequency = excluded.frequency,
                    frequencyUM = excluded.frequencyUM
            """, (config_id, now, frequency, frequency_um))
            conn.commit()
        logger.debug(f"Saved trigger event for config {config_id}")
    except Exception as e:
        logger.error(f"Failed to save trigger event for config {config_id}: {e}")


def get_last_trigger_info(config_id: str,
                          db_path: str = "intDB.db") -> tuple[datetime | None, int | None, str | None]:
    """Retrieve the last trigger timestamp, frequency,
    and unit for a given config_id."""
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT ID, last_trigger_time, frequency, frequencyUM
                FROM trigger_log
                WHERE config_id = ?
            """, (config_id,))
            row = cur.fetchone()

        if row and row[0]:
            try:
                last_time = datetime.fromisoformat(row[1])
                return last_time, row[2], row[3]
            except Exception as e:
                logger.error(f"Failed to parse last_trigger_time for config {config_id}: {e}")
    except Exception as e:
        logger.error(f"Failed to retrieve last trigger info for config {config_id}: {e}")
    return None, None, None
