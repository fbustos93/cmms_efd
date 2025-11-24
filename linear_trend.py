from __future__ import annotations

import numpy as np
import pandas as pd
from backend.logger_setup import logger, LOG_TIME_FORMAT


def run_linear_trend(df: pd.DataFrame, column: str) -> None:
    """
    Perform a linear regression analysis on the selected telemetry field.
    This function estimates trend slope, intercept and goodness-of-fit (R²)
    and prints diagnostic details.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame containing timestamps and the selected field.
    column : str
        Name of the telemetry field to analyze.

    Notes
    -----
    The model applies a least-squares linear regression where:
    • x = elapsed seconds since first timestamp
    • y = telemetry field values

    Outputs
    -------
    • slope        : direction and intensity of the long-term trend
    • intercept    : regression line intercept
    • r2           : coefficient of determination (0–1)

    Interpretation
    --------------
    slope  > 0 : increasing trend
    slope  < 0 : decreasing trend
    r2 close to 1 : strong linear behavior
    r2 close to 0 : weak or noisy linear relation
    """

    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: starting analysis for '{column}'")

    if df.empty:
        logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: empty DataFrame")
        return

    if column not in df.columns:
        logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: column '{column}' not present")
        return

    df_local = df.copy().dropna(subset=[column])

    # Debug: preview
    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend DEBUG — raw preview:")
    logger.info("\n" + str(df_local[column].head(10)))

    # Debug: basic stats
    logger.info(
        f"{LOG_TIME_FORMAT()} LinearTrend DEBUG — stats: "
        f"min={df_local[column].min()}, max={df_local[column].max()}, "
        f"mean={df_local[column].mean()}, std={df_local[column].std()}"
    )
    logger.info(
        f"{LOG_TIME_FORMAT()} LinearTrend DEBUG — unique (first 5): "
        f"{df_local[column].unique()[:5]}"
    )

    if df_local.empty:
        logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: all values are NaN")
        return

    time_col = "time" if "time" in df_local.columns else "timestamp"
    df_local[time_col] = pd.to_datetime(df_local[time_col], utc=True, errors="coerce")
    df_local = df_local.dropna(subset=[time_col])

    if df_local.empty:
        logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: no valid timestamps")
        return

    t0 = df_local[time_col].min()
    df_local["t_sec"] = (df_local[time_col] - t0).dt.total_seconds()

    x = df_local["t_sec"].astype(float).values
    y = df_local[column].astype(float).values

    if x.size < 2:
        logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: insufficient samples (<2)")
        return

    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept

    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend: analysis completed")
    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend points={len(x)}")
    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend slope={slope}")
    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend intercept={intercept}")
    logger.info(f"{LOG_TIME_FORMAT()} LinearTrend r2={r2}")
