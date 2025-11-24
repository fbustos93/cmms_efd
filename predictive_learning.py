from __future__ import annotations

from typing import Literal

import pandas as pd
from backend.logger_setup import logger, LOG_TIME_FORMAT


def learn_baseline_from_series(
    series: pd.Series,
    method: Literal["mean", "median", "p90"] = "p90",
) -> float:
    """
    Learn a baseline (normal operating level) from a telemetry series.

    Parameters
    ----------
    series : pandas.Series
        Input series with numeric values representing a stable period
        of normal operation.
    method : {'mean', 'median', 'p90'}, optional
        Statistical strategy used to estimate the baseline.

    Returns
    -------
    float
        Baseline value for the metric.

    Notes
    -----
    This function does not attempt to distinguish between healthy
    and faulty samples; it assumes the provided data corresponds
    to a normal operating regime.
    """
    clean = series.astype(float).dropna()

    if clean.empty:
        logger.info(f"{LOG_TIME_FORMAT()} Baseline learning: empty series")
        return 0.0

    if method == "mean":
        baseline = float(clean.mean())
    elif method == "median":
        baseline = float(clean.median())
    elif method == "p90":
        baseline = float(clean.quantile(0.90))
    else:
        baseline = float(clean.mean())

    logger.info(
        f"{LOG_TIME_FORMAT()} Baseline learning: method={method}, "
        f"baseline={baseline}"
    )
    return baseline


def learn_flow_baseline(
    df: pd.DataFrame,
    column: str,
    method: Literal["mean", "median", "p90"] = "p90",
) -> float:
    """
    Learn a baseline flow value for a given telemetry column.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing the telemetry field.
    column : str
        Column name to analyze.
    method : {'mean', 'median', 'p90'}, optional
        Statistical strategy used to estimate the baseline.

    Returns
    -------
    float
        Baseline flow value for the selected column.
    """
    if df.empty or column not in df.columns:
        logger.info(
            f"{LOG_TIME_FORMAT()} Flow baseline learning: "
            f"invalid DataFrame or missing column '{column}'"
        )
        return 0.0

    series = df[column].astype(float).dropna()
    return learn_baseline_from_series(series, method=method)


def compute_flow_thresholds(
    baseline_flow: float,
    warning_ratio: float = 0.8,
    critical_ratio: float = 0.6,
) -> dict:
    """
    Compute warning and critical thresholds from a baseline flow.

    Parameters
    ----------
    baseline_flow : float
        Nominal flow value representing healthy operation.
    warning_ratio : float, optional
        Fraction of the baseline that defines the warning level.
    critical_ratio : float, optional
        Fraction of the baseline that defines the critical level.

    Returns
    -------
    dict
        Dictionary containing baseline, warning_threshold and
        critical_threshold.

    Notes
    -----
    Typical values:
    - warning_ratio  ~ 0.8  (80% of baseline)
    - critical_ratio ~ 0.6  (60% of baseline)
    """
    baseline = float(max(baseline_flow, 0.0))
    warning_threshold = baseline * warning_ratio
    critical_threshold = baseline * critical_ratio

    logger.info(
        f"{LOG_TIME_FORMAT()} Flow thresholds: "
        f"baseline={baseline}, "
        f"warning_threshold={warning_threshold}, "
        f"critical_threshold={critical_threshold}"
    )

    return {
        "baseline_flow": baseline,
        "warning_threshold": warning_threshold,
        "critical_threshold": critical_threshold,
    }
