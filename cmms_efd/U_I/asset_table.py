# asset_table.py (Streamlit version)
import os
import requests
import streamlit as st
from dotenv import load_dotenv
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import read_config_from_db

load_dotenv()

ASSET_ENDPOINT = os.getenv("CMMS_ASSET_ENDPOINT")
USERNAME = os.getenv("CMMS_USERNAME")
PASSWORD = os.getenv("CMMS_PASSWORD")
AUTH_URL = os.getenv("AUTH_URL")


def get_token():
    """Authenticate and return CMMS token or None."""
    if not AUTH_URL or not USERNAME or not PASSWORD:
        st.error("AUTH_URL, CMMS_USERNAME or CMMS_PASSWORD not set in .env")
        return None
    try:
        resp = requests.post(AUTH_URL, json={"username": USERNAME,
                                             "password": PASSWORD},
                                             timeout=10,
                                             verify=False)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("_id")
    except Exception as e:
        st.error(f"Authentication failed: {e}")
        return None


def get_asset_details(token, asset_id):
    """Fetch asset detail endpoint /assets/{id} and return the 'data' dict or None."""
    try:
        headers = {"Content-Type": "application/json", "CMDBuild-Authorization": str(token)}
        url = f"{ASSET_ENDPOINT.rstrip('/')}/{asset_id}"
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception:
        return None


def format_cmms_value(details: dict, attribute: str) -> str:
    """Extract the attribute value from CMMS asset details. If not found, return 'N/A'."""
    if not details or not isinstance(details, dict):
        return "N/A"
    if attribute in details:
        return str(details[attribute])
    for k, v in details.items():
        if k.lower() == attribute.lower():
            return str(v)
    return "N/A"


def create_ui():
    """Build the Assets UI in Streamlit."""
    st.header("CMMS Assets Viewer")

    if st.button("Load Assets"):
        token = get_token()
        if not token:
            return

        try:
            configs = read_config_from_db()
        except Exception as e:
            st.error(f"Failed to read local DB: {e}")
            return

        if not configs:
            st.info("No configs found in DB")
            return

        table_data = []
        for entry in configs:
            asset_id = entry.get("asset_id")
            name = entry.get("name", "")
            attribute = entry.get("attribute", "")

            details = get_asset_details(token, asset_id)
            cmms_value = format_cmms_value(details, attribute)

            table_data.append({
                "ID": asset_id,
                "Name": name,
                "Attribute": attribute,
                "CMMS Value": cmms_value
            })

        st.table(table_data)


if __name__ == "__main__":
    create_ui()

