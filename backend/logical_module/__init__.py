"""
ETHOS Logical Module — Confidence-Based Abstention Engine

Implements research-grounded confidence estimation combining:
  - Attention-weighted token entropy
  - Cluster-based self-consistency (HDBSCAN)
  - Outlier-penalized semantic coherence
  - Self-verification judge loop
  - Bayesian log-odds fusion
  - Expected-utility decision theory

Usage:
    from logical_module.api import LogicalModulePipeline

    pipeline = LogicalModulePipeline()
    result = pipeline.evaluate(model, tokenizer, prompt)
    # result["action"]     → "ANSWER" | "HEDGE" | "ABSTAIN"
    # result["confidence"] → float ∈ [0, 1]
    # result["response"]   → formatted response string
"""

from .confidence_estimator import ConfidenceEstimator
from .uncertainty_detector import UncertaintyDetector
from .abstention_policy import AbstentionPolicy, Action
from .logic_evaluator import SelfVerifier
from .calibrator import SignalCalibrator, TemperatureScaler
from .api import LogicalModulePipeline

__all__ = [
    "LogicalModulePipeline",
    "ConfidenceEstimator",
    "UncertaintyDetector",
    "AbstentionPolicy",
    "Action",
    "SelfVerifier",
    "SignalCalibrator",
    "TemperatureScaler",
]
