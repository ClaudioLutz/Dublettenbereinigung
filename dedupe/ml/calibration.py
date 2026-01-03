"""
Model calibration for well-calibrated confidence scores.

Provides isotonic regression calibration to ensure predicted probabilities
match true match probabilities.
"""

import joblib
import logging
from pathlib import Path
from typing import Tuple

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

logger = logging.getLogger(__name__)


class ModelCalibrator:
    """
    Calibrate model probabilities using isotonic regression.

    Ensures that predicted probabilities are well-calibrated to true
    match probabilities, which is critical for precision-focused matching.
    """

    def __init__(self, out_of_bounds: str = 'clip'):
        """
        Initialize calibrator.

        Args:
            out_of_bounds: How to handle out-of-bounds predictions
                          ('clip' or 'raise')
        """
        self.calibrator = IsotonicRegression(
            out_of_bounds=out_of_bounds,
            y_min=0.0,
            y_max=1.0,
        )
        self.is_fitted = False

    def fit(self, y_pred: np.ndarray, y_true: np.ndarray):
        """
        Fit calibrator on validation predictions.

        Args:
            y_pred: Uncalibrated predictions (n_samples,)
            y_true: True labels (n_samples,)
        """
        logger.info("Fitting isotonic regression calibrator...")

        self.calibrator.fit(y_pred, y_true)
        self.is_fitted = True

        # Compute calibration metrics
        brier_before = brier_score_loss(y_true, y_pred)
        y_pred_calibrated = self.calibrator.predict(y_pred)
        brier_after = brier_score_loss(y_true, y_pred_calibrated)

        logger.info(f"Brier score before calibration: {brier_before:.4f}")
        logger.info(f"Brier score after calibration:  {brier_after:.4f}")
        logger.info(f"Improvement: {brier_before - brier_after:.4f}")

    def transform(self, y_pred: np.ndarray) -> np.ndarray:
        """
        Apply calibration to predictions.

        Args:
            y_pred: Uncalibrated predictions (n_samples,)

        Returns:
            Calibrated predictions (n_samples,)
        """
        if not self.is_fitted:
            raise RuntimeError("Calibrator not fitted. Call fit() first.")

        return self.calibrator.predict(y_pred)

    def fit_transform(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
    ) -> np.ndarray:
        """
        Fit calibrator and transform predictions.

        Args:
            y_pred: Uncalibrated predictions
            y_true: True labels

        Returns:
            Calibrated predictions
        """
        self.fit(y_pred, y_true)
        return self.transform(y_pred)

    def evaluate_calibration(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
        n_bins: int = 10,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Evaluate calibration quality.

        Args:
            y_pred: Predictions to evaluate
            y_true: True labels
            n_bins: Number of bins for calibration curve

        Returns:
            Tuple of (fraction_of_positives, mean_predicted_value)
        """
        return calibration_curve(y_true, y_pred, n_bins=n_bins)

    def save(self, output_path: str):
        """
        Save calibrator to disk.

        Args:
            output_path: Path to save calibrator
        """
        if not self.is_fitted:
            raise RuntimeError("Calibrator not fitted.")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(self.calibrator, output_path)
        logger.info(f"Calibrator saved to {output_path}")

    @classmethod
    def load(cls, input_path: str) -> 'ModelCalibrator':
        """
        Load calibrator from disk.

        Args:
            input_path: Path to saved calibrator

        Returns:
            ModelCalibrator instance
        """
        calibrator = joblib.load(input_path)

        instance = cls()
        instance.calibrator = calibrator
        instance.is_fitted = True

        logger.info(f"Calibrator loaded from {input_path}")

        return instance
