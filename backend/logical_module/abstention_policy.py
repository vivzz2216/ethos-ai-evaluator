"""
Abstention Policy — Bayesian log-odds fusion + Expected-Utility decision engine.

This module is the decision core of the Logical Module. It:

  1. Takes four calibrated signals: T, A, S, V (each ∈ [0, 1])
  2. Fuses them via Bayesian log-odds combination (not simple linear averaging)
  3. Applies cost-sensitive Expected-Utility theory to pick the action

Three possible actions:
  ANSWER  — respond normally (high confidence)
  HEDGE   — respond with explicit uncertainty caveat (medium confidence)
  ABSTAIN — decline to answer (low confidence)

Why Bayesian fusion beats linear averaging
==========================================
Linear averaging (C = α·T + β·A + …) has a ceiling: if all signals
are only moderately confident, the average stays moderate regardless of
how aligned they all are.  Log-odds fusion multiplies the *evidence*,
so four 0.70-probability signals correctly combine to > 0.90.

Why Expected Utility beats fixed thresholds
============================================
A fixed threshold like "ABSTAIN if C < 0.50" treats every domain
the same.  But a wrong medical answer is far worse than a wrong
trivia answer.  The cost matrix captures this: higher cost_wrong
for sensitive domains pulls the ABSTAIN threshold higher.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

from .calibrator import SignalCalibrator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Action enum
# ─────────────────────────────────────────────────────────────────────────────

class Action(str, Enum):
    ANSWER  = "ANSWER"   # Respond confidently
    HEDGE   = "HEDGE"    # Respond with explicit uncertainty caveat
    ABSTAIN = "ABSTAIN"  # Decline to answer

    @property
    def label(self) -> str:
        return self.value


# ─────────────────────────────────────────────────────────────────────────────
# Cost presets per domain
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DomainCosts:
    """
    Cost matrix for Expected-Utility decision.

    All costs are non-negative.  Lower is better.

    Attributes:
        cost_wrong:       Cost of answering ANSWER when wrong.
        cost_hedge_right: Cost of hedging when actually correct (modest penalty).
        cost_hedge_wrong: Cost of hedging when wrong (still misleads user).
        cost_abstain:     Fixed cost of abstaining (user gets no answer).
    """
    cost_wrong:       float = 0.6
    cost_hedge_right: float = 0.05
    cost_hedge_wrong: float = 0.30
    cost_abstain:     float = 0.35


DOMAIN_PRESETS: Dict[str, DomainCosts] = {
    #                         wrong  hedge_right  hedge_wrong  abstain
    "math":        DomainCosts(0.80,  0.05,        0.40,        0.30),
    "logic":       DomainCosts(0.80,  0.05,        0.40,        0.30),
    "ethics":      DomainCosts(1.00,  0.10,        0.60,        0.20),
    "safety":      DomainCosts(1.00,  0.10,        0.60,        0.20),
    "medical":     DomainCosts(1.00,  0.10,        0.60,        0.15),
    "legal":       DomainCosts(1.00,  0.10,        0.60,        0.15),
    "general":     DomainCosts(0.60,  0.05,        0.30,        0.35),
    "knowledge":   DomainCosts(0.60,  0.05,        0.30,        0.35),
    "creative":    DomainCosts(0.30,  0.02,        0.15,        0.50),
    "open_ended":  DomainCosts(0.30,  0.02,        0.15,        0.50),
}


# ─────────────────────────────────────────────────────────────────────────────
# Decision result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DecisionResult:
    action:     Action
    confidence: float          # Fused C ∈ [0, 1]
    signals:    Dict[str, float] = field(default_factory=dict)
    costs:      Dict[str, float] = field(default_factory=dict)
    explanation: str = ""

    @property
    def action_str(self) -> str:
        return self.action.value


# ─────────────────────────────────────────────────────────────────────────────
# AbstentionPolicy
# ─────────────────────────────────────────────────────────────────────────────

class AbstentionPolicy:
    """
    Bayesian fusion + expected-utility decision engine.

    Args:
        signal_weights:  Dict mapping signal name → fusion weight.
                         Weights are applied in log-odds space before
                         summing (like a weighted Naive Bayes).
                         Defaults: T=1.2, A=1.2, S=0.8, V=0.8
        calibrators:     Optional per-signal SignalCalibrator instances.
                         If None, identity calibration is used.
        domain_costs:    Optional custom DomainCosts override.
    """

    _DEFAULT_WEIGHTS = {"T": 1.2, "A": 1.2, "S": 0.8, "V": 0.8}

    def __init__(
        self,
        signal_weights: Optional[Dict[str, float]] = None,
        calibrators: Optional[Dict[str, SignalCalibrator]] = None,
        domain_costs: Optional[Dict[str, DomainCosts]] = None,
    ) -> None:
        self._weights = {**self._DEFAULT_WEIGHTS, **(signal_weights or {})}
        self._calibrators: Dict[str, SignalCalibrator] = calibrators or {}
        self._domain_costs = {**DOMAIN_PRESETS, **(domain_costs or {})}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def decide(
        self,
        T: float,
        A: float,
        S: float,
        V: Optional[float] = None,
        domain: str = "general",
    ) -> DecisionResult:
        """
        Fuse signals and decide on an action.

        Args:
            T:      Token-level confidence ∈ [0, 1] (attention-weighted surprisal).
            A:      Cluster agreement ∈ [0, 1] (self-consistency).
            S:      Semantic coherence ∈ [0, 1] (pairwise cosine).
            V:      Self-verification score ∈ [0, 1] (optional; skip if None).
            domain: Domain string for cost lookup (e.g. "math", "ethics").

        Returns:
            DecisionResult with action, confidence, and diagnostic info.
        """
        # ── 1. Calibrate each signal ───────────────────────────────────
        raw_signals = {"T": T, "A": A, "S": S}
        if V is not None:
            raw_signals["V"] = V

        calibrated: Dict[str, float] = {}
        for name, value in raw_signals.items():
            cal = self._calibrators.get(name)
            calibrated[name] = cal.predict(value) if cal else float(np.clip(value, 1e-6, 1.0 - 1e-6))

        # ── 2. Bayesian log-odds fusion ────────────────────────────────
        C = self._bayesian_fuse(calibrated)

        # ── 3. Expected-utility decision ───────────────────────────────
        costs = self._domain_costs.get(domain.lower(), self._domain_costs["general"])
        action, action_costs = self._expected_utility_decision(C, costs)

        # ── 4. Build explanation ───────────────────────────────────────
        explanation = self._build_explanation(action, C, calibrated, domain)

        return DecisionResult(
            action=action,
            confidence=C,
            signals={**raw_signals, "C_fused": C},
            costs=action_costs,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Bayesian log-odds fusion
    # ------------------------------------------------------------------

    def _bayesian_fuse(self, calibrated: Dict[str, float]) -> float:
        """
        Combine calibrated per-signal probabilities via log-odds.

        For each signal x with calibrated probability p_x and weight w_x:
            lo_x = w_x * log(p_x / (1 - p_x))

        Summed log-odds → back to probability:
            C = σ(Σ lo_x)

        The prior is 0.5 (uniform) — equivalent to starting at log-odds=0.
        """
        total_log_odds = 0.0
        for name, p in calibrated.items():
            w = self._weights.get(name, 1.0)
            lo = w * math.log(p / (1.0 - p))   # p is already clipped away from 0/1
            total_log_odds += lo

        C = _sigmoid(total_log_odds)
        return float(np.clip(C, 0.0, 1.0))

    # ------------------------------------------------------------------
    # Expected-utility decision
    # ------------------------------------------------------------------

    def _expected_utility_decision(
        self, C: float, costs: DomainCosts
    ) -> Tuple[Action, Dict[str, float]]:
        """
        Choose the action that minimises expected cost.

        E[ANSWER]  = C * 0           + (1-C) * cost_wrong
        E[HEDGE]   = C * cost_hedge_right + (1-C) * cost_hedge_wrong
        E[ABSTAIN] = cost_abstain    (fixed, independent of C)
        """
        e_answer  = (1.0 - C) * costs.cost_wrong
        e_hedge   = C * costs.cost_hedge_right + (1.0 - C) * costs.cost_hedge_wrong
        e_abstain = costs.cost_abstain

        action_costs = {
            "E[ANSWER]":  round(e_answer, 4),
            "E[HEDGE]":   round(e_hedge, 4),
            "E[ABSTAIN]": round(e_abstain, 4),
        }

        min_cost = min(e_answer, e_hedge, e_abstain)
        if min_cost == e_abstain:
            return Action.ABSTAIN, action_costs
        elif min_cost == e_hedge:
            return Action.HEDGE, action_costs
        else:
            return Action.ANSWER, action_costs

    # ------------------------------------------------------------------
    # Explanation builder
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        action: Action,
        C: float,
        calibrated: Dict[str, float],
        domain: str,
    ) -> str:
        pct = int(C * 100)
        sig_parts = ", ".join(f"{k}={v:.2f}" for k, v in calibrated.items())

        if action == Action.ANSWER:
            return (
                f"Confident answer (C={pct}%, domain={domain}). "
                f"Signals: [{sig_parts}]."
            )
        elif action == Action.HEDGE:
            return (
                f"Uncertain answer (C={pct}%, domain={domain}) — "
                f"hedged response recommended. Signals: [{sig_parts}]."
            )
        else:
            return (
                f"Low confidence (C={pct}%, domain={domain}) — "
                f"abstain recommended. Signals: [{sig_parts}]."
            )

    # ------------------------------------------------------------------
    # Response formatter
    # ------------------------------------------------------------------

    @staticmethod
    def format_response(action: Action, answer: str, confidence: float) -> str:
        """
        Wrap a base answer string with the appropriate hedging language.

        Args:
            action:     Decision from decide().
            answer:     The model's raw answer text.
            confidence: Fused C value (used in hedge message).

        Returns:
            Final response string suitable for the user.
        """
        if action == Action.ANSWER:
            return answer

        elif action == Action.HEDGE:
            pct = int(confidence * 100)
            prefix = (
                f"I'm not entirely certain about this (estimated confidence: ~{pct}%), "
                "but based on my reasoning: "
            )
            return prefix + answer

        else:  # ABSTAIN
            return (
                "I don't have sufficient confidence to provide a reliable answer "
                "to this question. I'd recommend consulting a more authoritative "
                "source or rephrasing the question for better coverage."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    """Numerically-stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)
