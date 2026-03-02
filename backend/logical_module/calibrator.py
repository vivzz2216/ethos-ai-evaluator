"""
Signal Calibrator — maps raw model signals to calibrated probabilities.

Two strategies:
  1. IsotonicRegression calibrator (non-parametric, better for non-monotone data)
  2. TemperatureScaler (Platt scaling, single parameter)

Both use scikit-learn and degrade gracefully to identity mapping when unfitted.
"""
from __future__ import annotations

import json
import logging
import math
import os
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.isotonic import IsotonicRegression  # type: ignore
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    IsotonicRegression = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# Isotonic Regression Calibrator
# ─────────────────────────────────────────────────────────────────────────────

class SignalCalibrator:
    """
    Per-signal isotonic regression calibrator.

    Maps a raw signal value (e.g., NLL-derived token confidence) to a
    calibrated probability of correctness.

    Usage:
        cal = SignalCalibrator(name="token_confidence")
        cal.fit(raw_scores, correctness_labels)   # once, on held-out data
        p = cal.predict(0.72)                     # at inference time

    If never fitted, predict() returns the raw value unchanged (identity).
    """

    def __init__(self, name: str = "signal") -> None:
        self.name = name
        self._fitted = False
        self._model: Optional[IsotonicRegression] = None
        self._x_min: float = 0.0
        self._x_max: float = 1.0

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, raw_scores: List[float], correctness_labels: List[float]) -> "SignalCalibrator":
        """
        Fit the calibrator on validation data.

        Args:
            raw_scores:          Raw signal values in [0,1] from model.
            correctness_labels:  Binary (0 = wrong, 1 = correct) labels.

        Returns:
            self (for chaining)
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available; calibrator will use identity mapping.")
            return self

        X = np.array(raw_scores, dtype=float)
        y = np.array(correctness_labels, dtype=float)

        if len(X) < 5:
            logger.warning("Too few samples to fit calibrator (%d < 5); using identity.", len(X))
            return self

        self._x_min = float(X.min())
        self._x_max = float(X.max())

        model = IsotonicRegression(y_min=1e-7, y_max=1.0 - 1e-7, out_of_bounds="clip")
        model.fit(X, y)
        self._model = model
        self._fitted = True
        logger.info("SignalCalibrator '%s' fitted on %d samples.", self.name, len(X))
        return self

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------

    def predict(self, raw_score: float) -> float:
        """Return calibrated probability in (0, 1)."""
        if not self._fitted or self._model is None:
            # Identity mapping — clamp to avoid log(0) in fusion
            return float(np.clip(raw_score, 1e-7, 1.0 - 1e-7))

        x = np.array([[raw_score]], dtype=float).ravel()
        p = float(self._model.predict(x)[0])
        return float(np.clip(p, 1e-7, 1.0 - 1e-7))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Persist calibrator to JSON (approximate: stores the fitted X/Y pairs)."""
        if not self._fitted or self._model is None:
            logger.warning("Calibrator '%s' not fitted; nothing to save.", self.name)
            return

        payload = {
            "name": self.name,
            "fitted": True,
            "x": self._model.X_thresholds_.tolist(),
            "y": self._model.y_thresholds_.tolist(),
            "x_min": self._x_min,
            "x_max": self._x_max,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(payload, f)
        logger.info("Calibrator '%s' saved to %s.", self.name, path)

    def load(self, path: str) -> "SignalCalibrator":
        """Load a previously saved calibrator."""
        if not os.path.exists(path):
            logger.warning("Calibrator file not found: %s", path)
            return self

        if not SKLEARN_AVAILABLE:
            return self

        with open(path) as f:
            payload = json.load(f)

        X = np.array(payload["x"])
        Y = np.array(payload["y"])
        model = IsotonicRegression(y_min=1e-7, y_max=1.0 - 1e-7, out_of_bounds="clip")
        model.fit(X, Y)
        self._model = model
        self._fitted = bool(payload.get("fitted", True))
        self._x_min = payload.get("x_min", 0.0)
        self._x_max = payload.get("x_max", 1.0)
        self.name = payload.get("name", self.name)
        logger.info("Calibrator '%s' loaded from %s.", self.name, path)
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Temperature Scaler (Platt Scaling)
# ─────────────────────────────────────────────────────────────────────────────

class TemperatureScaler:
    """
    Single-parameter Platt scaling (temperature scaling).

    Finds a scalar T that minimises NLL on validation data:
        p_calibrated = σ(logit(p_raw) / T)

    When not fitted, T defaults to 1.0 (identity).

    Fitting uses a simple grid search over T ∈ [0.1, 5.0].
    """

    def __init__(self, name: str = "temperature_scaler") -> None:
        self.name = name
        self.temperature: float = 1.0
        self._fitted = False

    # ------------------------------------------------------------------

    def _sigmoid(self, x: float) -> float:
        """Numerically stable sigmoid."""
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        e = math.exp(x)
        return e / (1.0 + e)

    def _logit(self, p: float) -> float:
        p = float(np.clip(p, 1e-7, 1.0 - 1e-7))
        return math.log(p / (1.0 - p))

    def _nll(self, T: float, logits: np.ndarray, labels: np.ndarray) -> float:
        """Negative log-likelihood for temperature T."""
        scaled = logits / T
        probs = np.array([self._sigmoid(float(s)) for s in scaled])
        probs = np.clip(probs, 1e-7, 1.0 - 1e-7)
        return float(-np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs)))

    # ------------------------------------------------------------------

    def fit(self, raw_scores: List[float], correctness_labels: List[float]) -> "TemperatureScaler":
        """Grid-search for optimal temperature on validation set."""
        X = np.array(raw_scores, dtype=float)
        y = np.array(correctness_labels, dtype=float)

        if len(X) < 5:
            logger.warning("TemperatureScaler '%s': too few samples (%d < 5).", self.name, len(X))
            return self

        logits = np.array([self._logit(float(p)) for p in X])
        grid = np.linspace(0.1, 5.0, 50)
        best_T = 1.0
        best_nll = float("inf")
        for T in grid:
            nll = self._nll(T, logits, y)
            if nll < best_nll:
                best_nll = nll
                best_T = float(T)

        self.temperature = best_T
        self._fitted = True
        logger.info("TemperatureScaler '%s' fitted: T=%.4f (NLL=%.4f).", self.name, best_T, best_nll)
        return self

    def predict(self, raw_score: float) -> float:
        """Return temperature-scaled probability."""
        if not self._fitted:
            return float(np.clip(raw_score, 1e-7, 1.0 - 1e-7))
        logit = self._logit(raw_score)
        return float(np.clip(self._sigmoid(logit / self.temperature), 1e-7, 1.0 - 1e-7))
