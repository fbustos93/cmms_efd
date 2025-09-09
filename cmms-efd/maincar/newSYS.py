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
import tkinter as tk
from tkinter import ttk
import requests
import logging
from dotenv import load_dotenv

from config_loader import read_config_from_db, insert_config, update_config

load_dotenv()

AUTH_URL = os.getenv("AUTH_URL")
URL_ASSET_CARD = os.getenv("URL_ASSET_CARD")
CMMS_USERNAME = os.getenv("CMMS_USERNAME")
CMMS_PASSWORD = os.getenv("CMMS_PASSWORD")

REQUIRED_COLUMNS = {
    "name", "measurement", "field", "asset_id", "attribute",
    "db_name", "time_interval", "type_telemetry"
}
COLUMNS_TO_DISPLAY = ("name", "measurement", "field", "current_value")
field_vars = {}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)


def save_entry():
    """Save or update a configuration record."""
    entry = {k.replace("_var", ""): v.get() for k, v in field_vars.items() if k != "sal_index_var"}

    sal_index = field_vars["sal_index_var"].get()
    if sal_index:
        try:
            entry["salIndex"] = int(sal_index)
        except ValueError:
            logger.warning("SAL Index must be an integer.")
            return

    existing_names = [c["name"] for c in read_config_from_db()]
    if entry["name"] in existing_names:
        update_config(entry)
        logger.info(f"Configuration updated: {entry['name']}")
    else:
        insert_config(entry)
        logger.info(f"Configuration inserted: {entry['name']}")

    clear_fields()


def clear_fields():
    """Clear all form input fields."""
    for var in field_vars.values():
        var.set("")


def show_entries(parent):
    """Display saved configurations in a listbox with edit option."""
    top = tk.Toplevel(parent)
    top.title("Saved Configurations")
    top.geometry("800x400")

    listbox = tk.Listbox(top, width=100)
    listbox.pack(padx=10, pady=10, fill="both", expand=True)

    config = read_config_from_db()
    for idx, item in enumerate(config):
        display = f"{idx + 1}. {item.get('name', '[no name]')} | {item['measurement']} → {item['field']}"
        listbox.insert(tk.END, display)

    def edit_selected():
        sel = listbox.curselection()
        if not sel:
            logger.warning("No configuration selected for editing.")
            return
        load_for_editing(sel[0])

    ttk.Button(top, text="Edit", command=edit_selected).pack(pady=5)


def load_for_editing(index):
    """Load a configuration into the form for editing."""
    item = read_config_from_db()[index]
    for key, var in field_vars.items():
        var.set(str(item.get(key.replace("_var", ""), "")))


def authenticate_cmms():
    """Authenticate to CMMS and return session token."""
    if not AUTH_URL:
        logger.error("AUTH_URL not defined in environment.")
        return None

    try:
        headers = {"Content-Type": "application/json"}
        credentials = {"username": CMMS_USERNAME, "password": CMMS_PASSWORD}
        response = requests.post(AUTH_URL, headers=headers, json=credentials, timeout=10, verify=False)
        response.raise_for_status()
        token = response.json().get("data", {}).get("_id")
        if not token:
            logger.error("Token not found in CMMS response.")
        return token
    except Exception as e:
        logger.error(f"CMMS authentication failed: {e}")
        return None


def get_current_value(token, asset_id, attribute):
    """Retrieve current telemetry value from CMMS."""
    try:
        url = URL_ASSET_CARD.replace("{asset_id}", str(asset_id))
        headers = {"CMDBuild-Authorization": token}
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        return response.json().get("data", {}).get(attribute)
    except Exception as e:
        logger.error(f"Error fetching value {asset_id}.{attribute}: {e}")
        return None


def show_current_values(parent):
    """Display current telemetry values for all entries."""
    token = authenticate_cmms()
    if not token:
        return

    config = read_config_from_db()

    win = tk.Toplevel(parent)
    win.title("Current Values in CMMS")
    win.geometry("900x400")

    tree = ttk.Treeview(win, columns=COLUMNS_TO_DISPLAY, show="headings")
    for col in COLUMNS_TO_DISPLAY:
        tree.heading(col, text=col.replace("_", " ").capitalize())
        tree.column(col, width=200)
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    for entry in config:
        value = get_current_value(token, entry["asset_id"], entry["attribute"])
        tree.insert("", "end", values=(
            entry.get("name", ""),
            entry.get("measurement", ""),
            entry.get("field", ""),
            value if value is not None else "N/A"
        ))


def create_ui(parent):
    """Build the NewSYS configuration UI."""
    global field_vars
    frame = ttk.Frame(parent, padding=10)
    frame.pack(fill="both", expand=True)

    field_vars = {
        "name_var": tk.StringVar(),
        "measurement_var": tk.StringVar(),
        "field_var": tk.StringVar(),
        "asset_id_var": tk.StringVar(),
        "attribute_var": tk.StringVar(),
        "db_name_var": tk.StringVar(),
        "time_interval_var": tk.StringVar(),
        "sal_index_var": tk.StringVar(),
        "type_telemetry_var": tk.StringVar(),
    }

    fields_order = [
        ("Descriptive Name", "name_var"),
        ("Measurement", "measurement_var"),
        ("Field", "field_var"),
        ("Asset ID", "asset_id_var"),
        ("Attribute", "attribute_var"),
        ("Database Name", "db_name_var"),
        ("Time Interval", "time_interval_var"),
        ("SAL Index (optional)", "sal_index_var"),
        ("Telemetry Type", "type_telemetry_var")
    ]

    for idx, (label, varname) in enumerate(fields_order):
        ttk.Label(frame, text=label).grid(row=idx, column=0, sticky="w", padx=10, pady=5)
        ttk.Entry(frame, textvariable=field_vars[varname], width=40).grid(row=idx, column=1, padx=10, pady=5)

    ttk.Button(frame, text="Save", command=save_entry).grid(row=len(fields_order), column=0, padx=10, pady=20)
    ttk.Button(frame, text="Show/Edit Configurations",
               command=lambda: show_entries(parent)).grid(row=len(fields_order), column=1, padx=10, pady=20)
    ttk.Button(frame, text="See Current Values",
               command=lambda: show_current_values(parent)).grid(row=len(fields_order) + 1, column=0,
                                                                 columnspan=2, pady=10)
    return frame

