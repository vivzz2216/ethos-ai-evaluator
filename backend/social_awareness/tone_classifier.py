"""
Tone Classifier — assigns a style label from StyleDetector scores and checks
policy compliance.  Also supports custom brand voice matching.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional


STYLE_LABELS = ("FORMAL", "INFORMAL", "CORPORATE", "HUMAN", "HYBRID")
MIXED_GAP_THRESHOLD = 0.15  # if top two scores are within this, label as HYBRID


class ToneClassifier:
    """
    Converts raw style scores (from StyleDetector) into:
      - A human-readable style label
      - A compliance verdict against a required policy or brand voice
      - Style boundary thresholds from style_profiles.json
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, Any] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        config_path = os.path.join(
            os.path.dirname(__file__), "config", "style_profiles.json"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self._profiles = json.load(f)
        except Exception:
            self._profiles = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def classify(
        self,
        detection_result: Dict[str, Any],
        required_style: Optional[str] = None,
        brand_voice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Args:
            detection_result: output of StyleDetector.detect()
            required_style:   one of 'formal', 'informal', 'corporate', 'human'
            brand_voice:      key in style_profiles.json > brand_voices

        Returns dict with: label, compliance, violations, brand_voice_info
        """
        label = self._derive_label(detection_result)
        violations = self._check_violations(detection_result)
        compliance = self._check_compliance(label, detection_result, required_style, brand_voice)
        brand_info = self._get_brand_voice_info(brand_voice) if brand_voice else None

        return {
            "label": label,
            "compliance": compliance,
            "required_style": required_style,
            "brand_voice": brand_voice,
            "brand_voice_info": brand_info,
            "violations": violations,
        }

    def get_available_styles(self) -> Dict[str, Any]:
        """Return built-in styles and registered brand voices."""
        styles = {k: v for k, v in self._profiles.items() if k != "brand_voices"}
        brand_voices = self._profiles.get("brand_voices", {})
        return {"built_in_styles": list(styles.keys()), "brand_voices": brand_voices}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _derive_label(self, det: Dict[str, Any]) -> str:
        if det.get("is_mixed", False):
            return "HYBRID"

        dom = det.get("dominant_style", "").lower()
        mapping = {
            "formal": "FORMAL",
            "informal": "INFORMAL",
            "corporate": "CORPORATE",
            "human": "HUMAN",
        }
        return mapping.get(dom, "HYBRID")

    def _check_violations(self, det: Dict[str, Any]) -> list:
        """Build a list of named violation flags from detection signals."""
        violations = []
        rule = det.get("rule_signals", {})
        syntax = det.get("syntax_signals", {})

        if rule.get("contraction_ratio", 0) * 8 > 0.3:
            violations.append("informal_contraction")
        if rule.get("slang_ratio", 0) * 10 > 0.2:
            violations.append("slang_detected")
        if rule.get("emoji_ratio", 0) > 0.05:
            violations.append("emoji_present")
        if rule.get("exclamation_ratio", 0) > 0.4:
            violations.append("excessive_punctuation")
        if syntax.get("passive_voice_ratio", 0) < 0.05 and det.get("dominant_style") == "corporate":
            violations.append("low_passive_voice_for_corporate")
        if syntax.get("noun_phrase_density", 0) < 0.1 and det.get("dominant_style") == "formal":
            violations.append("low_noun_density_for_formal")

        return violations

    def _check_compliance(
        self,
        label: str,
        det: Dict[str, Any],
        required_style: Optional[str],
        brand_voice: Optional[str],
    ) -> str:
        if not required_style and not brand_voice:
            return "NOT_CHECKED"

        if brand_voice:
            bv = self._profiles.get("brand_voices", {}).get(brand_voice)
            if bv:
                base = bv.get("base_style", "formal").upper()
                required_style = base  # use base style for compliance

        if required_style:
            req = required_style.upper()
            if label == req:
                return "COMPLIANT"
            if label == "HYBRID":
                # Check if the required style is the dominant contributor
                score_key = f"{required_style.lower()}_score"
                if det.get(score_key, 0) >= 0.45:
                    return "PARTIAL"
            return "VIOLATION"

        return "NOT_CHECKED"

    def _get_brand_voice_info(self, brand_voice: str) -> Optional[Dict[str, Any]]:
        return self._profiles.get("brand_voices", {}).get(brand_voice)
