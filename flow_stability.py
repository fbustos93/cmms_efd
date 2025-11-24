from __future__ import annotations

from typing import Any

import pandas as pd
from backend.logger_setup import logger, LOG_TIME_FORMAT
from predictive_learning import learn_baseline_from_series, compute_flow_thresholds


def run_flow_stability(
    df: pd.DataFrame,
    column: str,
    baseline_flow: float | None = None,
    warning_ratio: float = 0.8,
    critical_ratio: float = 0.6,
) -> dict[str, Any]:
    """
    Evaluate flow stability using rolling statistics and distribution percentiles.
    This function returns diagnostics and dynamic thresholds that can be used
    as trigger values for maintenance logic.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame containing timestamps and the selected telemetry field.
    column : str
        Data column to be analyzed.
    baseline_flow : float, optional
        Known nominal flow value. If None, a baseline is learned from the
        provided series using a percentile-based strategy.
    warning_ratio : float, optional
        Fraction of the baseline that defines the warning level.
    critical_ratio : float, optional
        Fraction of the baseline that defines the critical level.

    Returns
    -------
    dict
        Dictionary containing:
        - state               : qualitative state label
        - baseline_flow       : learned or provided baseline
        - warning_threshold   : flow value for warning state
        - critical_threshold  : flow value for critical state
        - rolling_mean        : rolling mean over the last window
        - rolling_std         : rolling standard deviation over the last window
        - percentile_10       : 10th percentile of the full series

    Notes
    -----
    This model evaluates:
    • Rolling mean (500 samples)
    • Rolling standard deviation (500 samples)
    • Percentile-10 of the full distribution

    States
    ------
    NORMAL:
        rolling_mean >= warning_threshold  and  percentile_10 >= warning_threshold
    DEGRADED:
        warning_threshold > rolling_mean >= critical_threshold
    APPROACHING LIMIT:
        rolling_mean < warning_threshold and rolling_mean > critical_threshold
    CRITICAL:
        rolling_mean <= critical_threshold
    """

    logger.info(f"{LOG_TIME_FORMAT()} FlowStability: starting analysis for '{column}'")

    result: dict[str, Any] = {
        "state": "UNKNOWN",
        "baseline_flow": None,
        "warning_threshold": None,
        "critical_threshold": None,
        "rolling_mean": None,
        "rolling_std": None,
        "percentile_10": None,
    }

    if df.empty:
        logger.info(f"{LOG_TIME_FORMAT()} FlowStability: empty DataFrame")
        result["state"] = "INSUFFICIENT_DATA"
        return result

    if column not in df.columns:
        logger.info(f"{LOG_TIME_FORMAT()} FlowStability: column '{column}' not present")
        result["state"] = "INVALID_COLUMN"
        return result

    series = df[column].astype(float).dropna()

    if series.empty:
        logger.info(f"{LOG_TIME_FORMAT()} FlowStability: series is empty after cleaning")
        result["state"] = "INSUFFICIENT_DATA"
        return result

    logger.info(f"{LOG_TIME_FORMAT()} FlowStability DEBUG — raw preview:")
    logger.info("\n" + str(series.head(10)))

    logger.info(
        f"{LOG_TIME_FORMAT()} FlowStability DEBUG — stats: "
        f"min={series.min()}, max={series.max()}, "
        f"mean={series.mean()}, std={series.std()}"
    )
    logger.info(
        f"{LOG_TIME_FORMAT()} FlowStability DEBUG — unique (first 5): "
        f"{series.unique()[:5]}"
    )

    if len(series) < 500:
        logger.info(f"{LOG_TIME_FORMAT()} FlowStability: insufficient samples (<500)")
        result["state"] = "INSUFFICIENT_DATA"
        return result

    # Baseline learning or usage
    if baseline_flow is None:
        logger.info(
            f"{LOG_TIME_FORMAT()} FlowStability: no baseline provided, "
            f"learning from data (p90 strategy)."
        )
        baseline = learn_baseline_from_series(series, method="p90")
    else:
        baseline = float(baseline_flow)
        logger.info(
            f"{LOG_TIME_FORMAT()} FlowStability: using provided baseline={baseline}"
        )

    thresholds = compute_flow_thresholds(
        baseline_flow=baseline,
        warning_ratio=warning_ratio,
        critical_ratio=critical_ratio,
    )
    warning_threshold = thresholds["warning_threshold"]
    critical_threshold = thresholds["critical_threshold"]

    # Rolling statistics
    rolling_mean = float(series.rolling(500).mean().iloc[-1])
    rolling_std = float(series.rolling(500).std().iloc[-1])
    percentile_10 = float(series.quantile(0.10))

    logger.info(f"{LOG_TIME_FORMAT()} FlowStability rolling_mean={rolling_mean}")
    logger.info(f"{LOG_TIME_FORMAT()} FlowStability rolling_std={rolling_std}")
    logger.info(f"{LOG_TIME_FORMAT()} FlowStability percentile_10={percentile_10}")

    # Classification
    if rolling_mean >= warning_threshold and percentile_10 >= warning_threshold:
        state = "NORMAL"
    elif warning_threshold > rolling_mean >= critical_threshold:
        state = "DEGRADED"
    elif rolling_mean < warning_threshold and rolling_mean > critical_threshold:
        state = "APPROACHING LIMIT"
    else:
        state = "CRITICAL — Maintenance Required"

    logger.info(f"{LOG_TIME_FORMAT()} FlowStability State: {state}")

    result.update(
        {
            "state": state,
            "baseline_flow": baseline,
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
            "rolling_mean": rolling_mean,
            "rolling_std": rolling_std,
            "percentile_10": percentile_10,
        }
    )
    return result
