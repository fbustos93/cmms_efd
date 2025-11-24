# import_excel_panel.py
from __future__ import annotations

import os
import sys
from typing import List, Dict, Any

import pandas as pd
import panel as pn
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.logger_setup import logger, LOG_TIME_FORMAT
from config_loader import read_config_from_db

load_dotenv()


def import_from_excel(file_path: str) -> pd.DataFrame:
    """
    Load data from an Excel file into a DataFrame.

    Parameters
    ----------
    file_path : str
        Local path of the file.

    Returns
    -------
    pandas.DataFrame
        Imported table or empty DataFrame if import fails.
    """
    try:
        df = pd.read_excel(file_path)
        logger.info(f"{LOG_TIME_FORMAT()} Imported Excel file: {file_path}")
        return df
    except Exception as exc:
        logger.error(f"{LOG_TIME_FORMAT()} Excel import failed: {exc}", exc_info=True)
        return pd.DataFrame()


def create_panel() -> pn.Column:
    """
    Construct the Panel UI for importing and previewing Excel configuration data.

    Returns
    -------
    pn.Column
        Layout containing upload widget and preview table.
    """
    title = pn.pane.Markdown("### Import Excel Data")
    table_placeholder = pn.Spacer(height=10)

    upload = pn.widgets.FileInput(accept=".xlsx,.xls")

    def handle_upload(event=None) -> None:
        if not upload.value:
            table_placeholder.objects = [pn.pane.Markdown("**No file selected.**")]
            return

        file_path = upload.filename
        try:
            with open(file_path, "wb") as f:
                f.write(upload.value)
        except Exception:
            table_placeholder.objects = [pn.pane.Markdown("**Failed to save uploaded file**", style={"color": "red"})]
            return

        df = import_from_excel(file_path)
        if df.empty:
            table_placeholder.objects = [pn.pane.Markdown("**The file is empty or invalid.**")]
            return

        preview = df.head(50).fillna("")
        cols = [c for c in preview.columns if c in ("name", "measurement", "field", "attribute")]

        if not cols:
            table_placeholder.objects = [pn.pane.Markdown("**No configuration fields found in the file.**")]
            return

        table_placeholder.objects = [
            pn.widgets.Tabulator(preview[cols], height=350, layout="fit_data_stretch")
        ]
        logger.info(f"{LOG_TIME_FORMAT()} Displayed preview of uploaded Excel data ({len(preview)} rows).")

    upload.param.watch(handle_upload, "value")

    def load_from_db(event=None) -> None:
        try:
            configs = read_config_from_db()
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} DB read error: {exc}", exc_info=True)
            table_placeholder.objects = [pn.pane.Markdown("**Failed to read configuration database.**")]
            return

        if not configs:
            table_placeholder.objects = [pn.pane.Markdown("**No stored configurations found.**")]
            return

        rows = [
            {
                "Name": c.get("name", ""),
                "Measurement": c.get("measurement", ""),
                "Field": c.get("field", ""),
                "Attribute": c.get("attribute", ""),
            }
            for c in configs
        ]

        df = pd.DataFrame(rows)
        table_placeholder.objects = [
            pn.widgets.Tabulator(df, height=350, layout="fit_data_stretch")
        ]
        logger.info(f"{LOG_TIME_FORMAT()} Displayed {len(rows)} DB configuration rows.")

    load_btn = pn.widgets.Button(name="Load Configurations from DB", button_type="primary")
    load_btn.on_click(load_from_db)

    return pn.Column(
        title,
        upload,
        load_btn,
        table_placeholder,
        sizing_mode="stretch_width",
    )
