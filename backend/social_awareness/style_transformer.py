"""
Style Transformer — rewrites text to match a target communication style.

Features:
  - Batch-capable: accepts List[str]
  - Rule-based substitutions (always available, fast)
  - LLM prompt-engineering rewrite (optional, uses local model)
  - Semantic similarity guard via sentence-transformers (lazy-loaded)
    → if similarity < threshold, falls back to rule-based result
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional

# ── Contraction tables ────────────────────────────────────────────────────────

# Expand contractions (informal → formal)
CONTRACTION_EXPANSIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "won't": "will not", "wouldn't": "would not", "can't": "cannot",
    "couldn't": "could not", "shouldn't": "should not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "I'm": "I am", "I've": "I have", "I'll": "I will", "I'd": "I would",
    "you're": "you are", "you've": "you have", "you'll": "you will",
    "he's": "he is", "she's": "she is", "it's": "it is",
    "we're": "we are", "we've": "we have", "we'll": "we will",
    "they're": "they are", "they've": "they have", "they'll": "they will",
    "that's": "that is", "there's": "there is", "here's": "here is",
    "let's": "let us", "who's": "who is", "what's": "what is",
    "could've": "could have", "should've": "should have", "would've": "would have",
    "gonna": "going to", "wanna": "want to", "gotta": "have got to",
    "dunno": "do not know", "ain't": "is not",
}

# Compress expansions (formal → informal)
CONTRACTION_COMPRESSIONS = {v: k for k, v in CONTRACTION_EXPANSIONS.items()
                             if k not in {"gonna", "wanna", "gotta", "dunno", "ain't"}}

# Opener phrase substitutions per style
OPENER_MAP: Dict[str, Dict[str, str]] = {
    "formal": {
        "sure!": "Certainly.",
        "sure,": "Certainly,",
        "absolutely!": "Certainly.",
        "of course!": "Of course.",
        "hey,": "Greetings,",
        "hi,": "Hello,",
        "yeah,": "Indeed,",
        "yep,": "Yes,",
        "no problem!": "This will not be an issue.",
        "no worries!": "There is no cause for concern.",
        "cool!": "Acknowledged.",
        "awesome!": "Excellent.",
        "sounds good!": "Understood.",
    },
    "informal": {
        "certainly.": "Sure!",
        "certainly,": "Sure,",
        "greetings,": "Hey,",
        "indeed,": "Yeah,",
        "this will not be an issue.": "No problem!",
        "there is no cause for concern.": "No worries!",
        "understood.": "Sounds good!",
    },
    "corporate": {
        "sure!": "Acknowledged.",
        "absolutely!": "Confirmed.",
        "of course!": "Noted.",
        "hey,": "To all parties,",
        "hi,": "Hello,",
        "no problem!": "This is within scope.",
        "no worries!": "This is manageable.",
    },
    "human": {
        "certainly.": "Of course!",
        "greetings,": "Hi there,",
        "indeed,": "That's right,",
        "this will not be an issue.": "Don't worry, I've got you!",
    },
}

SLANG_REPLACEMENTS = {
    "gonna": "going to", "wanna": "want to", "gotta": "have to",
    "ya": "you", "yep": "yes", "nope": "no", "kinda": "kind of",
    "sorta": "sort of", "lemme": "let me", "gimme": "give me",
    "dunno": "I don't know", "wassup": "what is happening",
    "lol": "", "lmao": "", "omg": "oh my",
    "tbh": "to be honest", "imo": "in my opinion", "btw": "by the way",
    "fyi": "for your information", "ngl": "", "fr": "", "rn": "right now",
    "lowkey": "", "highkey": "", "brb": "", "bestie": "",
}

# Formal vocabulary → casual replacements (Fix 2: deep word-level transforms)
FORMAL_TO_INFORMAL = {
    "utilize": "use", "utilise": "use",
    "purchase": "buy", "require": "need",
    "commence": "start", "commence": "start",
    "ascertain": "figure out", "endeavour": "try",
    "endeavor": "try", "facilitate": "help with",
    "demonstrate": "show", "subsequently": "then",
    "approximately": "about", "sufficient": "enough",
    "regarding": "about", "regarding": "about",
    "therefore": "so", "however": "but",
    "furthermore": "also", "moreover": "also",
    "additionally": "also", "nevertheless": "still",
    "consequently": "so", "henceforth": "from now on",
    "accordingly": "so", "notwithstanding": "even though",
    "pursuant": "following", "aforementioned": "that",
    "implement": "set up", "initiate": "start",
    "terminate": "end", "allocate": "give",
    "substantial": "big", "numerous": "lots of",
    "diminish": "shrink", "comprehend": "get",
    "expedite": "speed up", "prioritize": "focus on",
    "acknowledge": "note", "incorporate": "add",
    "preliminary": "early", "subsequent": "next",
    "prior": "before", "optimal": "best",
    "modifications": "changes", "modification": "change",
    "assistance": "help", "documentation": "docs",
    "functionality": "features", "methodology": "method",
}

# Informal vocabulary → formal replacements
INFORMAL_TO_FORMAL = {
    "use": "utilize", "buy": "purchase",
    "need": "require", "start": "commence",
    "try": "endeavour", "show": "demonstrate",
    "about": "approximately", "enough": "sufficient",
    "so": "therefore", "but": "however",
    "also": "additionally", "still": "nevertheless",
    "end": "terminate", "give": "allocate",
    "big": "substantial", "get": "obtain",
    "help": "assistance", "docs": "documentation",
    "set up": "implement", "speed up": "expedite",
    "changes": "modifications", "method": "methodology",
    "next": "subsequent", "before": "prior",
    "best": "optimal", "focus on": "prioritize",
}

# Formal opening phrases to kill when going informal
FORMAL_OPENER_KILLERS = [
    (r'^Certainly[,.]?\s*', 'Sure! '),
    (r'^Indeed[,.]?\s*', 'Yeah, '),
    (r'^Of course[,.]?\s*', 'yeah, '),
    (r'^It is (important|worth|imperative) (to note|noting|mentioning) that\s*', 'heads up — '),
    (r'^It should be noted that\s*', 'btw '),
    (r'^In order to\s+', 'To '),
    (r'^Furthermore,?\s*', 'also, '),
    (r'^However,?\s*', 'but '),
    (r'^Therefore,?\s*', 'so '),
    (r'^Additionally,?\s*', 'also '),
    (r'^Moreover,?\s*', 'plus '),
    (r'^Nevertheless,?\s*', 'still tho, '),
    (r'^Consequently,?\s*', 'so basically '),
    (r'^I would be pleased to\s+', "I'll "),
    (r'^I am pleased to\s+', "I'll "),
    (r'^Kindly\s+', ''),
    (r'^Please note that\s*', 'heads up — '),
    (r'^As per\s+', 'based on '),
    (r'^In accordance with\s+', 'following '),
]

# LLM prompt templates per target style
STYLE_PROMPTS: Dict[str, str] = {
    "formal": (
        "Rewrite the following text in strict formal English. "
        "Remove all slang, contractions, and casual phrasing. "
        "Use professional vocabulary, complete sentences, and a neutral tone. "
        "Do NOT change the meaning or add new information.\n\nText: {text}\n\nFormal version:"
    ),
    "informal": (
        "Rewrite the following text in a casual, friendly tone. "
        "Use natural contractions and conversational language. "
        "Keep it short and friendly. "
        "Do NOT change the meaning or add new information.\n\nText: {text}\n\nCasual version:"
    ),
    "corporate": (
        "Rewrite the following text in a direct, concise corporate style. "
        "Remove all emotion and filler words. Use active voice where possible. "
        "Be precise and professional. "
        "Do NOT change the meaning or add new information.\n\nText: {text}\n\nCorporate version:"
    ),
    "human": (
        "Rewrite the following text to sound warm, empathetic and conversational. "
        "Use first-person, acknowledge the reader's perspective, and use natural phrasing. "
        "Do NOT change the meaning or add new information.\n\nText: {text}\n\nEmpathetic version:"
    ),
}

SIMILARITY_THRESHOLD = 0.75  # cosine similarity; below this → fall back to rule-based


class StyleTransformer:
    """
    Rewrites text to match a target style. Batch-capable.
    Lazy-loads embedder and LLM model on first use.
    """

    def __init__(self) -> None:
        self._embedder = None
        self._llm_model = None

    # ── Public API ────────────────────────────────────────────────────────────

    def transform(
        self,
        texts: List[str],
        target_style: str,
        use_llm: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Transform a list of texts to the target style.

        Args:
            texts:        list of input strings
            target_style: 'formal' | 'informal' | 'corporate' | 'human'
            use_llm:      attempt LLM rewrite (requires local model to be loaded)

        Returns:
            list of TransformResult dicts
        """
        target_style = target_style.lower()
        return [self._transform_one(t, target_style, use_llm) for t in texts]

    # ── Single-text pipeline ──────────────────────────────────────────────────

    def _transform_one(self, text: str, target_style: str, use_llm: bool) -> Dict[str, Any]:
        if not text or not text.strip():
            return self._empty_result(text, target_style)

        # Step 1: Rule-based substitutions (always runs)
        rule_result = self._rule_based_transform(text, target_style)

        # Step 2: Optional LLM rewrite
        llm_result: Optional[str] = None
        if use_llm:
            llm_result = self._llm_transform(text, target_style)

        # Step 3: Pick candidate (prefer LLM if available)
        candidate = llm_result if llm_result else rule_result
        method = "llm_rewrite" if llm_result else "rule_based"

        # Step 4: Semantic similarity guard
        similarity = self._compute_similarity(text, candidate)
        meaning_preserved = similarity >= SIMILARITY_THRESHOLD

        if not meaning_preserved and llm_result:
            # LLM changed meaning too much — fall back to rule-based
            candidate = rule_result
            method = "rule_based_fallback"
            similarity = self._compute_similarity(text, candidate)
            meaning_preserved = similarity >= SIMILARITY_THRESHOLD

        return {
            "original": text,
            "transformed": candidate,
            "target_style": target_style,
            "similarity_score": round(similarity, 3),
            "meaning_preserved": meaning_preserved,
            "method": method,
        }

    # ── Rule-based transform ──────────────────────────────────────────────────

    def _rule_based_transform(self, text: str, target_style: str) -> str:
        result = text

        if target_style in ("formal", "corporate"):
            # Expand contractions
            for contraction, expansion in CONTRACTION_EXPANSIONS.items():
                result = re.sub(
                    r"\b" + re.escape(contraction) + r"\b",
                    expansion, result, flags=re.IGNORECASE,
                )
            # Replace slang
            for slang, replacement in SLANG_REPLACEMENTS.items():
                result = re.sub(
                    r"\b" + re.escape(slang) + r"\b",
                    replacement, result, flags=re.IGNORECASE,
                )
            # Replace informal words with formal equivalents
            for informal, formal in INFORMAL_TO_FORMAL.items():
                result = re.sub(
                    r"\b" + re.escape(informal) + r"\b",
                    formal, result, flags=re.IGNORECASE,
                )
            # Remove emojis entirely
            result = re.sub(
                r"[\U0001F300-\U0001FFFF\U00002600-\U000027BF"
                r"\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]+",
                "", result,
            )
            # Remove excessive punctuation
            result = re.sub(r"!{2,}", ".", result)
            result = re.sub(r"!(?=\s|$)", ".", result)
            # Remove casual filler words at sentence boundaries
            result = re.sub(r"(?i)\b(like,?\s+)?(honestly|basically|literally)\b[,]?\s*", "", result)

        elif target_style in ("informal", "human"):
            # Compress formal expansions into contractions
            for expansion, contraction in CONTRACTION_COMPRESSIONS.items():
                result = re.sub(
                    r"\b" + re.escape(expansion) + r"\b",
                    contraction, result, flags=re.IGNORECASE,
                )
            # Replace formal vocabulary with casual equivalents
            for formal, informal in FORMAL_TO_INFORMAL.items():
                result = re.sub(
                    r"\b" + re.escape(formal) + r"\b",
                    informal, result, flags=re.IGNORECASE,
                )
            # Kill formal opening phrases
            for pattern, replacement in FORMAL_OPENER_KILLERS:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            # Force contractions on common expansions the model might still output
            force_contractions = [
                (r"\bdo not\b", "don't"), (r"\bcannot\b", "can't"),
                (r"\bwill not\b", "won't"), (r"\bit is\b", "it's"),
                (r"\bI am\b", "I'm"), (r"\bthey are\b", "they're"),
                (r"\bwe are\b", "we're"), (r"\byou are\b", "you're"),
                (r"\bhe is\b", "he's"), (r"\bshe is\b", "she's"),
                (r"\bthat is\b", "that's"), (r"\bthere is\b", "there's"),
                (r"\bI have\b", "I've"), (r"\bI will\b", "I'll"),
                (r"\bI would\b", "I'd"), (r"\bwould not\b", "wouldn't"),
                (r"\bcould not\b", "couldn't"), (r"\bshould not\b", "shouldn't"),
            ]
            for pattern, repl in force_contractions:
                result = re.sub(pattern, repl, result, flags=re.IGNORECASE)

        # Apply opener phrase substitutions (style-specific openers)
        openers = OPENER_MAP.get(target_style, {})
        for original_opener, replacement_opener in openers.items():
            result = re.sub(
                r"(?i)(^|\.\s+)" + re.escape(original_opener),
                lambda m: m.group(1) + replacement_opener,
                result,
            )

        # Clean up double spaces and strip
        result = re.sub(r" {2,}", " ", result).strip()
        return result

    # ── LLM transform ─────────────────────────────────────────────────────────

    def _llm_transform(self, text: str, target_style: str) -> Optional[str]:
        """Attempt a prompt-engineering-based rewrite using the local model."""
        try:
            from ethos_testing.local_model import get_model  # type: ignore
            model = get_model()
            prompt_template = STYLE_PROMPTS.get(target_style, STYLE_PROMPTS["formal"])
            prompt = prompt_template.format(text=text)
            response = model.respond(prompt, max_new_tokens=200, temperature=0.3)
            # Strip the prompt echo if needed
            if response.startswith(prompt):
                response = response[len(prompt):].strip()
            return response.strip() if response.strip() else None
        except Exception:
            return None

    # ── Semantic similarity ───────────────────────────────────────────────────

    def _compute_similarity(self, text_a: str, text_b: str) -> float:
        """Cosine similarity between embeddings. Falls back to character overlap."""
        try:
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            emb = self._embedder.encode([text_a, text_b], convert_to_tensor=False)
            import numpy as np
            a, b = emb[0], emb[1]
            cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
            return max(0.0, min(cos, 1.0))
        except Exception:
            return self._char_overlap_similarity(text_a, text_b)

    def _char_overlap_similarity(self, a: str, b: str) -> float:
        """Fallback: Jaccard similarity on word sets."""
        set_a = set(re.findall(r"\b\w+\b", a.lower()))
        set_b = set(re.findall(r"\b\w+\b", b.lower()))
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _empty_result(self, text: str, target_style: str) -> Dict[str, Any]:
        return {
            "original": text,
            "transformed": text,
            "target_style": target_style,
            "similarity_score": 1.0,
            "meaning_preserved": True,
            "method": "passthrough",
        }
