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

# newSYS_panel.py
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import panel as pn
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.logger_setup import logger, LOG_TIME_FORMAT
from config_loader import read_config_from_db, insert_config, update_config
from influx_query import EfdQueryClient

load_dotenv()


def save_entry(entry: Dict[str, Any]) -> None:
    """
    Insert or update a telemetry configuration.

    Parameters
    ----------
    entry : dict
        Configuration record.
    """
    try:
        if entry.get("id") is not None:
            update_config(entry)
        else:
            insert_config(entry)
        logger.info(f"{LOG_TIME_FORMAT()} Configuration saved: {entry.get('name','')}")
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Config save failure: {exc}", exc_info=True)


def create_panel() -> pn.Column:
    """
    Build Panel UI for EFD → CMMS configuration management.

    Returns
    -------
    pn.Column
        Panel layout containing create/update inputs and saved items list.
    """
    client = EfdQueryClient()

    title = pn.pane.Markdown("### New SYS Configuration")

    name = pn.widgets.TextInput(name="Name")
    asset_id = pn.widgets.TextInput(name="Asset ID")
    attribute = pn.widgets.TextInput(name="Attribute")
    db_name = pn.widgets.TextInput(name="Database Name")
    time_interval = pn.widgets.TextInput(name="Time Interval", value="24h")
    sal_index = pn.widgets.TextInput(name="SAL Index (optional)")
    telemetry_type = pn.widgets.TextInput(name="Telemetry Type")

    measurement = pn.widgets.Select(name="Measurement", options=[])
    field = pn.widgets.Select(name="Field", options=[])

    def load_measurements(event=None) -> None:
        try:
            measurements = client.get_measurements()
            measurement.options = {m: m for m in measurements}
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Measurement load failed: {exc}")

    def load_fields(event=None) -> None:
        if not measurement.value:
            return
        try:
            field.options = client.get_fields(measurement.value) or []
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Field load failed: {exc}")

    measurement.param.watch(load_fields, "value")

    configs_container = pn.Column()

    def refresh_configs(event=None) -> None:
        try:
            configs = read_config_from_db()
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Failed to read config DB: {exc}", exc_info=True)
            configs_container.objects = [pn.pane.Markdown("**Error loading stored configurations**")]
            return

        if not configs:
            configs_container.objects = [pn.pane.Markdown("No configurations stored.")]
            return

        rows = []
        for c in configs:
            row = pn.Row(
                pn.pane.Markdown(f"**[{c.get('id','?')}]** {c.get('name','')}"),
                pn.widgets.Button(name="Edit", button_type="warning", width=80,
                                  on_click=lambda event, data=c: open_editor(data)),
                sizing_mode="stretch_width",
            )
            rows.append(row)

        configs_container.objects = rows

    def save_current(event=None) -> None:
        entry = {
            "id": None,
            "name": name.value,
            "measurement": measurement.value,
            "field": field.value,
            "asset_id": asset_id.value,
            "attribute": attribute.value,
            "db_name": db_name.value,
            "time_interval": time_interval.value,
            "salIndex": int(sal_index.value) if sal_index.value.isdigit() else None,
            "type_telemetry": telemetry_type.value,
        }
        save_entry(entry)
        refresh_configs()

    def open_editor(data: Dict[str, Any]) -> None:
        dialog = pn.widgets.Dialog(width=420)

        e_name = pn.widgets.TextInput(name="Name", value=data.get("name", ""))
        e_asset = pn.widgets.TextInput(name="Asset ID", value=str(data.get("asset_id", "")))
        e_attr = pn.widgets.TextInput(name="Attribute", value=data.get("attribute", ""))
        e_db = pn.widgets.TextInput(name="Database Name", value=data.get("db_name", ""))
        e_ti = pn.widgets.TextInput(name="Time Interval", value=data.get("time_interval", "24h"))
        e_sal = pn.widgets.TextInput(name="SAL Index", value=str(data.get("salIndex", "") or ""))
        e_type = pn.widgets.TextInput(name="Telemetry Type", value=data.get("type_telemetry", ""))

        def apply_changes(event=None):
            payload = {
                "id": data.get("id"),
                "name": e_name.value,
                "asset_id": e_asset.value,
                "attribute": e_attr.value,
                "db_name": e_db.value,
                "time_interval": e_ti.value,
                "salIndex": int(e_sal.value) if e_sal.value.isdigit() else None,
                "type_telemetry": e_type.value,
                "measurement": data.get("measurement"),
                "field": data.get("field"),
            }
            save_entry(payload)
            dialog.close()
            refresh_configs()

        dialog_content = pn.Column(
            pn.pane.Markdown(f"#### Edit: {data.get('name','')}"),
            e_name, e_asset, e_attr, e_db, e_ti, e_sal, e_type,
            pn.Row(
                pn.widgets.Button(name="Save Changes", button_type="success", on_click=apply_changes),
                pn.widgets.Button(name="Cancel", button_type="default", on_click=lambda e=None: dialog.close()),
            ),
        )

        dialog.objects = [dialog_content]
        dialog.open()

    refresh_configs()

    return pn.Column(
        title,
        pn.Row(name, asset_id, attribute),
        pn.Row(db_name, time_interval, telemetry_type),
        pn.Row(sal_index),
        pn.Row(measurement, field),
        pn.Row(
            pn.widgets.Button(name="Load Measurements", button_type="primary", on_click=load_measurements),
            pn.widgets.Button(name="Save Configuration", button_type="success", on_click=save_current),
        ),
        pn.pane.Markdown("### Saved Configurations"),
        configs_container,
        sizing_mode="stretch_width",
    )
