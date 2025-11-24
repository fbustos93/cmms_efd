# plot_interface_catcher_panel.py
from __future__ import annotations

import os
import sys
from typing import List, Dict, Any

import requests
import panel as pn
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.logger_setup import logger, LOG_TIME_FORMAT

load_dotenv()

AUTH_URL = os.getenv("AUTH_URL")
USERNAME = os.getenv("CMMS_USERNAME")
PASSWORD = os.getenv("CMMS_PASSWORD")
BASE_URL = os.getenv("URL_CREATE_PM_INSTANCE")


def get_token() -> str | None:
    """
    Authenticate to CMMS and return token.

    Returns
    -------
    str or None
        Authentication token.
    """
    payload = {"username": USERNAME, "password": PASSWORD}
    try:
        response = requests.post(AUTH_URL, json=payload, verify=False, timeout=10)
        response.raise_for_status()
        return response.json().get("data", {}).get("_id")
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Authentication failure: {exc}", exc_info=True)
        return None


def fetch_instances(token: str) -> List[Dict[str, Any]]:
    """
    Retrieve maintenance instances from CMMS.

    Returns
    -------
    list of dict
        Records from CMMS.
    """
    try:
        headers = {"CMDBuild-Authorization": token}
        response = requests.get(BASE_URL, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Failed to fetch records: {exc}", exc_info=True)
        return []


def fetch_activity(token: str, activity_id: str) -> Dict[str, Any]:
    """
    Retrieve a single maintenance record by ID.
    """
    try:
        headers = {"CMDBuild-Authorization": token}
        response = requests.get(f"{BASE_URL}/{activity_id}", headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        return response.json().get("data", {})
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Fetch activity failed: {exc}", exc_info=True)
        return {}


def parse_register(html: str) -> List[str]:
    """
    Extract notes from CMMS HTML register.
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    return [span.get_text(strip=True) for span in soup.select("span[data-block='notes']")]


def create_panel() -> pn.Column:
    """
    Render Panel interface for extracting maintenance notes.

    Returns
    -------
    pn.Column
        Panel UI layout.
    """
    title = pn.pane.Markdown("### Maintenance Notes Viewer")

    token = get_token()
    if not token:
        return pn.Column(title, pn.pane.Markdown("**Authentication failed.**"))

    instances = fetch_instances(token)
    if not instances:
        return pn.Column(title, pn.pane.Markdown("**No maintenance records available.**"))

    options = {
        inst.get("Description", f"ID {inst.get('_id')}"): inst.get("_id")
        for inst in instances
    }

    select = pn.widgets.MultiSelect(
        name="Select Maintenance Orders",
        options=list(options.keys()),
        size=8,
    )

    output = pn.Column()

    def run(event=None):
        output.objects = []
        selected = select.value or []
        if not selected:
            output.objects = [pn.pane.Markdown("**Select at least one record.**")]
            return

        for desc in selected:
            activity_id = options.get(desc)
            if not activity_id:
                continue

            activity = fetch_activity(token, activity_id)
            notes_direct = activity.get("Notes")
            notes_html = parse_register(activity.get("Register", ""))

            section = pn.Column(
                pn.pane.Markdown(f"#### Activity: {activity_id}"),
                pn.pane.Markdown("**Notes:**"),
                pn.pane.Markdown(notes_direct if notes_direct else "_None_"),
                pn.pane.Markdown("**Register Notes:**"),
                pn.pane.Markdown("\n".join(f"- {n}" for n in notes_html) if notes_html else "_None_"),
                pn.layout.Divider(),
            )
            output.append(section)

    run_btn = pn.widgets.Button(name="Fetch Notes", button_type="primary")
    run_btn.on_click(run)

    return pn.Column(
        title,
        select,
        run_btn,
        output,
        sizing_mode="stretch_width",
    )
