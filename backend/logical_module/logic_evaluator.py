"""
Self-Verifier — judge-loop that asks the model to re-evaluate its own answer.

Implements the "self-evaluation prompting" technique from research showing
that models catch ~30% of their own errors when given a structured
meta-cognitive prompt.

The verifier sends a specially crafted prompt asking the model:
  "You answered X.  How confident are you that this is correct? Rate 0–100."

It then robustly extracts a numeric score and converts it to V ∈ [0, 1].

Integration notes
─────────────────
V is an optional signal.  If the model does not produce a numeric score
(e.g. very short models), it returns 0.5 (neutral) and logs a warning.
The AbstentionPolicy handles V=None gracefully.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import torch  # type: ignore
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ─────────────────────────────────────────────────────────────────────────────

_VERIFY_TEMPLATE = """\
Original question: {question}

Your answer: {answer}

Rate your confidence that the above answer is correct on a scale from 0 to 100,
where 0 means completely wrong and 100 means completely correct.

Respond with ONLY a single integer between 0 and 100. No explanation.
Confidence score:"""

_VERIFY_TEMPLATE_VERBOSE = """\
Original question: {question}

Your previous answer: {answer}

Carefully review your answer. Consider:
- Is the answer factually accurate?
- Is the reasoning valid and complete?
- Could there be a different, better answer?

On a scale from 0 (definitely wrong) to 100 (definitely correct),
what confidence score do you assign to your answer?

IMPORTANT: End your response with a line "Score: <number>" where <number> is 0–100.
"""


# ─────────────────────────────────────────────────────────────────────────────
# SelfVerifier
# ─────────────────────────────────────────────────────────────────────────────

class SelfVerifier:
    """
    Constructs a meta-cognitive verification prompt and extracts V ∈ [0, 1].

    Args:
        verbose:          Use the longer, more context-rich verification prompt.
        max_new_tokens:   Token budget for the verification response.
        temperature:      Sampling temp for verification (lower = more deterministic).
    """

    def __init__(
        self,
        verbose: bool = False,
        max_new_tokens: int = 80,
        temperature: float = 0.2,
    ) -> None:
        self._verbose = verbose
        self._max_new_tokens = max_new_tokens
        self._temperature = temperature

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(
        self,
        model,
        tokenizer,
        question: str,
        answer: str,
    ) -> Tuple[float, dict]:
        """
        Ask the model to self-evaluate its answer.

        Args:
            model:     HuggingFace causal-LM.
            tokenizer: Corresponding tokenizer.
            question:  Original question text.
            answer:    The model's candidate answer.

        Returns:
            (V, meta) — V ∈ [0, 1], meta with diagnostics.
        """
        prompt = self._build_verification_prompt(question, answer)

        if not TORCH_AVAILABLE:
            logger.warning("torch not available; skipping self-verification.")
            return 0.5, {"method": "unavailable"}

        try:
            response_text = self._run_model(model, tokenizer, prompt)
            score, raw = self._extract_score(response_text)
            return score, {
                "method": "self_verification",
                "raw_response": response_text[:200],
                "raw_extracted": raw,
                "V": score,
            }
        except Exception as exc:
            logger.warning("Self-verification failed: %s", exc)
            return 0.5, {"method": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_verification_prompt(self, question: str, answer: str) -> str:
        """Select and fill the verification prompt template."""
        template = _VERIFY_TEMPLATE_VERBOSE if self._verbose else _VERIFY_TEMPLATE
        return template.format(
            question=question.strip()[:600],   # truncate to avoid context overflow
            answer=answer.strip()[:400],
        )

    # ------------------------------------------------------------------
    # Model call
    # ------------------------------------------------------------------

    def _run_model(self, model, tokenizer, prompt: str) -> str:
        """Run the model on the verification prompt and return decoded text."""
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        input_len = inputs["input_ids"].shape[1]
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=self._max_new_tokens,
                do_sample=self._temperature > 0,
                temperature=self._temperature if self._temperature > 0 else 1.0,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        new_ids = out[0][input_len:]
        return tokenizer.decode(new_ids, skip_special_tokens=True).strip()

    # ------------------------------------------------------------------
    # Score extractor
    # ------------------------------------------------------------------

    def _extract_score(self, response_text: str) -> Tuple[float, Optional[str]]:
        """
        Robustly extract a 0–100 integer from the model's verification response.

        Tries in order:
          1. "Score: <number>"  pattern (verbose template)
          2. Lone integer on its own line
          3. First integer in the entire response
          4. Falls back to 50 (neutral)

        Returns:
            (V ∈ [0, 1], raw_match_string)
        """
        text = response_text.strip()

        # Pattern 1: "Score: 75" or "score:75"
        m = re.search(r"[Ss]core\s*:\s*(\d{1,3})", text)
        if m:
            return self._clamp_score(int(m.group(1))), m.group(0)

        # Pattern 2: lone integer on a line
        for line in text.splitlines():
            stripped = line.strip()
            if re.fullmatch(r"\d{1,3}", stripped):
                return self._clamp_score(int(stripped)), stripped

        # Pattern 3: first integer anywhere
        m = re.search(r"\b(\d{1,3})\b", text)
        if m:
            candidate = int(m.group(1))
            if 0 <= candidate <= 100:
                return self._clamp_score(candidate), m.group(1)

        logger.debug("Could not extract a numeric score from: %r", text[:100])
        return 0.5, None

    @staticmethod
    def _clamp_score(raw_int: int) -> float:
        """Convert integer 0–100 to float ∈ [0, 1], clamped."""
        clamped = max(0, min(100, raw_int))
        return round(clamped / 100.0, 4)
