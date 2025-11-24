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
from typing import Any, Dict, List, Optional, Tuple

import httpx
import pytz
from dotenv import load_dotenv

from backend.logger_setup import logger, LOG_TIME_FORMAT
from error_utils import safe_execution
from config_loader import read_config_from_db

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

CHILE_TZ = pytz.timezone("America/Santiago")

URL_PREV_MAINT_CONFIG_CARDS = os.getenv("URL_PREV_MAINT_CONFIG_CARDS")
URL_PREV_MAINT_CONFIG_CARD = os.getenv("URL_PREV_MAINT_CONFIG_CARD")
URL_ASSET_CARD = os.getenv("URL_ASSET_CARD")
URL_CREATE_PM_INSTANCE = os.getenv("URL_CREATE_PM_INSTANCE")
URL_ACTIVITIES = os.getenv("URL_ACTIVITIES")
URL_ADVANCE = os.getenv("URL_ADVANCE")


def _console(msg: str) -> None:
    """Mirror logs to stdout for visibility in Jupyter notebook terminals."""
    print(msg)


@safe_execution(retries=3, delay=3)
async def get_prev_maint_configs(client: httpx.AsyncClient, token: str) -> List[Dict[str, Any]]:
    """
    Retrieve all preventive maintenance configurations from CMMS.

    Parameters
    ----------
    client : httpx.AsyncClient
        CMMS HTTP client session.
    token : str
        CMMS authorization token.

    Returns
    -------
    list of dict
        Preventive maintenance configuration entries.
    """
    headers = {"CMDBuild-Authorization": token}
    response = await client.get(URL_PREV_MAINT_CONFIG_CARDS, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json().get("data", [])
    logger.info(f"{LOG_TIME_FORMAT()} Retrieved {len(data)} PM configuration records.")
    _console(f"[PM CONFIG] Retrieved {len(data)} records")
    return data


@safe_execution(retries=3, delay=3)
async def get_prev_maint_config_by_id(client: httpx.AsyncClient, token: str, config_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed configuration for a specific preventive maintenance setup.
    """
    headers = {"CMDBuild-Authorization": token}
    url = URL_PREV_MAINT_CONFIG_CARD.format(config_id=config_id)
    response = await client.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    config_data = response.json().get("data", {})
    logger.info(f"{LOG_TIME_FORMAT()} Retrieved PM configuration for {config_id}.")
    _console(f"[PM CONFIG] Loaded config {config_id}")
    return config_data


@safe_execution(retries=3, delay=3)
async def get_attribute(client: httpx.AsyncClient, token: str, asset_id: int, attribute: str) -> Optional[Any]:
    """
    Retrieve an asset attribute value from CMMS.
    """
    headers = {"CMDBuild-Authorization": token}
    url = URL_ASSET_CARD.format(asset_id=asset_id)
    response = await client.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    data = response.json().get("data", {})
    value = data.get(attribute)

    logger.info(f"{LOG_TIME_FORMAT()} Asset {asset_id}: {attribute}={value}")
    _console(f"[ATTRIBUTE] {asset_id}.{attribute} = {value}")

    return value


def is_trigger_met(value: Any, config: Dict[str, Any]) -> bool:
    """
    Evaluate whether the trigger condition in the PM config is met.
    """
    try:
        trigger_types = [
            ("trigger_integer", float),
            ("trigger_string", str),
            ("trigger_time", str),
            ("trigger_True_False", lambda x: str(x).lower() in ("true", "1")),
        ]

        for key, cast in trigger_types:
            expected = config.get(key)
            if expected is not None:
                try:
                    return cast(value) == cast(expected)
                except Exception:
                    return False

        return False
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Trigger evaluation failure: {exc}")
        _console(f"[TRIGGER ERROR] {exc}")
        return False


@safe_execution(retries=3, delay=3)
async def check_existing_active_pm(client: httpx.AsyncClient, token: str, config_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check whether an active PM instance already exists for this configuration.
    """
    headers = {"CMDBuild-Authorization": token}
    response = await client.get(URL_CREATE_PM_INSTANCE, headers=headers, timeout=10)
    response.raise_for_status()

    for pm in response.json().get("data", []):
        if pm.get("PrevMaintConfig") == config_id:
            status = (pm.get("_status_description") or "").lower()
            if status != "aborted":
                _console(f"[PM EXISTS] {config_id} (PM ID: {pm.get('_id')})")
                return True, pm.get("_id")

    return False, None


@safe_execution(retries=3, delay=3)
async def create_pm(client: httpx.AsyncClient, token: str, config_id: str) -> Optional[str]:
    """
    Create a new preventive maintenance instance in CMMS.
    """
    config_data = await get_prev_maint_config_by_id(client, token, config_id)
    if not config_data:
        return None

    payload = {key: config_data.get(key) for key in [
        "Description", "Site", "Action", "CISubset", "Team", "Priority",
        "EstimatedDuration", "Notes", "ActivityType",
    ]}
    payload["maintConf"] = config_id
    payload["PrevMaintConfig"] = config_id
    payload["ShortDescr"] = config_data.get("Description")

    headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}
    response = await client.post(URL_CREATE_PM_INSTANCE, headers=headers, json=payload, timeout=10)
    response.raise_for_status()

    new_id = response.json().get("data", {}).get("_id")
    _console(f"[PM CREATED] {new_id}")
    return new_id


@safe_execution(retries=3, delay=3)
async def advance_pm(client: httpx.AsyncClient, token: str, pm_id: str) -> bool:
    """
    Advance a PM instance to planning stage.
    """
    headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}

    url_activities = URL_ACTIVITIES.format(pm_id=pm_id)
    resp_acts = await client.get(url_activities, headers=headers, timeout=10)
    resp_acts.raise_for_status()
    activity_id = resp_acts.json()["data"][0]["_id"]

    payload = {
        "_activity": activity_id,
        "_type": "PreventiveMaint",
        "_advance": True,
        "status": "acceptance",
        "execution_date": datetime.now(CHILE_TZ).strftime("%Y-%m-%d"),
    }

    url_advance = URL_ADVANCE.format(pm_id=pm_id)
    resp_adv = await client.put(url_advance, headers=headers, json=payload, timeout=10)
    resp_adv.raise_for_status()

    _console(f"[PM ADVANCED] {pm_id}")
    return True


async def maintenance_loop(token: str) -> None:
    """
    Continuous execution loop to evaluate triggers and create PM instances.
    """
    async with httpx.AsyncClient(verify=False) as client:
        while True:
            configs = await get_prev_maint_configs(client, token)

            try:
                system_configs = read_config_from_db()
            except Exception as exc:
                logger.error(f"{LOG_TIME_FORMAT()} Failed to load local config DB: {exc}")
                _console(f"[LOCAL CONFIG ERROR] {exc}")
                await asyncio.sleep(60)
                continue

            for config in configs:
                config_id = config.get("_id")
                asset_id = config.get("Asset_related")

                if not asset_id:
                    continue

                try:
                    asset_id = int(asset_id)
                except ValueError:
                    continue

                sys_cfg = next((c for c in system_configs if int(c.get("asset_id", -1)) == asset_id), None)
                if not sys_cfg:
                    continue

                attribute = sys_cfg.get("attribute")
                if not attribute:
                    continue

                value = await get_attribute(client, token, asset_id, attribute)
                if value is None or not is_trigger_met(value, config):
                    continue

                exists, existing_pm_id = await check_existing_active_pm(client, token, config_id)
                if exists:
                    continue

                new_pm_id = await create_pm(client, token, config_id)
                if new_pm_id:
                    await advance_pm(client, token, new_pm_id)

            await asyncio.sleep(60)
