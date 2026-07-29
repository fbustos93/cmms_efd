from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import panel as pn
from statsmodels.tsa.arima.model import ARIMA

from influx_query import EfdQueryClient
from config_loader_test import (
    insert_efd_point,
    list_measurements,
    list_fields,
    list_salindices,
    fetch_efd_series,
)

pn.extension()

_CLIENT = EfdQueryClient(results_as_dataframe=False)


def _fetch_efd_series_1h_all_history(
    measurement: str,
    field: str,
    sal_index: Optional[int],
) -> pd.DataFrame:
    if sal_index is not None:
        query = (
            f'SELECT mean("{field}") AS "value" '
            f'FROM "{measurement}" '
            f'WHERE time > 0 AND "salIndex" = {sal_index} '
            f'GROUP BY time(1h) fill(none) ORDER BY time ASC'
        )
    else:
        query = (
            f'SELECT mean("{field}") AS "value" '
            f'FROM "{measurement}" '
            f'WHERE time > 0 '
            f'GROUP BY time(1h) fill(none) ORDER BY time ASC'
        )

    raw = _CLIENT.query(query)
    block = raw.get("results", [{}])[0]

    if "series" not in block or not block["series"]:
        raise ValueError("No data returned from EFD.")

    series = block["series"][0]
    df = pd.DataFrame(series["values"], columns=series["columns"])
    df["timestamp"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["timestamp", "value"])
    return df[["timestamp", "value"]].reset_index(drop=True)


def _build_signal_id(measurement: str, field: str, sal_index: Optional[int]) -> str:
    if sal_index is None:
        return f"{measurement}.{field}"
    return f"{measurement}.{field}[{sal_index}]"


class TemperatureArimaEngine:
    def __init__(
        self,
        arima_order: Tuple[int, int, int] = (1, 1, 1),
        forecast_hours: int = 72,
    ) -> None:
        self.arima_order = arima_order
        self.forecast_hours = forecast_hours

    @staticmethod
    def _compute_threshold(values: pd.Series, manual: Optional[float]) -> float:
        if manual is not None:
            return float(manual)
        return float(values.mean() + 3.0 * values.std(ddof=0))

    def create_arima_plots_from_series(
        self,
        series: list[tuple[datetime, float]],
        threshold: Optional[float],
    ) -> tuple[plt.Figure, plt.Figure]:
        df = pd.DataFrame(series, columns=["timestamp", "value"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = (
            df.dropna()
            .set_index("timestamp")
            .resample("1H")
            .mean()
            .dropna()
            .reset_index()
        )

        if len(df) < 30:
            raise ValueError("Not enough historical data.")

        thr = self._compute_threshold(df["value"], threshold)

        fig_hist, ax_hist = plt.subplots(figsize=(12, 4))
        ax_hist.plot(df["timestamp"], df["value"])
        ax_hist.grid(True)
        ax_hist.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        fig_hist.autofmt_xdate()

        y = df["value"].astype(float).values
        fitted = ARIMA(y, order=self.arima_order).fit()
        forecast = fitted.get_forecast(steps=self.forecast_hours).predicted_mean

        future_index = pd.date_range(
            start=df["timestamp"].iloc[-1] + pd.Timedelta(hours=1),
            periods=self.forecast_hours,
            freq="1H",
        )

        fig_fore, ax_fore = plt.subplots(figsize=(12, 4))
        ax_fore.plot(
            df["timestamp"].iloc[-168:],
            df["value"].iloc[-168:],
            alpha=0.7,
        )
        ax_fore.plot(future_index, forecast)
        ax_fore.axhline(thr, linestyle="--")
        ax_fore.grid(True)
        ax_fore.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        fig_fore.autofmt_xdate()

        return fig_hist, fig_fore


def create_panel_app() -> pn.Column:
    engine = TemperatureArimaEngine()

    fetch_measurement = pn.widgets.TextInput(name="EFD Measurement")
    fetch_field = pn.widgets.TextInput(name="EFD Field")
    fetch_sal = pn.widgets.TextInput(name="SAL (optional)")
    btn_fetch = pn.widgets.Button(name="Fetch & Store", button_type="primary")
    fetch_status = pn.pane.Markdown("")

    meas_select = pn.widgets.Select(name="DB Measurement", options=[], disabled=True)
    field_select = pn.widgets.Select(name="DB Field", options=[], disabled=True)
    sal_select = pn.widgets.Select(name="DB salIndex", options=[], disabled=True)

    threshold_input = pn.widgets.TextInput(name="Failure threshold")
    btn_plot = pn.widgets.Button(
        name="Generate ARIMA Plots",
        button_type="success",
        disabled=True,
    )

    output = pn.Column()

    def _reload_sqlite():
        m_opts = list_measurements()
        meas_select.options = m_opts
        meas_select.disabled = not bool(m_opts)
        meas_select.value = m_opts[0] if m_opts else None

    def _refresh_fields(*_):
        f_opts = list_fields(meas_select.value)
        field_select.options = f_opts
        field_select.disabled = not bool(f_opts)
        field_select.value = f_opts[0] if f_opts else None

    def _refresh_sal(*_):
        s_opts = list_salindices(meas_select.value, field_select.value)
        sal_select.options = s_opts
        sal_select.disabled = not bool(s_opts)
        sal_select.value = s_opts[0] if s_opts else None
        btn_plot.disabled = not bool(s_opts)

    meas_select.param.watch(_refresh_fields, "value")
    field_select.param.watch(_refresh_sal, "value")

    def _on_fetch(event):
        fetch_status.object = "Fetch started"

        m = fetch_measurement.value_input.strip()
        f = fetch_field.value_input.strip()
        s = fetch_sal.value_input.strip()
        sal = int(s) if s.isdigit() else None

        df = _fetch_efd_series_1h_all_history(m, f, sal)
        signal_id = _build_signal_id(m, f, sal)

        for _, r in df.iterrows():
            insert_efd_point(
                signal_id=signal_id,
                measurement=m,
                field=f,
                salIndex=sal,
                time_utc=r["timestamp"].to_pydatetime(),
                value=float(r["value"]),
                resolution="1h",
            )

        fetch_status.object = f"Fetch completed ({len(df)} points)"
        _reload_sqlite()

    def _on_plot(event):
        series = fetch_efd_series(
            measurement=meas_select.value,
            field=field_select.value,
            salIndex=sal_select.value,
        )

        thr_raw = threshold_input.value.strip()
        thr_val = float(thr_raw) if thr_raw else None

        fig_hist, fig_fore = engine.create_arima_plots_from_series(series, thr_val)

        output.objects = [
            pn.pane.Matplotlib(fig_hist, height=300),
            pn.pane.Matplotlib(fig_fore, height=300),
        ]

    btn_fetch.on_click(_on_fetch)
    btn_plot.on_click(_on_plot)

    controls = pn.WidgetBox(
        fetch_measurement,
        fetch_field,
        fetch_sal,
        btn_fetch,
        fetch_status,
        meas_select,
        field_select,
        sal_select,
        threshold_input,
        btn_plot,
    )

    return pn.Column(controls, output)
