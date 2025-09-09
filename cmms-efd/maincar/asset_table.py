import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from dotenv import load_dotenv

from config_loader import read_config_from_db

load_dotenv()

ASSET_ENDPOINT = os.getenv("CMMS_ASSET_ENDPOINT")
USERNAME = os.getenv("CMMS_USERNAME")
PASSWORD = os.getenv("CMMS_PASSWORD")
AUTH_URL = os.getenv("AUTH_URL")


def get_token():
    """Authenticate and return CMMS token or None."""
    if not AUTH_URL or not USERNAME or not PASSWORD:
        messagebox.showerror("Configuration Error","AUTH_URL, CMMS_USERNAME or CMMS_PASSWORD not set in .env")
        return None
    try:
        resp = requests.post(AUTH_URL, json={"username": USERNAME,
                                             "password": PASSWORD},
                                             timeout=10,
                                             verify=False)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("_id")
    except Exception as e:
        messagebox.showerror("Auth Error", f"Authentication failed: {e}")
        return None


def get_asset_details(token, asset_id):
    """Fetch asset detail endpoint /assets/{id}
    and return the 'data' dict or None."""
    try:
        headers = {"Content-Type": "application/json", "CMDBuild-Authorization": str(token)}
        url = f"{ASSET_ENDPOINT.rstrip('/')}/{asset_id}"
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception:
        return None


def format_cmms_value(details: dict, attribute: str) -> str:
    """
    Extract the attribute value from CMMS asset details.
    If not found, return "N/A".
    """
    if not details or not isinstance(details, dict):
        return "N/A"

    if attribute in details:
        return str(details[attribute])

    for k, v in details.items():
        if k.lower() == attribute.lower():
            return str(v)

    return "N/A"


def create_ui(parent):
    """
    Build the Assets UI: shows ID, Name, Attribute, and current CMMS_value.
    """
    frame = ttk.Frame(parent, padding=10)
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, columns=("ID", "Name", "Attribute", "CMMS_value"), show="headings")
    tree.heading("ID", text="ID")
    tree.heading("Name", text="Name")
    tree.heading("Attribute", text="Attribute")
    tree.heading("CMMS_value", text="CMMS value")
    tree.column("ID", width=150)
    tree.column("Name", width=250)
    tree.column("Attribute", width=200)
    tree.column("CMMS_value", width=300)
    tree.pack(fill="both", expand=True, pady=5)

    status_label = ttk.Label(frame, text="")
    status_label.pack(pady=(4, 0))

    def clear_table():
        for r in tree.get_children():
            tree.delete(r)

    def load_assets():
        """Start background thread to load assets and their CMMS values."""
        status_label.config(text="Loading...")
        clear_table()
        threading.Thread(target=_load_assets_thread, daemon=True).start()

    def _load_assets_thread():
        token = get_token()
        if not token:
            parent.after(0, lambda: status_label.config(text="Authentication failed"))
            return

        try:
            configs = read_config_from_db()
        except Exception as e:  # noqa: F841
            parent.after(0, lambda: status_label.config(text=f"Failed to read local DB: {e}"))  # noqa: F821
            return

        if not configs:
            parent.after(0, lambda: status_label.config(text="No configs found in DB"))
            return

        for entry in configs:
            asset_id = entry.get("asset_id")
            name = entry.get("name", "")
            attribute = entry.get("attribute", "")

            details = get_asset_details(token, asset_id)
            cmms_value = format_cmms_value(details, attribute)

            parent.after(
                0,
                lambda aid=asset_id, nm=name, att=attribute, cv=cmms_value:
                tree.insert("", "end", values=(aid, nm, att, cv))
            )

        parent.after(0, lambda: status_label.config(text=f"Loaded {len(configs)} assets"))

    load_button = ttk.Button(frame, text="Load Assets", command=load_assets)
    load_button.pack(pady=5)

    return frame


if __name__ == "__main__":
    root = tk.Tk()
    root.title("CMMS Assets Viewer")
    root.geometry("1000x600")
    create_ui(root)
    root.mainloop()
