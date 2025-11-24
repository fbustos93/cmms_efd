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
from typing import Optional

import requests
from dotenv import load_dotenv

from backend.logger_setup import logger, LOG_TIME_FORMAT
from backend.error_utils import safe_execution

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config_loader import read_config_from_db
from backend.pm_handler import maintenance_loop
from backend.efd_monitor import monitor_subsystem

load_dotenv()

AUTH_URL = os.getenv("AUTH_URL")
USERNAME = os.getenv("CMMS_USERNAME")
PASSWORD = os.getenv("CMMS_PASSWORD")


def _console(msg: str) -> None:
    """Mirror logs to stdout for visibility when executed in Jupyter notebooks."""
    print(msg)


@safe_execution(retries=3, delay=3)
async def get_token() -> str | None:
    """
    Authenticate against CMMS and retrieve session token.
    """
    if not AUTH_URL:
        logger.error("AUTH_URL is not defined in environment variables.")
        _console("[AUTH ERROR] Missing AUTH_URL")
        return None

    headers = {"Content-Type": "application/json"}
    credentials = {"username": USERNAME, "password": PASSWORD}

    response = requests.post(
        AUTH_URL, headers=headers, json=credentials, verify=False, timeout=10
    )
    response.raise_for_status()

    token = response.json().get("data", {}).get("_id")
    if not token:
        logger.warning("Token missing in authentication response.")
        _console("[AUTH WARNING] Missing token field")
        return None

    logger.info(f"{LOG_TIME_FORMAT()} Authentication successful.")
    _console("[AUTH OK]")
    return token


async def main() -> None:
    """
    Backend entry point.

    Notes
    -----
    This function does:
    1. Authentication
    2. Load telemetry monitoring configuration
    3. Start monitoring + preventive maintenance tasks
    """
    site = "usdf"
    db_name = "efd"

    token = await get_token()
    if not token:
        logger.error(f"{LOG_TIME_FORMAT()} Cannot start backend without authentication token.")
        _console("[BACKEND ERROR] Token retrieval failed")
        return

    try:
        configs = read_config_from_db()
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Failed to load configuration database: {exc}", exc_info=True)
        _console(f"[CONFIG ERROR] {exc}")
        return

    if not configs:
        logger.warning("No telemetry system configuration found.")
        _console("[CONFIG WARNING] No monitor configurations. Backend idle.")
        return

    tasks = [monitor_subsystem(token, site, db_name, cfg) for cfg in configs]
    tasks.append(maintenance_loop(token))

    logger.info(f"{LOG_TIME_FORMAT()} Starting backend tasks ({len(tasks)} total).")
    _console(f"[BACKEND] Running {len(tasks)} async tasks")

    try:
        await asyncio.gather(*tasks)
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Exception during async execution: {exc}", exc_info=True)
        _console(f"[BACKEND ERROR] {exc}")