from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

from backend.logger_setup import logger, LOG_TIME_FORMAT
from linear_regression_model import LinearRegressionModel
from config_loader import (
    init_ml_storage,
    save_ml_linear_model,
    load_latest_ml_linear_model,
)


def compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Compute the Root Mean Square Error (RMSE).

    Parameters
    ----------
    y_true : np.ndarray
        Ground-truth values.
    y_pred : np.ndarray
        Predicted values.

    Returns
    -------
    float
        RMSE value.
    """
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def compute_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Compute the coefficient of determination R^2.

    Parameters
    ----------
    y_true : np.ndarray
        Ground-truth values.
    y_pred : np.ndarray
        Model predictions.

    Returns
    -------
    float
        R^2 coefficient.
    """
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))

    if ss_tot == 0.0:
        return 0.0

    return float(1.0 - ss_res / ss_tot)


def _incremental_update(
    model: LinearRegressionModel,
    x: np.ndarray,
    y: np.ndarray,
    lr: float = 1e-6
) -> LinearRegressionModel:
    """
    Incrementally update slope and intercept using gradient descent.

    Parameters
    ----------
    model : LinearRegressionModel
        Previously learned model.
    x : np.ndarray
        Time values in seconds.
    y : np.ndarray
        Target telemetry values.
    lr : float
        Learning rate for gradient descent.

    Returns
    -------
    LinearRegressionModel
        Updated model instance.
    """
    y_pred = model.slope * x + model.intercept
    error = y - y_pred

    grad_slope = (-2.0 / len(x)) * np.sum(x * error)
    grad_intercept = (-2.0 / len(x)) * np.sum(error)

    new_slope = model.slope - lr * grad_slope
    new_intercept = model.intercept - lr * grad_intercept

    logger.info(
        f"{LOG_TIME_FORMAT()} ML: incremental update | "
        f"grad_slope={grad_slope:.6f}, grad_intercept={grad_intercept:.6f}"
    )

    return LinearRegressionModel(
        slope=float(new_slope),
        intercept=float(new_intercept)
    )


def train_linear_regression(
    df: pd.DataFrame,
    measurement: str,
    field: str
) -> Optional[LinearRegressionModel]:
    """
    Hybrid machine learning training pipeline:
    (1) Online incremental learning for small batches.
    (2) Full re-training using polyfit when batch size is large.

    The model is only saved when improvement is detected.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame with timestamps and the target field.
    measurement : str
        EFD measurement name.
    field : str
        Telemetry variable to learn.

    Returns
    -------
    LinearRegressionModel or None
        The best model after evaluation.
    """
    if df.empty or field not in df.columns:
        logger.info(f"{LOG_TIME_FORMAT()} ML: invalid DataFrame")
        return None

    df = df.copy()
    df = df.dropna(subset=[field])

    if df.empty:
        logger.info(f"{LOG_TIME_FORMAT()} ML: no valid target values")
        return None

    if "timestamp" not in df.columns:
        if "time" in df.columns:
            df = df.rename(columns={"time": "timestamp"})
        else:
            logger.info(f"{LOG_TIME_FORMAT()} ML: missing timestamp column")
            return None

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])

    if df.empty:
        logger.info(f"{LOG_TIME_FORMAT()} ML: no valid timestamps")
        return None

    t0 = df["timestamp"].min()
    df["t_sec"] = (df["timestamp"] - t0).dt.total_seconds()

    x = df["t_sec"].astype(float).values
    y = df[field].astype(float).values

    if x.size < 5:
        logger.info(f"{LOG_TIME_FORMAT()} ML: insufficient samples (<5)")
        return None

    previous = load_latest_ml_linear_model(measurement, field)

    if previous is not None:
        old_slope, old_intercept = previous
        previous_model = LinearRegressionModel(
            slope=float(old_slope),
            intercept=float(old_intercept)
        )
        logger.info(
            f"{LOG_TIME_FORMAT()} ML: loaded previous model | "
            f"slope={old_slope:.6f}, intercept={old_intercept:.6f}"
        )
    else:
        previous_model = None
        logger.info(f"{LOG_TIME_FORMAT()} ML: no previous model available")

    if 5 <= x.size < 50:
        if previous_model is None:
            logger.info(f"{LOG_TIME_FORMAT()} ML: incremental bootstrap (no previous model)")
            slope, intercept = np.polyfit(x, y, 1)
            new_model = LinearRegressionModel(slope=float(slope), intercept=float(intercept))
        else:
            logger.info(f"{LOG_TIME_FORMAT()} ML: performing incremental learning")
            new_model = _incremental_update(previous_model, x, y, lr=1e-6)
    else:
        logger.info(f"{LOG_TIME_FORMAT()} ML: performing full batch re-training")
        slope, intercept = np.polyfit(x, y, 1)
        new_model = LinearRegressionModel(slope=float(slope), intercept=float(intercept))

    logger.info(
        f"{LOG_TIME_FORMAT()} ML: new model parameters | "
        f"slope={new_model.slope:.6f}, intercept={new_model.intercept:.6f}"
    )

    new_pred = new_model.slope * x + new_model.intercept
    new_rmse = compute_rmse(y, new_pred)
    new_r2 = compute_r2(y, new_pred)

    logger.info(f"{LOG_TIME_FORMAT()} ML: new model RMSE={new_rmse:.6f}")
    logger.info(f"{LOG_TIME_FORMAT()} ML: new model R2={new_r2:.6f}")

    if previous_model is not None:
        old_pred = previous_model.slope * x + previous_model.intercept
        old_rmse = compute_rmse(y, old_pred)
        old_r2 = compute_r2(y, old_pred)

        logger.info(f"{LOG_TIME_FORMAT()} ML: previous model RMSE={old_rmse:.6f}")
        logger.info(f"{LOG_TIME_FORMAT()} ML: previous model R2={old_r2:.6f}")

        if new_rmse >= old_rmse:
            logger.info(f"{LOG_TIME_FORMAT()} ML: new model rejected (worse RMSE)")
            return previous_model

    init_ml_storage()
    save_ml_linear_model(measurement, field, new_model.slope, new_model.intercept)

    logger.info(f"{LOG_TIME_FORMAT()} ML: new model accepted and saved")
    return new_model
