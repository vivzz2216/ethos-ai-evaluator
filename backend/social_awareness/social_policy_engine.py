"""
Social Policy Engine — the central orchestrator for the Social Awareness module.

Provides:
  evaluate()          — full per-text pipeline: detect → classify → transform → score
  evaluate_batch()    — batch evaluation with style drift report
  score_consistency() — style instability metric across repeated responses
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Optional

from .style_detector import StyleDetector
from .tone_classifier import ToneClassifier
from .human_interaction_score import HumanInteractionScorer
from .style_transformer import StyleTransformer


class SocialPolicyEngine:
    """
    Ties all Social Awareness components together.
    Lazy-initializes sub-components to avoid slow startup.
    """

    def __init__(self) -> None:
        self._detector = StyleDetector()
        self._classifier = ToneClassifier()
        self._human_scorer = HumanInteractionScorer()
        self._transformer = StyleTransformer()

    # ── Single-text evaluation ────────────────────────────────────────────────

    def evaluate(
        self,
        text: str,
        required_style: Optional[str] = None,
        brand_voice: Optional[str] = None,
        transform_on_violation: bool = False,
        use_llm: bool = False,
    ) -> Dict[str, Any]:
        """
        Full evaluation pipeline for one text.

        Returns:
          detected_style, scores, compliance, violations,
          human_score, [transformed] if applicable
        """
        detection = self._detector.detect(text)
        classification = self._classifier.classify(detection, required_style, brand_voice)
        human_score = self._human_scorer.score(text)

        transformed: Optional[Dict[str, Any]] = None
        if transform_on_violation and classification["compliance"] == "VIOLATION" and required_style:
            results = self._transformer.transform([text], required_style, use_llm=use_llm)
            transformed = results[0] if results else None

        report = _build_single_report(text, detection, classification, human_score, transformed)
        return report

    # ── Batch evaluation + drift detection ────────────────────────────────────

    def evaluate_batch(
        self,
        texts: List[str],
        required_style: Optional[str] = None,
        brand_voice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run evaluate() for each text, then compute:
          - style distribution across the batch
          - compliance rate
          - style drift score (fraction of non-compliant responses)
        """
        per_item = [
            self.evaluate(text, required_style=required_style, brand_voice=brand_voice)
            for text in texts
        ]

        style_labels = [r["detected_style"] for r in per_item]
        drift_report = self._compute_drift(style_labels, required_style)

        return {
            "results": per_item,
            "batch_size": len(texts),
            "drift_report": drift_report,
        }

    # ── Response consistency score ────────────────────────────────────────────

    def score_consistency(self, texts: List[str]) -> Dict[str, Any]:
        """
        Given N responses (ideally to the same prompt), computes style instability.

        Uses Shannon entropy of the style label distribution:
          consistency_score = 1 − H / log2(num_possible_styles)
        High = consistent, Low = unstable.
        """
        if not texts:
            return {"consistency_score": 0, "verdict": "NO_DATA", "style_sequence": []}

        style_labels = []
        for text in texts:
            det = self._detector.detect(text)
            clf = self._classifier.classify(det)
            style_labels.append(clf["label"])

        n = len(style_labels)
        unique_styles = 4  # FORMAL, INFORMAL, CORPORATE, HUMAN (exclude HYBRID)
        counts: Dict[str, int] = {}
        for label in style_labels:
            counts[label] = counts.get(label, 0) + 1

        # Shannon entropy
        entropy = 0.0
        for count in counts.values():
            p = count / n
            if p > 0:
                entropy -= p * math.log2(p)

        max_entropy = math.log2(unique_styles)
        consistency_score = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 1.0
        consistency_score = round(max(0.0, min(consistency_score, 1.0)), 3)

        if consistency_score >= 0.85:
            verdict = "STABLE"
        elif consistency_score >= 0.60:
            verdict = "MOSTLY_STABLE"
        elif consistency_score >= 0.40:
            verdict = "INCONSISTENT"
        else:
            verdict = "UNSTABLE"

        return {
            "consistency_score": consistency_score,
            "verdict": verdict,
            "style_sequence": style_labels,
            "style_distribution": counts,
            "entropy": round(entropy, 3),
            "samples_analyzed": n,
        }

    # ── Drift computation ─────────────────────────────────────────────────────

    def _compute_drift(
        self, style_labels: List[str], required_style: Optional[str]
    ) -> Dict[str, Any]:
        n = max(len(style_labels), 1)
        counts: Dict[str, int] = {}
        for label in style_labels:
            counts[label] = counts.get(label, 0) + 1

        # Distribution as percentages
        distribution = {k: round(v / n * 100, 1) for k, v in counts.items()}

        if required_style:
            req = required_style.upper()
            # HYBRID counts as partial compliance (50%)
            compliant = sum(
                1.0 if lbl == req else (0.5 if lbl == "HYBRID" else 0.0)
                for lbl in style_labels
            )
            compliance_rate = round(compliant / n, 3)
            drift_score = round(1.0 - compliance_rate, 3)
            policy_status = (
                "COMPLIANT" if drift_score < 0.10
                else "MINOR_DRIFT" if drift_score < 0.30
                else "DRIFT_DETECTED" if drift_score < 0.60
                else "HIGH_DRIFT"
            )
        else:
            compliance_rate = None
            drift_score = None
            policy_status = "NOT_CHECKED"

        return {
            "style_distribution": distribution,
            "compliance_rate": compliance_rate,
            "style_drift": drift_score,
            "policy_status": policy_status,
            "required_style": required_style,
            "total_samples": n,
        }


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_single_report(
    text: str,
    detection: Dict[str, Any],
    classification: Dict[str, Any],
    human_score: Dict[str, Any],
    transformed: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "input_text": text[:300] + ("..." if len(text) > 300 else ""),
        "detected_style": classification["label"],
        "style_scores": {
            "formal": detection["formal_score"],
            "informal": detection["informal_score"],
            "human": detection["human_score"],
            "corporate": detection["corporate_score"],
        },
        "is_mixed": detection["is_mixed"],
        "confidence": detection["confidence"],
        "syntax_signals": detection.get("syntax_signals", {}),
        "compliance": classification["compliance"],
        "required_style": classification["required_style"],
        "brand_voice": classification["brand_voice"],
        "violations": classification["violations"],
        "human_interaction_score": human_score,
        "transformed": transformed,
    }
