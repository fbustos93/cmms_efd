from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class LinearRegressionModel:
    """
    Linear regression model storing slope and intercept.

    Parameters
    ----------
    slope : float
        Learned slope of the regression.
    intercept : float
        Learned intercept of the regression.
    """

    slope: float
    intercept: float

    def predict(self, x_seconds: float) -> float:
        """
        Predict a future telemetry value using the linear regression model.

        Parameters
        ----------
        x_seconds : float
            Time offset in seconds from the reference timestamp.

        Returns
        -------
        float
            Predicted telemetry value.
        """
        return self.slope * x_seconds + self.intercept

    def update(
        self,
        x: np.ndarray,
        y: np.ndarray,
        lr: float = 1e-6
    ) -> None:
        """
        Incrementally update the model parameters using gradient descent.

        This method performs online learning, allowing the model to adjust its
        slope and intercept without full re-training. It is mathematically
        equivalent to performing one optimization step of linear regression.

        Parameters
        ----------
        x : numpy.ndarray
            Array of time values in seconds.
        y : numpy.ndarray
            Array of target telemetry values.
        lr : float
            Learning rate for gradient descent. Small values ensure stability.

        Returns
        -------
        None
            The model parameters (slope and intercept) are updated in-place.
        """
        y_pred = self.slope * x + self.intercept
        error = y - y_pred

        grad_slope = (-2.0 / len(x)) * np.sum(x * error)
        grad_intercept = (-2.0 / len(x)) * np.sum(error)

        self.slope -= lr * grad_slope
        self.intercept -= lr * grad_intercept

    def to_dict(self) -> dict[str, float]:
        """
        Export model parameters as a dictionary.

        Returns
        -------
        dict
            Dictionary with slope and intercept.
        """
        return {"slope": self.slope, "intercept": self.intercept}

    @staticmethod
    def from_dict(data: dict[str, float]) -> LinearRegressionModel:
        """
        Load a LinearRegressionModel from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary with keys 'slope' and 'intercept'.

        Returns
        -------
        LinearRegressionModel
        """
        return LinearRegressionModel(
            slope=float(data["slope"]),
            intercept=float(data["intercept"])
        )
