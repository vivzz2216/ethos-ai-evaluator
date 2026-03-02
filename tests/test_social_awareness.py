"""
Tests for the Social Awareness / Communication Style Module.

Run with:
    python -m pytest tests/test_social_awareness.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest

# ── Imports ───────────────────────────────────────────────────────────────────

from social_awareness.style_detector import StyleDetector
from social_awareness.tone_classifier import ToneClassifier
from social_awareness.human_interaction_score import HumanInteractionScorer, WEIGHTS
from social_awareness.style_transformer import StyleTransformer
from social_awareness.social_policy_engine import SocialPolicyEngine

# ── Fixtures ──────────────────────────────────────────────────────────────────

FORMAL_TEXT = (
    "I am writing to formally request your assistance with the preparation "
    "of the aforementioned documentation. The required materials should be "
    "submitted no later than Friday. We would appreciate your prompt attention to this matter."
)

INFORMAL_TEXT = (
    "Hey! Can ya help me out? I'm gonna need those docs asap lol. "
    "Don't worry, it's super easy. Just send 'em over when you're free! 😊"
)

CORPORATE_TEXT = (
    "The quarterly deliverable shall be submitted by end of business Friday. "
    "Non-compliance may result in project delays. All stakeholders must adhere to this timeline."
)

HUMAN_TEXT = (
    "I completely understand how overwhelming this can feel. "
    "I'm here to help you work through it step by step. "
    "Could you tell me which part is most challenging for you right now?"
)

MIXED_TEXT = (
    "Sure! I will assist you with the preparation of the requested documentation. "
    "Please don't hesitate to reach out."
)


# ── StyleDetector tests ───────────────────────────────────────────────────────

class TestStyleDetector:
    def setup_method(self):
        self.detector = StyleDetector()

    def test_formal_text_high_formal_score(self):
        result = self.detector.detect(FORMAL_TEXT)
        assert result["formal_score"] > 0.55, f"Expected formal > 0.55, got {result['formal_score']}"

    def test_informal_text_high_informal_score(self):
        result = self.detector.detect(INFORMAL_TEXT)
        assert result["informal_score"] > 0.55, f"Expected informal > 0.55, got {result['informal_score']}"

    def test_mixed_text_flagged_as_mixed(self):
        result = self.detector.detect(MIXED_TEXT)
        assert result["is_mixed"] is True, "Mixed text should be flagged as is_mixed=True"

    def test_scores_between_zero_and_one(self):
        result = self.detector.detect(FORMAL_TEXT)
        for key in ("formal_score", "informal_score", "human_score", "corporate_score"):
            assert 0.0 <= result[key] <= 1.0, f"{key} out of bounds: {result[key]}"

    def test_syntax_signals_returned(self):
        result = self.detector.detect(FORMAL_TEXT)
        assert "syntax_signals" in result
        sig = result["syntax_signals"]
        assert "passive_voice_ratio" in sig
        assert "formal_modal_ratio" in sig
        assert "noun_phrase_density" in sig
        assert "sentence_length_variance" in sig
        assert "syntax_formality" in sig

    def test_passive_voice_detected_in_corporate(self):
        text = "The report was reviewed and submitted by the committee."
        result = self.detector.detect(text)
        assert result["syntax_signals"]["passive_voice_ratio"] > 0, "Passive voice not detected"

    def test_modal_verbs_detected_in_formal(self):
        text = "You may submit the document. The committee shall review it accordingly."
        result = self.detector.detect(text)
        assert result["syntax_signals"]["formal_modal_ratio"] > 0, "Modal verbs not detected"

    def test_empty_text_returns_safe_defaults(self):
        result = self.detector.detect("")
        assert result["dominant_style"] == "unknown"
        assert result["confidence"] == 0.0

    def test_batch_returns_correct_count(self):
        results = self.detector.detect_batch([FORMAL_TEXT, INFORMAL_TEXT, CORPORATE_TEXT])
        assert len(results) == 3


# ── ToneClassifier tests ──────────────────────────────────────────────────────

class TestToneClassifier:
    def setup_method(self):
        self.detector = StyleDetector()
        self.classifier = ToneClassifier()

    def _classify(self, text, **kwargs):
        det = self.detector.detect(text)
        return self.classifier.classify(det, **kwargs)

    def test_hybrid_label_for_mixed_text(self):
        result = self._classify(MIXED_TEXT)
        assert result["label"] == "HYBRID"

    def test_compliance_when_style_matches(self):
        result = self._classify(FORMAL_TEXT, required_style="formal")
        assert result["compliance"] in ("COMPLIANT", "PARTIAL")

    def test_violation_when_style_mismatches(self):
        result = self._classify(INFORMAL_TEXT, required_style="formal")
        assert result["compliance"] == "VIOLATION"

    def test_not_checked_when_no_policy(self):
        result = self._classify(FORMAL_TEXT)
        assert result["compliance"] == "NOT_CHECKED"

    def test_violation_types_populated(self):
        result = self._classify(INFORMAL_TEXT)
        # Should pick up at least contractions or slang
        # violations list may be empty for clean texts; just check type
        assert isinstance(result["violations"], list)

    def test_informal_violations_contain_contraction_or_slang(self):
        result = self._classify(INFORMAL_TEXT)
        violation_types = result["violations"]
        overlap = set(violation_types) & {"informal_contraction", "slang_detected", "emoji_present", "excessive_punctuation"}
        assert len(overlap) > 0, f"Expected informal violations, got: {violation_types}"

    def test_get_available_styles_returns_dict(self):
        styles = self.classifier.get_available_styles()
        assert "built_in_styles" in styles
        assert "brand_voices" in styles
        assert "formal" in styles["built_in_styles"]


# ── HumanInteractionScorer tests ──────────────────────────────────────────────

class TestHumanInteractionScorer:
    def setup_method(self):
        self.scorer = HumanInteractionScorer()

    def test_all_dimensions_returned(self):
        result = self.scorer.score(HUMAN_TEXT)
        for dim in ("empathy", "clarity", "politeness", "engagement", "conversational_flow", "overall"):
            assert dim in result, f"Missing dimension: {dim}"

    def test_scores_in_0_100_range(self):
        result = self.scorer.score(HUMAN_TEXT)
        for dim in ("empathy", "clarity", "politeness", "engagement", "conversational_flow", "overall"):
            assert 0 <= result[dim] <= 100, f"{dim}={result[dim]} out of [0,100]"

    def test_weighted_normalization_correct(self):
        result = self.scorer.score(HUMAN_TEXT)
        expected = (
            WEIGHTS["empathy"] * result["empathy"]
            + WEIGHTS["clarity"] * result["clarity"]
            + WEIGHTS["politeness"] * result["politeness"]
            + WEIGHTS["engagement"] * result["engagement"]
            + WEIGHTS["conversational_flow"] * result["conversational_flow"]
        )
        assert abs(result["overall"] - round(expected)) <= 1, (
            f"Weighted overall mismatch: got {result['overall']}, expected ~{round(expected)}"
        )

    def test_human_text_outscores_corporate_text(self):
        human = self.scorer.score(HUMAN_TEXT)["overall"]
        corp = self.scorer.score(CORPORATE_TEXT)["overall"]
        assert human >= corp, f"Human text ({human}) should score >= corporate ({corp})"

    def test_empty_text_returns_zeros(self):
        result = self.scorer.score("")
        assert result["overall"] == 0

    def test_batch_returns_correct_count(self):
        results = self.scorer.score_batch([HUMAN_TEXT, FORMAL_TEXT])
        assert len(results) == 2


# ── StyleTransformer tests ────────────────────────────────────────────────────

class TestStyleTransformer:
    def setup_method(self):
        self.transformer = StyleTransformer()

    def test_batch_returns_correct_count(self):
        results = self.transformer.transform([INFORMAL_TEXT, MIXED_TEXT], "formal")
        assert len(results) == 2

    def test_contraction_expanded_in_formal(self):
        text = "I don't know what you're talking about. We can't help right now."
        results = self.transformer.transform([text], "formal")
        transformed = results[0]["transformed"].lower()
        # Contractions should be expanded
        assert "don't" not in transformed or "do not" in transformed

    def test_opener_substituted_in_formal(self):
        text = "Sure! I will help you with that."
        results = self.transformer.transform([text], "formal")
        transformed = results[0]["transformed"]
        assert "Sure!" not in transformed

    def test_result_has_required_keys(self):
        results = self.transformer.transform(["Hello there!"], "formal")
        r = results[0]
        for key in ("original", "transformed", "target_style", "similarity_score", "meaning_preserved", "method"):
            assert key in r, f"Missing key: {key}"

    def test_similarity_score_in_range(self):
        results = self.transformer.transform([FORMAL_TEXT], "corporate")
        assert 0.0 <= results[0]["similarity_score"] <= 1.0

    def test_passthrough_on_empty(self):
        results = self.transformer.transform([""], "formal")
        assert results[0]["method"] == "passthrough"


# ── SocialPolicyEngine tests ──────────────────────────────────────────────────

class TestSocialPolicyEngine:
    def setup_method(self):
        self.engine = SocialPolicyEngine()

    def test_evaluate_returns_required_keys(self):
        result = self.engine.evaluate(FORMAL_TEXT, required_style="formal")
        for key in (
            "detected_style", "style_scores", "compliance",
            "violations", "human_interaction_score",
        ):
            assert key in result, f"Missing key: {key}"

    def test_style_scores_dict_has_four_keys(self):
        result = self.engine.evaluate(FORMAL_TEXT)
        assert set(result["style_scores"].keys()) == {"formal", "informal", "human", "corporate"}

    def test_drift_detected_for_mixed_batch(self):
        # 2 formal + 3 informal → significant drift
        texts = [FORMAL_TEXT, FORMAL_TEXT, INFORMAL_TEXT, INFORMAL_TEXT, INFORMAL_TEXT]
        batch = self.engine.evaluate_batch(texts, required_style="formal")
        drift = batch["drift_report"]["style_drift"]
        assert drift is not None
        assert drift > 0.0, "Expected drift > 0 for mixed batch"

    def test_no_drift_for_uniform_formal_batch(self):
        texts = [FORMAL_TEXT, FORMAL_TEXT, FORMAL_TEXT]
        batch = self.engine.evaluate_batch(texts, required_style="formal")
        drift = batch["drift_report"]["style_drift"]
        assert drift is not None
        assert drift < 0.5, f"Expected low drift for uniform formal batch, got {drift}"

    def test_consistency_stable_for_uniform_texts(self):
        texts = [FORMAL_TEXT] * 5
        result = self.engine.score_consistency(texts)
        assert result["consistency_score"] == pytest.approx(1.0, abs=0.05)
        assert result["verdict"] == "STABLE"

    def test_consistency_unstable_for_varied_texts(self):
        texts = [FORMAL_TEXT, INFORMAL_TEXT, CORPORATE_TEXT, HUMAN_TEXT, MIXED_TEXT]
        result = self.engine.score_consistency(texts)
        assert result["consistency_score"] < 0.9

    def test_consistency_returns_style_sequence(self):
        texts = [FORMAL_TEXT, INFORMAL_TEXT]
        result = self.engine.score_consistency(texts)
        assert "style_sequence" in result
        assert len(result["style_sequence"]) == 2

    def test_empty_batch_consistency(self):
        result = self.engine.score_consistency([])
        assert result["verdict"] == "NO_DATA"
