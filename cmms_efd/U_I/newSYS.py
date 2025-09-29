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

import streamlit as st
import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_loader import read_config_from_db, insert_config, update_config
from dotenv import load_dotenv
load_dotenv()

AUTH_URL = os.getenv("AUTH_URL")
URL_ASSET_CARD = os.getenv("URL_ASSET_CARD")
CMMS_USERNAME = os.getenv("CMMS_USERNAME")
CMMS_PASSWORD = os.getenv("CMMS_PASSWORD")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)


def save_entry_streamlit(entry):
    existing_names = [c["name"] for c in read_config_from_db()]
    if entry["name"] in existing_names:
        update_config(entry)
        st.success(f"Configuration updated: {entry['name']}")
    else:
        insert_config(entry)
        st.success(f"Configuration inserted: {entry['name']}")


def show_entries_streamlit():
    config = read_config_from_db()
    if config:
        st.table([{k: v for k, v in item.items()
                  if k in ["name", "measurement", "field", "asset_id", "attribute"]}
                 for item in config])
    else:
        st.info("No saved configurations found.")
    return config


def create_ui():
    st.header("New SYS Configuration")
    configs = read_config_from_db()
    config_names = [""] + [c["name"] for c in configs] if configs else [""]
    selected_name = st.selectbox("Select configuration to edit", config_names)
    if st.button("Load Configuration") and selected_name:
        selected_entry = next((c for c in configs if c["name"] == selected_name), {})
        st.session_state.current_entry = selected_entry
    current_entry = st.session_state.get("current_entry", {})

    name = st.text_input("Descriptive Name", value=current_entry.get("name", ""))
    measurement = st.text_input("Measurement", value=current_entry.get("measurement", ""))
    field = st.text_input("Field", value=current_entry.get("field", ""))
    asset_id = st.text_input("Asset ID", value=current_entry.get("asset_id", ""))
    attribute = st.text_input("Attribute", value=current_entry.get("attribute", ""))
    db_name = st.text_input("Database Name", value=current_entry.get("db_name", ""))
    time_interval = st.text_input("Time Interval", value=current_entry.get("time_interval", "24h"))
    sal_index = st.text_input("SAL Index (optional)", value=str(current_entry.get("salIndex", "")))
    type_telemetry = st.text_input("Telemetry Type", value=current_entry.get("type_telemetry", ""))

    entry = {
        "name": name,
        "measurement": measurement,
        "field": field,
        "asset_id": asset_id,
        "attribute": attribute,
        "db_name": db_name,
        "time_interval": time_interval,
        "salIndex": int(sal_index) if sal_index.isdigit() else None,
        "type_telemetry": type_telemetry
    }

    if st.button("Save Configuration"):
        save_entry_streamlit(entry)

   
    st.subheader("Saved Configurations")
    show_entries_streamlit()
