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
import sys
import os
from datetime import datetime
import httpx
import pytz
from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config_loader import read_config_from_db

from logger_setup import logger, LOG_TIME_FORMAT

load_dotenv()

CHILE_TZ = pytz.timezone("America/Santiago")

URL_PREV_MAINT_CONFIG_CARDS = os.getenv("URL_PREV_MAINT_CONFIG_CARDS")
URL_PREV_MAINT_CONFIG_CARD = os.getenv("URL_PREV_MAINT_CONFIG_CARD")
URL_ASSET_CARD = os.getenv("URL_ASSET_CARD")
URL_CREATE_PM_INSTANCE = os.getenv("URL_CREATE_PM_INSTANCE")
URL_ACTIVITIES = os.getenv("URL_ACTIVITIES")
URL_ADVANCE = os.getenv("URL_ADVANCE")
get_current_time_chile = LOG_TIME_FORMAT

async def get_prev_maint_configs(client: httpx.AsyncClient, token: str) -> list:
    headers = {"CMDBuild-Authorization": token}
    try:
        response = await client.get(URL_PREV_MAINT_CONFIG_CARDS, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", [])
        logger.info(f"{
            get_current_time_chile()} - Retrieved {len(data)} preventive maintenance configs from CMMS.")
        return data
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Failed to fetch maintenance configurations: {e}")
        return []


async def get_prev_maint_config_by_id(client: httpx.AsyncClient, token: str, config_id: str) -> dict:
    headers = {"CMDBuild-Authorization": token}
    url = URL_PREV_MAINT_CONFIG_CARD.format(config_id=config_id)
    try:
        response = await client.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        config_data = response.json().get("data", {})
        logger.info(f"{get_current_time_chile()} - Fetched config details for ID {config_id}.")
        return config_data
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Failed to fetch config {config_id}: {e}")
        return {}


async def get_attribute(client: httpx.AsyncClient, token: str, asset_id: str | int, attribute: str):
    headers = {"CMDBuild-Authorization": token}
    url = URL_ASSET_CARD.format(asset_id=asset_id)
    try:
        response = await client.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        value = response.json()["data"].get(attribute)
        logger.info(f"{get_current_time_chile()} - [CMMS] Asset {asset_id}: {attribute}={value}")
        return value
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Could not get '{attribute}' from asset {asset_id}: {e}")
        return None


def is_trigger_met(value, config: dict) -> bool:
    try:
        trigger_types = [
            ("trigger_integer", float),
            ("trigger_string", str),
            ("trigger_time", str),
            ("trigger_True_False", lambda x: str(x).lower() in ("true", "1")),
        ]

        for key, caster in trigger_types:
            trigger_value = config.get(key)
            if trigger_value is not None:
                if value is None:
                    logger.warning(f"{get_current_time_chile()} Value is None for config {config.get('_id')}")
                    return False
                try:
                    if caster(value) == caster(trigger_value):
                        return True
                    else:
                        logger.info(f"{
                            get_current_time_chile()
                            } - Trigger not met for {config.get('_id')}: {value} != {trigger_value}")
                        return False
                except (ValueError, TypeError) as e:
                    logger.warning(f"{get_current_time_chile()} - Failed casting for {key}: {e}")
                    return False

        logger.warning(f"{get_current_time_chile()} - No valid trigger found in config {config.get('_id')}")
        return False
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Trigger evaluation failed: {e}")
        return False


async def check_existing_active_pm(client: httpx.AsyncClient,
                                   token: str,
                                   config_id: str) -> tuple[bool, str | None]:
    headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}
    try:
        response = await client.get(URL_CREATE_PM_INSTANCE, headers=headers, timeout=10)
        response.raise_for_status()
        for pm in response.json().get("data", []):
            if pm.get("PrevMaintConfig") == config_id:
                status = pm.get("_status_description", "").lower()
                if status != "aborted":
                    logger.info(f"{
                        get_current_time_chile()
                        } - Existing active PM found for config {config_id}: PM ID {pm.get('_id')}")
                    return True, pm.get("_id")
        return False, None
    except Exception as e:
        logger.warning(f"{get_current_time_chile()} - Could not check existing PM: {e}")
        return False, None


async def create_pm(client: httpx.AsyncClient, token: str, config_id: str) -> str | None:
    headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}
    config_data = await get_prev_maint_config_by_id(client, token, config_id)
    if not config_data:
        logger.warning(f"{get_current_time_chile()} - No configuration data to create PM for ID {config_id}")
        return None

    payload = {
        "maintConf": config_id,
        "PrevMaintConfig": config_id,
        "ShortDescr": config_data.get("Description"),
        "Site": config_data.get("Site"),
        "Action": config_data.get("Action"),
        "CISubset": config_data.get("CISubset"),
        "Team": config_data.get("Team"),
        "Priority": config_data.get("Priority"),
        "EstimatedDuration": config_data.get("EstimatedDuration"),
        "Notes": config_data.get("Notes"),
        "ActivityType": config_data.get("ActivityType"),
    }

    try:
        response = await client.post(URL_CREATE_PM_INSTANCE, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        pm_id = response.json().get("data", {}).get("_id")
        logger.info(f"{get_current_time_chile()} - Created new PM: ID {pm_id}")
        return pm_id
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Could not create PM: {e}")
        return None


async def advance_pm(client: httpx.AsyncClient, token: str, pm_id: str) -> bool:
    headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}
    url_activities = URL_ACTIVITIES.format(pm_id=pm_id)
    try:
        response = await client.get(url_activities, headers=headers, timeout=10)
        response.raise_for_status()
        activity_id = response.json()["data"][0]["_id"]
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Could not fetch activities for PM {pm_id}: {e}")
        return False

    url_advance = URL_ADVANCE.format(pm_id=pm_id)
    payload = {
        "_activity": activity_id,
        "_type": "PreventiveMaint",
        "_advance": True,
        "status": "acceptance",
        "execution_date": datetime.now(CHILE_TZ).strftime("%Y-%m-%d"),
    }

    try:
        response = await client.put(url_advance, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"{get_current_time_chile()} - Advanced PM {pm_id} to planning stage.")
        return True
    except Exception as e:
        logger.error(f"{get_current_time_chile()} - Could not advance PM {pm_id}: {e}")
        return False


async def maintenance_loop(token: str) -> None:
    async with httpx.AsyncClient(verify=False) as client:
        while True:
            configs = await get_prev_maint_configs(client, token)

            try:
                local_system_configs = read_config_from_db()
                logger.info(f"{
                    get_current_time_chile()} - Retrieved {len(local_system_configs)} local system configs.")
            except Exception as e:
                logger.error(f"{get_current_time_chile()} - Failed to load local configs: {e}")
                await asyncio.sleep(60)
                continue

            for config in configs:
                config_id = config.get("_id")
                asset_id = config.get("Asset_related")

                if not asset_id:
                    logger.warning(f"{get_current_time_chile()} - Missing asset for config {config_id}")
                    continue

                try:
                    asset_id = int(asset_id)
                except ValueError:
                    logger.warning(f"{get_current_time_chile()} - Invalid asset_id for config {config_id}")
                    continue

                system_cfg = next(
                    (c for c in local_system_configs if int(c.get("asset_id", -1)) == asset_id),
                    None
                )
                if not system_cfg:
                    logger.warning(f"{get_current_time_chile()} -No system config found for asset {asset_id}")
                    continue

                attribute = system_cfg.get("attribute")
                if not attribute:
                    logger.warning(f"{get_current_time_chile()} - No attribute defined for asset {asset_id}")
                    continue

                asset_value = await get_attribute(client, token, asset_id, attribute)
                if asset_value is None:
                    continue

                if not is_trigger_met(asset_value, config):
                    continue

                logger.info(f"{
                    get_current_time_chile()
                    } - Trigger met: config {config_id} — asset {asset_id} → {attribute}={asset_value}")

                exists, existing_pm_id = await check_existing_active_pm(client, token, config_id)
                if exists:
                    continue

                new_pm_id = await create_pm(client, token, config_id)
                if not new_pm_id:
                    continue

                await advance_pm(client, token, new_pm_id)

            await asyncio.sleep(60)
