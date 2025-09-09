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

import asyncio
import os
from datetime import datetime
import pytz
import httpx

from dotenv import load_dotenv

from config_loader import (
    has_24h_passed_since_last_run,
    update_last_run_timestamp,
    get_last_run_timestamp,
    save_shutter_activation_to_db,
    save_efd_history,
)
from influx_query import EfdQueryClient
from shutter_counter import get_shutter_activations
from error_utils import safe_execution

from logger_setup import logger, LOG_TIME_FORMAT

load_dotenv()

ASSET_ENDPOINT = os.getenv("CMMS_ASSET_ENDPOINT")
CHILE_TZ = pytz.timezone("America/Santiago")


def query_latest_influx_value(
    client_efd: EfdQueryClient,
    measurement: str,
    field: str,
    interval: str,
    sal_index: int | None = None,
) -> float | None:
    if sal_index is not None:
        query = (
            f'SELECT "{field}" FROM "{measurement}" '
            f'WHERE time > now() - {interval} AND "salIndex" = {sal_index} '
            f'ORDER BY time DESC LIMIT 1'
        )
        logger.info(f"{LOG_TIME_FORMAT()} - Executing InfluxDB query with salIndex={sal_index}")
    else:
        query = (
            f'SELECT "{field}" FROM "{measurement}" '
            f'WHERE time > now() - {interval} '
            f'ORDER BY time DESC LIMIT 1'
        )
        logger.info(f"{LOG_TIME_FORMAT()} - Executing InfluxDB query without salIndex")

    result = client_efd.query(query)
    if result.empty:
        logger.info(f"{LOG_TIME_FORMAT()} - No data returned for {measurement}.{field}")
        return None

    logger.info(f"{LOG_TIME_FORMAT()} - InfluxDB query result:\n{result}")
    return result.iloc[0][field]


@safe_execution(retries=3, delay=2)
async def get_cmms_attribute(client: httpx.AsyncClient,
                             token: str,
                             asset_id: str | int,
                             attribute: str) -> int | float | None:
    url = f"{ASSET_ENDPOINT}/{asset_id}"
    headers = {"CMDBuild-Authorization": token}

    response = await client.get(url, headers=headers)
    response.raise_for_status()
    data = response.json().get("data", {})
    value = data.get(attribute)
    logger.info(f"{LOG_TIME_FORMAT()} - [CMMS] Retrieved {attribute}={value} for asset {asset_id}")
    return value


@safe_execution(retries=3, delay=2)
async def update_cmms_attribute(client: httpx.AsyncClient,
                                token: str,
                                asset_id: str | int,
                                attribute: str,
                                value: int | float) -> None:
    url = f"{ASSET_ENDPOINT}/{asset_id}"
    headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}
    payload = {attribute: int(float(value))}

    response = await client.put(url, headers=headers, json=payload)
    response.raise_for_status()
    logger.info(f"{LOG_TIME_FORMAT()} - [CMMS] Updated {attribute}={value} for asset {asset_id}")


async def monitor_subsystem(token: str, site: str, db_name: str, config: dict) -> None:
    name = config["name"]
    measurement = config["measurement"]
    field = config["field"]
    asset_id = config["asset_id"]
    attribute = config["attribute"]
    interval = config.get("time_interval", "24h")
    influx_db_name = config.get("db_name", db_name)
    sal_index = config.get("salIndex")
    type_telemetry = config.get("type_telemetry")
    client_efd = EfdQueryClient(site=site, db_name=influx_db_name)

    async with httpx.AsyncClient(verify=False) as http_client:
        while True:
            try:
                if type_telemetry == "actuation":
                    cycle_active = has_24h_passed_since_last_run()
                    last_run = get_last_run_timestamp()
                    last_run_str = last_run.strftime("%Y-%m-%d %H:%M:%S") if last_run else "Never"

                    logger.info(f"{LOG_TIME_FORMAT()} - Last activation recorded: {last_run_str}")
                    logger.info(f"{LOG_TIME_FORMAT()} - Is 24h cycle active?: {cycle_active}")

                    if cycle_active:
                        activation_count = get_shutter_activations(site, influx_db_name, measurement,interval)
                        logger.info(f"{LOG_TIME_FORMAT()} - Shutter activations detected: {activation_count}")

                        save_shutter_activation_to_db("intDB.db", asset_id, activation_count)

                        cmms_value = await get_cmms_attribute(http_client, token, asset_id, attribute) or 0
                        logger.info(f"{LOG_TIME_FORMAT()} - Current CMMS value for {attribute}: {cmms_value}")

                        if activation_count > 0:
                            updated_value = cmms_value + activation_count
                            await update_cmms_attribute(http_client, token, asset_id, attribute,updated_value)
                            logger.info(
                                f"{LOG_TIME_FORMAT()}-Updated{attribute}to{updated_value}(+{activation_count})"
                                )
                            update_last_run_timestamp()
                            logger.info(f"{LOG_TIME_FORMAT()} - Updated last run timestamp in DB.")
                        else:
                            logger.info(f"{LOG_TIME_FORMAT()} - No new shutter activations.")
                    else:
                        logger.info(f"{LOG_TIME_FORMAT()} - Shutter cycle already executed in last 24h.")

                else:
                    value = query_latest_influx_value(client_efd, measurement, field, interval, sal_index)
                    logger.info(f"{LOG_TIME_FORMAT()} - type_telemetry: {type_telemetry}")

                    if value is not None:
                        logger.info(f"{LOG_TIME_FORMAT()}Retrieved value{name}.{measurement}.{field}={value}")
                        await update_cmms_attribute(http_client, token, asset_id, attribute, value)

                        if measurement == "lsst.sal.MTM1M3.forceActuatorData":
                            ts = datetime.now(CHILE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
                            save_efd_history(ts, measurement, field, value, asset_id)
                            logger.info(f"{LOG_TIME_FORMAT()} - Saved historical value to SQLite.")
                    else:
                        logger.warning(f"{LOG_TIME_FORMAT()} - No value retrieved for {measurement}.{field}")

            except Exception as err:
                logger.error(f"{LOG_TIME_FORMAT()} - [MONITOR ERROR] {err}")

            await asyncio.sleep(60)
