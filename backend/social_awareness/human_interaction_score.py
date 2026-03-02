"""
Human Interaction Scorer — measures human-likeness across 5 dimensions
with weighted normalization.

Dimensions and weights:
  empathy            0.25   (VADER compound + empathy word list)
  clarity            0.25   (Flesch readability approximation)
  politeness         0.20   (politeness marker density)
  engagement         0.15   (questions, varied starters, acknowledgment)
  conversational_flow 0.15  (transitions, hedging, personal pronouns)
"""

from __future__ import annotations

import re
import math
from typing import Dict, Any, List, Optional

# ── Vocabulary constants ──────────────────────────────────────────────────────

EMPATHY_WORDS = {
    "understand", "understand that", "appreciate", "feel", "imagine",
    "realize", "recognize", "see how", "hear you", "empathize",
    "concern", "worried", "difficult", "tough", "challenge", "support",
    "help", "here for you", "care", "sorry",
}

POLITENESS_MARKERS = [
    "please", "thank you", "thanks", "appreciate", "grateful",
    "kindly", "excuse me", "pardon", "sorry", "apologies",
    "i apologize", "would you mind", "if you don't mind",
]

TRANSITION_WORDS = [
    "however", "therefore", "furthermore", "additionally", "moreover",
    "nevertheless", "consequently", "in conclusion", "for example",
    "on the other hand", "in addition", "as a result",
    "first", "second", "finally", "next", "then",
]

HEDGING_PHRASES = [
    "i think", "i believe", "it seems", "it appears", "perhaps",
    "possibly", "might", "could", "in my opinion", "generally",
    "typically", "often", "sometimes",
]

PERSONAL_PRONOUNS = r"\b(i|we|you|your|my|our|me|us)\b"

ACKNOWLEDGMENT_PHRASES = [
    "great question", "good point", "i see", "i understand",
    "absolutely", "of course", "certainly", "sure", "right",
    "that makes sense",
]

SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
SYLLABLE_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)

# Dimension weights must sum to 1.0
WEIGHTS = {
    "empathy": 0.25,
    "clarity": 0.25,
    "politeness": 0.20,
    "engagement": 0.15,
    "conversational_flow": 0.15,
}


class HumanInteractionScorer:
    """
    Scores how human-like a text response feels across 5 dimensions.
    Returns scores in [0, 100] with a weighted overall score.
    """

    def __init__(self) -> None:
        # Try to load VADER; degrade gracefully if unavailable
        self._vader = None
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
            self._vader = SentimentIntensityAnalyzer()
        except ImportError:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def score(self, text: str) -> Dict[str, Any]:
        """Score a single text string. Returns per-dimension and overall score."""
        if not text or not text.strip():
            return self._empty_score()

        empathy = self._score_empathy(text)
        clarity = self._score_clarity(text)
        politeness = self._score_politeness(text)
        engagement = self._score_engagement(text)
        flow = self._score_conversational_flow(text)

        # Apply weights and compute overall (all inputs already [0,100])
        overall = (
            WEIGHTS["empathy"] * empathy
            + WEIGHTS["clarity"] * clarity
            + WEIGHTS["politeness"] * politeness
            + WEIGHTS["engagement"] * engagement
            + WEIGHTS["conversational_flow"] * flow
        )

        return {
            "empathy": round(empathy),
            "clarity": round(clarity),
            "politeness": round(politeness),
            "engagement": round(engagement),
            "conversational_flow": round(flow),
            "overall": round(overall),
            "weights": WEIGHTS,
        }

    def score_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        return [self.score(t) for t in texts]

    # ── Dimension scorers ─────────────────────────────────────────────────────

    def _score_empathy(self, text: str) -> float:
        """Empathy = VADER positive sentiment + empathy word list density."""
        text_lower = text.lower()
        tokens = re.findall(r"\b\w+\b", text_lower)
        token_count = max(len(tokens), 1)

        # Empathy word list
        empathy_hits = sum(1 for w in EMPATHY_WORDS if w in text_lower)
        word_score = min(empathy_hits / 5.0, 1.0)  # saturate at 5 matches

        # VADER sentiment (positive compound = empathetic)
        vader_score = 0.5
        if self._vader:
            vs = self._vader.polarity_scores(text)
            # Positive compound mapped to [0,1]
            vader_score = (vs["compound"] + 1.0) / 2.0

        empathy_raw = 0.6 * word_score + 0.4 * vader_score
        return empathy_raw * 100.0

    def _score_clarity(self, text: str) -> float:
        """Clarity ≈ Flesch readability approximation → normalized to [0,100]."""
        words = re.findall(r"\b\w+\b", text)
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]

        word_count = max(len(words), 1)
        sentence_count = max(len(sentences), 1)

        # Count syllables (crude approximation)
        syllable_count = sum(
            max(len(SYLLABLE_RE.findall(w)), 1) for w in words
        )

        asl = word_count / sentence_count          # avg sentence length
        asw = syllable_count / word_count          # avg syllables per word

        # Flesch Reading Ease: 206.835 - 1.015*ASL - 84.6*ASW
        flesch = 206.835 - 1.015 * asl - 84.6 * asw
        # Clamp to [0, 100]
        return max(0.0, min(flesch, 100.0))

    def _score_politeness(self, text: str) -> float:
        """Politeness = density of politeness marker phrases."""
        text_lower = text.lower()
        hits = sum(1 for m in POLITENESS_MARKERS if m in text_lower)
        # 3+ markers = max score
        raw = min(hits / 3.0, 1.0)
        return raw * 100.0

    def _score_engagement(self, text: str) -> float:
        """Engagement = questions + positive acknowledgment phrases + sentence variety."""
        text_lower = text.lower()
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]

        question_ratio = text.count("?") / max(len(sentences), 1)
        question_score = min(question_ratio / 0.5, 1.0)  # 50% questions = max

        ack_hits = sum(1 for a in ACKNOWLEDGMENT_PHRASES if a in text_lower)
        ack_score = min(ack_hits / 3.0, 1.0)

        # Starter variety: how many unique first words across sentences
        starters = {re.split(r"\s+", s)[0].lower() for s in sentences if s}
        variety_score = min(len(starters) / max(len(sentences), 1), 1.0)

        raw = 0.4 * question_score + 0.4 * ack_score + 0.2 * variety_score
        return raw * 100.0

    def _score_conversational_flow(self, text: str) -> float:
        """Flow = transitions + hedging + personal pronoun usage."""
        text_lower = text.lower()
        tokens = re.findall(r"\b\w+\b", text_lower)
        token_count = max(len(tokens), 1)

        transition_hits = sum(1 for t in TRANSITION_WORDS if t in text_lower)
        transition_score = min(transition_hits / 4.0, 1.0)

        hedge_hits = sum(1 for h in HEDGING_PHRASES if h in text_lower)
        hedge_score = min(hedge_hits / 3.0, 1.0)

        pronoun_count = len(re.findall(PERSONAL_PRONOUNS, text_lower))
        pronoun_score = min(pronoun_count / max(token_count * 0.05, 1), 1.0)

        raw = 0.4 * transition_score + 0.3 * hedge_score + 0.3 * pronoun_score
        return raw * 100.0

    def _empty_score(self) -> Dict[str, Any]:
        return {
            "empathy": 0,
            "clarity": 0,
            "politeness": 0,
            "engagement": 0,
            "conversational_flow": 0,
            "overall": 0,
            "weights": WEIGHTS,
        }
