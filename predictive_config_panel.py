from __future__ import annotations

import os
import sys
from typing import Any

import pandas as pd
import panel as pn
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.logger_setup import logger, LOG_TIME_FORMAT
from influx_query import EfdQueryClient

from linear_trend import run_linear_trend
from flow_stability import run_flow_stability
from ML_trainer import train_linear_regression

load_dotenv()


def create_predictive_panel() -> pn.Column:
    """
    Build the predictive analysis configuration interface.

    This interface allows the user to select an EFD measurement, a field,
    a time window, and execute one of the available predictive models.

    Returns
    -------
    pn.Column
        Panel layout containing predictive configuration widgets.
    """

    client = EfdQueryClient()

    title = pn.pane.Markdown("### Predictive Analysis Configuration")

    measurement = pn.widgets.Select(name="Measurement", options=[])
    field = pn.widgets.Select(name="Field", options=[])

    time_value = pn.widgets.IntInput(name="Time Value", value=24, start=1)
    time_unit = pn.widgets.Select(
        name="Time Unit",
        options=["h", "d", "w"],
        value="h",
    )

    analysis_model = pn.widgets.Select(
        name="Analysis Model",
        options={
            "Linear Trend": "LinearTrend",
            "Flow Stability": "FlowStability",
            "Linear Regression ML": "LinearRegressionML",
        },
        value="LinearTrend",
    )

    def load_measurements(event: Any | None = None) -> None:
        try:
            measurements = client.get_measurements()
            measurement.options = measurements
            if measurements:
                measurement.value = measurements[0]
            logger.info(f"{LOG_TIME_FORMAT()} Measurements loaded")
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Measurement load failed: {exc}", exc_info=True)

    def load_fields(event: Any | None = None) -> None:
        if not measurement.value:
            return
        try:
            fields = client.get_fields(measurement.value) or []
            field.options = fields
            if fields:
                field.value = fields[0]
            logger.info(f"{LOG_TIME_FORMAT()} Fields loaded for {measurement.value}")
        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Field load failed: {exc}", exc_info=True)

    measurement.param.watch(load_fields, "value")

    def build_time_window() -> str:
        value = max(1, time_value.value)
        unit = time_unit.value
        return f"{value}{unit}"

    def run_analysis(event: Any | None = None) -> None:
        if not measurement.value or not field.value:
            logger.info(f"{LOG_TIME_FORMAT()} Missing measurement or field")
            return

        interval = build_time_window()

        try:
            influx_query = (
                f'SELECT "{field.value}" FROM "{measurement.value}" '
                f'WHERE time > now() - {interval}'
            )

            df = client.query(influx_query)

            if df.empty:
                logger.info(f"{LOG_TIME_FORMAT()} Query returned no data")
                return

            if "time" in df.columns and "timestamp" not in df.columns:
                df = df.rename(columns={"time": "timestamp"})

            model_name = analysis_model.value

            if model_name == "LinearTrend":
                run_linear_trend(df, field.value)

            elif model_name == "FlowStability":
                run_flow_stability(df, field.value)

            elif model_name == "LinearRegressionML":
                train_linear_regression(df, field.value)

            else:
                logger.info(f"{LOG_TIME_FORMAT()} Unknown model: {model_name}")

        except Exception as exc:
            logger.error(f"{LOG_TIME_FORMAT()} Analysis execution failed: {exc}", exc_info=True)

    load_button = pn.widgets.Button(
        name="Load Measurements",
        button_type="primary",
        width=160,
    )
    load_button.on_click(load_measurements)

    run_button = pn.widgets.Button(
        name="Run Analysis",
        button_type="success",
        width=160,
    )
    run_button.on_click(run_analysis)

    layout = pn.Column(
        title,
        pn.Row(measurement, field),
        pn.Row(time_value, time_unit, analysis_model),
        pn.Row(load_button, run_button),
        sizing_mode="stretch_width",
    )

    return layout
