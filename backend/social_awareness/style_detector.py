"""
Style Detector — analyzes text and returns per-style numeric scores.

Two-layer approach:
1. Rule-based heuristics (always available, no GPU required)
   - slang, contractions, emoji, politeness markers, punctuation
   - syntax formality: passive voice, modal verbs, sentence length variance,
     noun phrase density
2. ML formality scorer (optional, lazy-loaded)
   - s-nlp/roberta-base-formality-ranker
"""

from __future__ import annotations

import re
import math
import statistics
from typing import Dict, Any, List, Optional

# ── Vocabulary / pattern constants ──────────────────────────────────────────

SLANG_WORDS = {
    "gonna", "wanna", "gotta", "ya", "yep", "nope", "kinda", "sorta",
    "lemme", "gimme", "ain't", "dunno", "wassup", "sup", "lol", "lmao",
    "omg", "tbh", "imo", "imho", "btw", "fyi", "asap", "brb", "ngl", "fr",
    "lowkey", "highkey", "vibe", "lit", "dope", "chill", "legit", "bro",
    "dude", "sick", "fire", "bet", "cap", "sus", "slay",
    # Conversational fillers / casual markers
    "ok", "okay", "basically", "honestly", "literally", "actually",
    "seriously", "totally", "absolutely", "def", "tho", "totes",
    "welp", "whoa", "ooh", "yikes", "meh", "haha", "hehe", "yay",
    "gonna", "tryna", "finna", "boutta", "gooo", "yoo", "yooo",
    # Gen-Z / social media
    "mood", "stan", "goat", "fam", "periodt", "deadass", "bussin",
    "sheesh", "bestie", "sis", "bruh", "bae", "vibe", "salty",
    "boomer", "simp", "flex", "ratio", "idk", "rn", "irl",
}


CONTRACTION_RE = re.compile(
    r"\b("
    r"don't|doesn't|didn't|won't|wouldn't|can't|couldn't|shouldn't|"
    r"isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't|"
    r"I'm|I've|I'll|I'd|you're|you've|you'll|you'd|"
    r"he's|she's|it's|we're|we've|we'll|we'd|they're|they've|they'll|they'd|"
    r"that's|there's|here's|let's|who's|what's|how's|where's|"
    r"could've|should've|would've|might've|must've"
    r")\b",
    re.IGNORECASE,
)

EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FFFF"  # misc symbols and pictographs
    r"\U00002600-\U000027BF"   # misc symbols
    r"\U0001F600-\U0001F64F"   # emoticons
    r"\U0001F680-\U0001F6FF"   # transport & map
    r"]+",
    re.UNICODE,
)

POLITENESS_MARKERS = {
    "please", "thank you", "thanks", "appreciate", "grateful", "gratitude",
    "kindly", "excuse me", "pardon", "sorry", "apologies", "I apologize",
    "would you mind", "if you don't mind", "at your convenience",
}

MODAL_VERBS = {"may", "shall", "would", "might", "ought", "should", "must", "will", "can", "could"}

FORMAL_MODAL_VERBS = {"may", "shall", "would", "might", "ought"}

# Passive voice: forms of 'be' + past participle
PASSIVE_RE = re.compile(
    r"\b(is|are|was|were|be|been|being)\s+(\w+ed|written|done|made|sent|given|"
    r"taken|shown|seen|known|found|told|asked|used|based|formed|created|"
    r"provided|required|included|considered|expected|designed|called)\b",
    re.IGNORECASE,
)

# Simple noun-phrase detector: optional determiner + optional adjectives + noun
NP_RE = re.compile(
    r"\b(the|a|an|this|that|these|those|my|your|its|our|their)?\s*"
    r"(?:[A-Z]?[a-z]+(?:ly|ive|ful|ous|al|ic|ent|ant)?\s+)*"
    r"([A-Z]?[a-z]{3,}(?:tion|ment|ness|ity|ance|ence|ship|hood|dom|ist|ism))\b",
)

SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")


class StyleDetector:
    """
    Analyzes a text string and returns numeric scores per communication style.

    Scores are in [0, 1]. `formal_score + informal_score` approximately sum to 1;
    `human_score` and `corporate_score` are derived from the same signals.
    """

    def __init__(self, load_ml_model: bool = False) -> None:
        # ML model is lazy-loaded on first call; never loaded at startup
        self._ml_model = None
        self._load_ml_model = load_ml_model  # hint: try to load when first needed

    # ── Public API ───────────────────────────────────────────────────────────

    def detect(self, text: str) -> Dict[str, Any]:
        """Analyze text and return a full style detection report."""
        if not text or not text.strip():
            return self._empty_result()

        rule_signals = self._extract_rule_signals(text)
        syntax_signals = self._extract_syntax_signals(text)
        ml_formal_score = self._ml_formality_score(text)

        return self._compute_scores(text, rule_signals, syntax_signals, ml_formal_score)

    def detect_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze a list of texts and return one report per text."""
        return [self.detect(t) for t in texts]

    # ── Feature extraction ───────────────────────────────────────────────────

    def _extract_rule_signals(self, text: str) -> Dict[str, float]:
        tokens = re.findall(r"\b\w+\b", text.lower())
        token_count = max(len(tokens), 1)

        slang_count = sum(1 for t in tokens if t in SLANG_WORDS)
        contraction_count = len(CONTRACTION_RE.findall(text))
        emoji_count = len(EMOJI_RE.findall(text))
        politeness_count = sum(
            1 for marker in POLITENESS_MARKERS if marker.lower() in text.lower()
        )
        exclamation_count = text.count("!")
        question_count = text.count("?")

        return {
            "slang_ratio": slang_count / token_count,
            "contraction_ratio": contraction_count / token_count,
            "emoji_ratio": min(emoji_count / max(len(text) / 20, 1), 1.0),
            "politeness_ratio": min(politeness_count / 5, 1.0),
            "exclamation_ratio": min(exclamation_count / max(token_count / 10, 1), 1.0),
            "question_ratio": min(question_count / max(token_count / 10, 1), 1.0),
        }

    def _extract_syntax_signals(self, text: str) -> Dict[str, float]:
        """Extract advanced syntax-based formality signals."""
        sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
        tokens = re.findall(r"\b\w+\b", text.lower())
        token_count = max(len(tokens), 1)

        # ── Sentence length variance ──────────────────────────────────────
        sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences if s]
        if len(sentence_lengths) >= 2:
            length_variance = statistics.stdev(sentence_lengths)
            # Low variance = consistent long sentences = formal signal
            # Normalize: 0 variance → 1.0 (very formal), >20 → 0.0 (informal)
            norm_variance = max(0.0, 1.0 - length_variance / 20.0)
        else:
            length_variance = 0.0
            norm_variance = 0.5

        avg_sentence_length = (
            statistics.mean(sentence_lengths) if sentence_lengths else 0.0
        )
        # Longer avg sentences → more formal (normalize 0-40 words range)
        length_formal_signal = min(avg_sentence_length / 25.0, 1.0)

        # ── Passive voice ─────────────────────────────────────────────────
        passive_matches = PASSIVE_RE.findall(text)
        passive_ratio = min(len(passive_matches) / max(len(sentences), 1), 1.0)

        # ── Modal verbs ───────────────────────────────────────────────────
        formal_modal_count = sum(1 for t in tokens if t in FORMAL_MODAL_VERBS)
        modal_count = sum(1 for t in tokens if t in MODAL_VERBS)
        formal_modal_ratio = formal_modal_count / token_count
        modal_formality = (formal_modal_count / max(modal_count, 1)) if modal_count > 0 else 0.5

        # ── Noun phrase density ───────────────────────────────────────────
        np_matches = NP_RE.findall(text)
        noun_phrase_density = min(len(np_matches) / max(len(sentences), 1) / 3.0, 1.0)

        return {
            "passive_voice_ratio": round(passive_ratio, 3),
            "formal_modal_ratio": round(formal_modal_ratio, 3),
            "modal_formality_score": round(modal_formality, 3),
            "sentence_length_variance": round(length_variance, 2),
            "norm_length_variance": round(norm_variance, 3),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "length_formal_signal": round(length_formal_signal, 3),
            "noun_phrase_density": round(noun_phrase_density, 3),
            # Combined syntax formality signal (weighted average)
            "syntax_formality": round(
                0.25 * passive_ratio
                + 0.25 * modal_formality
                + 0.25 * norm_variance
                + 0.25 * noun_phrase_density,
                3,
            ),
        }

    # ── ML model ─────────────────────────────────────────────────────────────

    def _ml_formality_score(self, text: str) -> Optional[float]:
        """
        Returns [0,1] formal score using s-nlp/roberta-base-formality-ranker.
        Returns None if model unavailable.
        """
        if not self._load_ml_model:
            return None
        try:
            if self._ml_model is None:
                from transformers import pipeline  # type: ignore
                self._ml_model = pipeline(
                    "text-classification",
                    model="s-nlp/roberta-base-formality-ranker",
                )
            # Split into sentences and score each; average
            sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if len(s.strip()) > 5]
            if not sentences:
                sentences = [text[:512]]
            scores = []
            for sentence in sentences[:10]:  # cap at 10 sentences
                result = self._ml_model(sentence[:512])[0]
                # Model returns label FORMAL/INFORMAL with score
                label = result.get("label", "").upper()
                conf = float(result.get("score", 0.5))
                scores.append(conf if "FORMAL" in label else 1.0 - conf)
            return sum(scores) / len(scores)
        except Exception:
            return None

    # ── Score computation ─────────────────────────────────────────────────────

    def _compute_scores(
        self,
        text: str,
        rule: Dict[str, float],
        syntax: Dict[str, float],
        ml_score: Optional[float],
    ) -> Dict[str, Any]:

        # ── Detect formal vocabulary presence (anti-informal signal)
        formal_vocab = {
            "utilize", "commence", "endeavour", "endeavor", "furthermore",
            "therefore", "however", "moreover", "additionally", "subsequently",
            "accordingly", "henceforth", "nevertheless", "notwithstanding",
            "pursuant", "aforementioned", "ascertain", "facilitate",
        }
        tokens_lower = set(re.findall(r"\b\w+\b", text.lower()))
        formal_vocab_ratio = len(tokens_lower & formal_vocab) / max(len(tokens_lower), 1)

        # ── Base informal signal (higher = more informal)
        # Boosted multipliers: slang 15x, contractions 12x, emoji 3x
        informal_signal = (
            0.30 * min(rule["slang_ratio"] * 15, 1.0)
            + 0.25 * min(rule["contraction_ratio"] * 12, 1.0)
            + 0.15 * min(rule["emoji_ratio"] * 3, 1.0)
            + 0.15 * rule["exclamation_ratio"]
            + 0.10 * (1.0 - syntax["syntax_formality"])
            + 0.05 * (1.0 - formal_vocab_ratio * 10)
        )
        informal_signal = min(max(informal_signal, 0.0), 1.0)

        # ── Base formal signal
        formal_signal = (
            0.30 * syntax["syntax_formality"]
            + 0.20 * rule["politeness_ratio"]
            + 0.15 * min(formal_vocab_ratio * 10, 1.0)
            + 0.15 * (1.0 - min(rule["slang_ratio"] * 12, 1.0))
            + 0.10 * (1.0 - min(rule["contraction_ratio"] * 8, 1.0))
            + 0.10 * (1.0 - rule["exclamation_ratio"])
        )
        formal_signal = min(max(formal_signal, 0.0), 1.0)

        # Blend with ML score if available
        if ml_score is not None:
            formal_signal = 0.6 * formal_signal + 0.4 * ml_score
            informal_signal = 0.6 * informal_signal + 0.4 * (1.0 - ml_score)

        # Normalize to sum ≈ 1
        total = formal_signal + informal_signal
        if total > 0:
            formal_score = formal_signal / total
            informal_score = informal_signal / total
        else:
            formal_score = informal_score = 0.5

        # ── HARD OVERRIDE: clear informal markers force minimum score ──
        # If text has ANY slang (>3% ratio) or emojis (>2% ratio), it is
        # overwhelmingly likely to be informal regardless of syntax.
        if rule["slang_ratio"] > 0.03 or rule["emoji_ratio"] > 0.02:
            informal_score = max(informal_score, 0.65)
            formal_score = 1.0 - informal_score
        # If text has formal vocabulary and NO contractions/slang, force formal
        if formal_vocab_ratio > 0.02 and rule["contraction_ratio"] < 0.01 and rule["slang_ratio"] < 0.01:
            formal_score = max(formal_score, 0.65)
            informal_score = 1.0 - formal_score

        # Human score: empathetic + conversational
        human_score = min(
            0.35 * rule["politeness_ratio"]
            + 0.25 * rule["question_ratio"] * 4
            + 0.20 * rule["contraction_ratio"] * 3
            + 0.20 * (1.0 - rule["slang_ratio"] * 5),
            1.0,
        )
        human_score = max(human_score, 0.0)

        # Corporate score: direct, no emotion, structured
        corporate_score = min(
            0.35 * syntax["syntax_formality"]
            + 0.25 * (1.0 - rule["emoji_ratio"])
            + 0.25 * (1.0 - rule["exclamation_ratio"])
            + 0.15 * syntax["noun_phrase_density"],
            1.0,
        )

        # ── Determine dominant style (3-way: formal / informal / mixed) ──
        # Primary decision: formal vs informal
        gap = abs(formal_score - informal_score)
        is_mixed = gap < 0.15
        if is_mixed:
            dominant_style = "mixed"
        elif formal_score > informal_score:
            dominant_style = "formal"
        else:
            dominant_style = "informal"

        confidence = gap

        return {
            "formal_score": round(formal_score, 3),
            "informal_score": round(informal_score, 3),
            "human_score": round(human_score, 3),
            "corporate_score": round(corporate_score, 3),
            "dominant_style": dominant_style,
            "is_mixed": is_mixed,
            "confidence": round(confidence, 3),
            "ml_formality_score": round(ml_score, 3) if ml_score is not None else None,
            "syntax_signals": syntax,
            "rule_signals": {k: round(v, 3) for k, v in rule.items()},
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "formal_score": 0.5,
            "informal_score": 0.5,
            "human_score": 0.5,
            "corporate_score": 0.5,
            "dominant_style": "unknown",
            "is_mixed": True,
            "confidence": 0.0,
            "ml_formality_score": None,
            "syntax_signals": {},
            "rule_signals": {},
        }
