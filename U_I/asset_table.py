# asset_table_panel.py
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, List

import requests
import pandas as pd
import panel as pn
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.logger_setup import logger, LOG_TIME_FORMAT
from config_loader import read_config_from_db

load_dotenv()

ASSET_ENDPOINT = os.getenv("CMMS_ASSET_ENDPOINT")
AUTH_URL = os.getenv("AUTH_URL")
USERNAME = os.getenv("CMMS_USERNAME")
PASSWORD = os.getenv("CMMS_PASSWORD")


def get_token() -> Optional[str]:
    """
    Authenticate to CMMS and return a session token.

    Returns
    -------
    str or None
        CMMS authentication token or None if authentication fails.
    """
    if not AUTH_URL or not USERNAME or not PASSWORD:
        logger.error(f"{LOG_TIME_FORMAT()} Missing authentication environment variables.")
        return None

    credentials = {"username": USERNAME, "password": PASSWORD}

    try:
        response = requests.post(AUTH_URL, json=credentials, verify=False, timeout=10)
        response.raise_for_status()
        return response.json().get("data", {}).get("_id")
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Authentication failure: {exc}", exc_info=True)
        return None


def get_asset_details(token: str, asset_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve CMMS asset information.

    Parameters
    ----------
    token : str
        Active CMMS authorization token.
    asset_id : str
        Target asset identifier.

    Returns
    -------
    dict or None
        CMMS asset record, or None if unavailable.
    """
    try:
        url = f"{ASSET_ENDPOINT.rstrip('/')}/{asset_id}"
        headers = {"CMDBuild-Authorization": token, "Content-Type": "application/json"}

        response = requests.get(url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        return response.json().get("data", {})
    except Exception as exc:
        logger.warning(f"{LOG_TIME_FORMAT()} Failed to retrieve asset {asset_id}: {exc}")
        return None


def extract_attribute(details: Dict[str, Any], attribute: str) -> str:
    """
    Extract a specific attribute from an asset record.

    Parameters
    ----------
    details : dict
        Asset data structure.
    attribute : str
        Target attribute key.

    Returns
    -------
    str
        Extracted attribute value or "N/A".
    """
    if not details:
        return "N/A"
    if attribute in details:
        return str(details[attribute])
    for key, value in details.items():
        if key.lower() == attribute.lower():
            return str(value)
    return "N/A"


def create_panel() -> pn.Column:
    """
    Construct the Panel UI for viewing CMMS asset values.

    Returns
    -------
    pn.Column
        UI layout containing load button and results table.
    """
    title = pn.pane.Markdown("### CMMS Asset Viewer")
    table_placeholder = pn.Spacer(height=10)

    def load_assets(event=None) -> None:
        token = get_token()
        if not token:
            table_placeholder.objects = [pn.pane.Markdown("**Authentication Failed**", style={"color": "red"})]
            return

        try:
            configs = read_config_from_db()
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Failed to read config DB: {exc}", exc_info=True)
            table_placeholder.objects = [pn.pane.Markdown("**Error reading configuration database**")]
            return

        if not configs:
            table_placeholder.objects = [pn.pane.Markdown("**No configured assets found.**")]
            return

        rows: List[Dict[str, str]] = []
        for entry in configs:
            asset_id = entry.get("asset_id")
            name = entry.get("name", "")
            attribute = entry.get("attribute", "")

            details = get_asset_details(token, str(asset_id))
            value = extract_attribute(details, attribute)

            rows.append({
                "ID": str(asset_id),
                "Name": name,
                "Attribute": attribute,
                "CMMS Value": value,
            })

        df = pd.DataFrame(rows)
        table = pn.widgets.Tabulator(df, height=350, layout="fit_data_stretch")

        table_placeholder.objects = [table]
        logger.info(f"{LOG_TIME_FORMAT()} Asset UI updated with {len(rows)} records.")

    load_button = pn.widgets.Button(name="Load Assets", button_type="primary")
    load_button.on_click(load_assets)

    return pn.Column(title, load_button, table_placeholder, sizing_mode="stretch_width")
