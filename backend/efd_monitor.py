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

import os
import sys
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

import pytz
import httpx
from dotenv import load_dotenv

from influx_query import EfdQueryClient
from shutter_counter import get_shutter_activations
from error_utils import safe_execution
from backend.logger_setup import logger, LOG_TIME_FORMAT
from config_loader import (
    has_24h_passed_since_last_run,
    update_last_run_timestamp,
    get_last_run_timestamp,
    save_shutter_activation_to_db,
    save_efd_history,
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

ASSET_ENDPOINT = os.getenv("CMMS_ASSET_ENDPOINT")
CHILE_TZ = pytz.timezone("America/Santiago")


def _console(msg: str) -> None:
    """Mirror logs to stdout for visibility in Jupyter notebook terminals."""
    print(msg)


def query_latest_influx_value(
    client_efd: EfdQueryClient,
    measurement: str,
    field: str,
    interval: str,
    sal_index: Optional[int] = None,
) -> Optional[float]:
    """
    Query the most recent measurement value from InfluxDB.
    """
    if sal_index is not None:
        query = (
            f'SELECT "{field}" FROM "{measurement}" '
            f'WHERE time > now() - {interval} AND "salIndex" = {sal_index} '
            f"ORDER BY time DESC LIMIT 1"
        )
    else:
        query = (
            f'SELECT "{field}" FROM "{measurement}" '
            f"WHERE time > now() - {interval} ORDER BY time DESC LIMIT 1"
        )

    logger.info(f"{LOG_TIME_FORMAT()} Query: {query}")
    _console(f"[QUERY] {measurement}.{field}")

    result = client_efd.query(query)

    if result.empty:
        logger.info(f"{LOG_TIME_FORMAT()} No data returned for {measurement}.{field}")
        _console(f"[NO DATA] {measurement}.{field}")
        return None

    return float(result.iloc[0][field])


@safe_execution(retries=3, delay=2)
async def get_cmms_attribute(client, token, asset_id, attribute) -> Optional[float]:
    """
    Retrieve an attribute value from CMMS.
    """
    url = f"{ASSET_ENDPOINT}/{asset_id}"
    headers = {"CMDBuild-Authorization": token}
    response = await client.get(url, headers=headers)
    response.raise_for_status()

    data = response.json().get("data", {})
    value = data.get(attribute)

    logger.info(f"{LOG_TIME_FORMAT()} Retrieved {attribute}={value} from asset {asset_id}")
    _console(f"[GET] {attribute}={value} (asset {asset_id})")

    return float(value) if value is not None else None


@safe_execution(retries=3, delay=2)
async def update_cmms_attribute(client, token, asset_id, attribute, value) -> None:
    """
    Update a CMMS attribute.
    """
    url = f"{ASSET_ENDPOINT}/{asset_id}"
    headers = {
        "CMDBuild-Authorization": token,
        "Content-Type": "application/json",
    }
    payload = {attribute: int(float(value))}

    response = await client.put(url, headers=headers, json=payload)
    response.raise_for_status()

    logger.info(f"{LOG_TIME_FORMAT()} Updated {attribute}={value} for asset {asset_id}")
    _console(f"[UPDATE] {attribute}={value} → asset {asset_id}")


async def monitor_subsystem(token, site, db_name, config) -> None:
    """
    Monitor a subsystem and synchronize telemetry to CMMS.
    """
    measurement = config["measurement"]
    field = config["field"]
    asset_id = config["asset_id"]
    attribute = config["attribute"]
    interval = config.get("time_interval", "24h")
    influx_db_name = config.get("db_name", db_name)
    sal_index = config.get("salIndex")
    telemetry_type = config.get("type_telemetry")

    client_efd = EfdQueryClient(site=site, db_name=influx_db_name)

    async with httpx.AsyncClient(verify=False) as http_client:
        while True:
            try:
                _console(f"[MONITOR] {config['name']} (asset {asset_id})")

                if telemetry_type == "actuation":
                    if has_24h_passed_since_last_run():
                        activations = get_shutter_activations(site, influx_db_name, measurement, interval)
                        save_shutter_activation_to_db("intDB.db", asset_id, activations)

                        current = (await get_cmms_attribute(http_client, token, asset_id, attribute)) or 0.0

                        if activations > 0:
                            new_value = current + activations
                            await update_cmms_attribute(http_client, token, asset_id, attribute, new_value)
                            update_last_run_timestamp()

                else:
                    value = query_latest_influx_value(client_efd, measurement, field, interval, sal_index)

                    if value is not None:
                        await update_cmms_attribute(http_client, token, asset_id, attribute, value)
                        if measurement == "lsst.sal.MTM1M3.forceActuatorData":
                            ts = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
                            save_efd_history(ts, measurement, field, value, asset_id)

            except Exception as exc:
                logger.error(f"{LOG_TIME_FORMAT()} [MONITOR ERROR] {exc}", exc_info=True)
                _console(f"[ERROR] {exc}")

            await asyncio.sleep(60)
