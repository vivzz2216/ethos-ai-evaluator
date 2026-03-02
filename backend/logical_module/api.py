"""
Logical Module Pipeline — top-level orchestrator.

Chains all components:
  ConfidenceEstimator  → T  (token-level attention-weighted surprisal)
  UncertaintyDetector  → A, S  (cluster consistency + semantic coherence)
  SelfVerifier         → V  (judge loop)
  AbstentionPolicy     → C, action  (Bayesian fusion + expected utility)

Usage
─────
    from logical_module.api import LogicalModulePipeline

    pipeline = LogicalModulePipeline()          # lightweight — no model loaded here
    result   = pipeline.evaluate(
        model, tokenizer,
        prompt="Who was the 3rd president of the United States?",
        domain="knowledge",
        M=7,
        use_self_verify=True,
    )

    print(result["action"])            # "ANSWER" | "HEDGE" | "ABSTAIN"
    print(result["confidence"])        # float ∈ [0, 1]
    print(result["response"])          # formatted final response string
    print(result["signals"])           # dict of intermediate scores
    print(result["explanation"])       # human-readable decision explanation

Design decisions
────────────────
- All heavy components are lazy-loaded (no GPU hit at import time).
- If a component fails it degrades gracefully: missing signal is
  replaced with 0.5 (neutral) and logged.
- `evaluate_from_text()` variant accepts pre-generated answers
  (useful for API models where you can't access logits).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

from .confidence_estimator import ConfidenceEstimator
from .uncertainty_detector import UncertaintyDetector
from .abstention_policy import AbstentionPolicy, Action, DecisionResult
from .logic_evaluator import SelfVerifier

logger = logging.getLogger(__name__)

try:
    import torch  # type: ignore
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class LogicalModulePipeline:
    """
    End-to-end confidence-estimation and abstention pipeline.

    Args:
        embedding_model:    Sentence-transformers model for UncertaintyDetector.
        verbose_verify:     Use the longer self-verification prompt.
        signal_weights:     Override default Bayesian fusion weights.
        calibrators:        Pre-fitted SignalCalibrator instances.
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        verbose_verify: bool = False,
        signal_weights: Optional[Dict[str, float]] = None,
        calibrators: Optional[Dict] = None,
    ) -> None:
        self._estimator   = ConfidenceEstimator()
        self._detector    = UncertaintyDetector(embedding_model=embedding_model)
        self._verifier    = SelfVerifier(verbose=verbose_verify)
        self._policy      = AbstentionPolicy(
            signal_weights=signal_weights,
            calibrators=calibrators,
        )

    # ------------------------------------------------------------------
    # Full pipeline (requires access to model internals)
    # ------------------------------------------------------------------

    def evaluate(
        self,
        model,
        tokenizer,
        prompt: str,
        domain: str = "general",
        M: int = 7,
        use_self_verify: bool = True,
        max_new_tokens: int = 300,
        sampling_temperature: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Run the full confidence estimation pipeline.

        Args:
            model:                 HuggingFace causal-LM (on GPU/CPU).
            tokenizer:             Corresponding tokenizer.
            prompt:                The user's question / prompt.
            domain:                Domain hint for cost-sensitive decisions.
                                   One of: math, logic, ethics, safety,
                                   medical, legal, general, knowledge,
                                   creative, open_ended.
            M:                     Number of self-consistency samples.
            use_self_verify:       Whether to run the judge-verify loop (V).
            max_new_tokens:        Token budget for the primary answer.
            sampling_temperature:  Sampling temperature for consistency samples.

        Returns:
            Dict with keys: action, confidence, response, signals, explanation,
                            timing_ms, primary_answer.
        """
        t0 = time.time()

        if not TORCH_AVAILABLE:
            return self._unavailable_result(prompt)

        # ── Step 1: Generate primary answer ──────────────────────────────
        primary_answer, input_ids, output_ids, model_output = self._generate_primary(
            model, tokenizer, prompt, max_new_tokens
        )

        # ── Step 2: Token-level confidence (T) ───────────────────────────
        T, t_meta = self._safe_token_confidence(
            model, tokenizer, input_ids, output_ids
        )

        # ── Step 3: Self-consistency (A, S) ──────────────────────────────
        A, S, as_meta = self._safe_consistency(
            model, tokenizer, prompt, M, sampling_temperature, max_new_tokens
        )

        # ── Step 4: Self-verification (V) ────────────────────────────────
        V, v_meta = None, {}
        if use_self_verify:
            V, v_meta = self._safe_verify(model, tokenizer, prompt, primary_answer)

        # ── Step 5: Bayesian fusion + expected-utility decision ───────────
        decision: DecisionResult = self._policy.decide(T, A, S, V, domain=domain)

        # ── Step 6: Format response ───────────────────────────────────────
        formatted_response = AbstentionPolicy.format_response(
            decision.action, primary_answer, decision.confidence
        )

        elapsed_ms = int((time.time() - t0) * 1000)

        return {
            "action":         decision.action_str,
            "confidence":     round(decision.confidence, 4),
            "response":       formatted_response,
            "primary_answer": primary_answer,
            "signals": {
                "T":  round(T, 4),
                "A":  round(A, 4),
                "S":  round(S, 4),
                "V":  round(V, 4) if V is not None else None,
                "C":  round(decision.confidence, 4),
            },
            "costs":       decision.costs,
            "explanation": decision.explanation,
            "timing_ms":   elapsed_ms,
            "domain":      domain,
            "meta": {
                "token_confidence": t_meta,
                "consistency":      as_meta,
                "verification":     v_meta,
            },
        }

    # ------------------------------------------------------------------
    # API / text-only variant (no logit access needed)
    # ------------------------------------------------------------------

    def evaluate_from_text(
        self,
        primary_answer: str,
        sampled_answers: List[str],
        domain: str = "general",
        token_logprobs: Optional[List[float]] = None,
        self_verify_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compute confidence from pre-generated text (for API-only setups).

        Args:
            primary_answer:    The main model answer.
            sampled_answers:   M additional sampled answers (for consistency).
            domain:            Domain hint.
            token_logprobs:    Per-token log-probs if available from API.
            self_verify_score: Pre-computed V ∈ [0,1] if already obtained.

        Returns:
            Same dict structure as evaluate().
        """
        t0 = time.time()

        # Token confidence
        if token_logprobs:
            T, t_meta = self._estimator.from_logprobs(token_logprobs)
        else:
            T, t_meta = 0.5, {"method": "not_provided"}

        # Consistency
        if sampled_answers:
            A, S, as_meta = self._detector.compute_consistency_from_answers(
                sampled_answers
            )
        else:
            A, S, as_meta = 0.5, 0.5, {"method": "no_samples"}

        V = self_verify_score

        decision: DecisionResult = self._policy.decide(T, A, S, V, domain=domain)
        formatted_response = AbstentionPolicy.format_response(
            decision.action, primary_answer, decision.confidence
        )

        return {
            "action":         decision.action_str,
            "confidence":     round(decision.confidence, 4),
            "response":       formatted_response,
            "primary_answer": primary_answer,
            "signals": {
                "T":  round(T, 4),
                "A":  round(A, 4),
                "S":  round(S, 4),
                "V":  round(V, 4) if V is not None else None,
                "C":  round(decision.confidence, 4),
            },
            "costs":       decision.costs,
            "explanation": decision.explanation,
            "timing_ms":   int((time.time() - t0) * 1000),
            "domain":      domain,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_primary(self, model, tokenizer, prompt: str, max_new_tokens: int):
        """Generate the primary answer and return ids + model output."""
        inputs = tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=512
        )
        input_len = inputs["input_ids"].shape[1]
        device = next(model.parameters()).device
        inputs_gpu = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            output = model.generate(
                **inputs_gpu,
                max_new_tokens=max_new_tokens,
                do_sample=False,          # greedy for primary answer = deterministic
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        new_ids = output[0][input_len:]
        answer  = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        return answer, inputs["input_ids"], output, None

    def _safe_token_confidence(self, model, tokenizer, input_ids, output_ids):
        try:
            return self._estimator.compute_token_confidence(
                model, tokenizer, input_ids, output_ids
            )
        except Exception as exc:
            logger.warning("Token confidence failed: %s", exc)
            return 0.5, {"method": "error", "error": str(exc)}

    def _safe_consistency(
        self, model, tokenizer, prompt, M, temperature, max_new_tokens
    ):
        try:
            return self._detector.compute_consistency(
                model, tokenizer, prompt,
                M=M, temperature=temperature, max_new_tokens=max_new_tokens,
            )
        except Exception as exc:
            logger.warning("Consistency detection failed: %s", exc)
            return 0.5, 0.5, {"method": "error", "error": str(exc)}

    def _safe_verify(self, model, tokenizer, prompt, answer):
        try:
            return self._verifier.verify(model, tokenizer, prompt, answer)
        except Exception as exc:
            logger.warning("Self-verification failed: %s", exc)
            return None, {"method": "error", "error": str(exc)}

    @staticmethod
    def _unavailable_result(prompt: str) -> Dict[str, Any]:
        return {
            "action":         Action.HEDGE.value,
            "confidence":     0.5,
            "response":       (
                "I'm unable to estimate confidence without model access. "
                "Providing answer without certainty guarantee."
            ),
            "primary_answer": "",
            "signals":        {"T": 0.5, "A": 0.5, "S": 0.5, "V": None, "C": 0.5},
            "costs":          {},
            "explanation":    "torch not available — confidence estimation disabled.",
            "timing_ms":      0,
            "domain":         "general",
        }
