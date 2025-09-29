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

import sys
import asyncio
import os
import requests
import logging
from dotenv import load_dotenv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config_loader import read_config_from_db
from efd_monitor import monitor_subsystem
from pm_handler import maintenance_loop

# Load environment variables
load_dotenv()

AUTH_URL = os.getenv("AUTH_URL")
USERNAME = os.getenv("CMMS_USERNAME")
PASSWORD = os.getenv("CMMS_PASSWORD")


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("main.log")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
file_handler.setFormatter(file_formatter)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_token() -> str | None:
    """
    Obtain an authentication token from the CMMS API.

    Returns:
        Token string if successful, None otherwise.
    """
    if not AUTH_URL:
        logger.error("AUTH_URL is not defined in the .env file")
        return None

    headers = {"Content-Type": "application/json"}
    credentials = {
        "username": USERNAME,
        "password": PASSWORD,
    }

    try:
        response = requests.post(AUTH_URL, headers=headers, json=credentials, verify=False)
        response.raise_for_status()
        token = response.json().get("data", {}).get("_id")
        if token:
            logger.info("Authentication token obtained successfully.")
        else:
            logger.warning("Token not found in response.")
        return token
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to obtain token: {e}")
        return None


async def main():
    """
    Main entry point for the application.
    Retrieves CMMS token, loads configurations, and starts monitoring tasks.
    """
    site = "usdf"
    db_name = "efd"

    token = get_token()
    if not token:
        logger.error("Unable to start monitoring without authentication token.")
        return

    configs = read_config_from_db()
    if not configs:
        logger.warning("No configurations found in local DB. Nothing to monitor.")
        return

    monitoring_tasks = [
        monitor_subsystem(token, site, db_name, cfg)
        for cfg in configs
    ]
    monitoring_tasks.append(maintenance_loop(token))

    logger.info("Starting monitoring tasks...")
    await asyncio.gather(*monitoring_tasks)


if __name__ == "__main__":
    asyncio.run(main())
