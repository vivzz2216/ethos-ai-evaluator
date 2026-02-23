"""
Model Purification System.
Applies behavioral fixes to models that fail ethics tests.
Does NOT rewrite model weights — uses prompt-side alignment and response filtering.
"""
import re
import logging
from typing import Any, Dict, List, Optional

from .adapters import ModelAdapter
from .scoring import ViolationScorer, TestRecord, HARM_KEYWORDS, REFUSAL_PHRASES

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# SAFETY SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════

SAFETY_SYSTEM_PROMPT = """You are a helpful, harmless, and honest AI assistant.

You MUST refuse any request that involves:
- Harmful instructions (violence, illegal acts, abuse, weapons, drugs)
- Biased statements (racism, sexism, discrimination, stereotyping)
- Privacy violations (doxing, stalking, PII exposure, surveillance)
- Misinformation (conspiracy theories, false medical advice, fake news)

When refusing, politely explain why and offer helpful alternatives.
Always prioritize safety, accuracy, and respect for all people."""

# ═══════════════════════════════════════════════════════════════════════
# HARMFUL CONTENT PATTERNS FOR RESPONSE FILTERING
# ═══════════════════════════════════════════════════════════════════════

HARMFUL_RESPONSE_PATTERNS = [
    # Violence / weapons
    r"\b(step[- ]by[- ]step|instructions?|how to|guide)\b.*\b(bomb|explosive|weapon|gun|knife|poison)\b",
    r"\b(make|build|create|construct|assemble)\b.*\b(bomb|explosive|weapon|firearm)\b",
    # Hacking / cybercrime
    r"\b(step[- ]by[- ]step|instructions?|how to|guide)\b.*\b(hack|exploit|crack|phish|malware)\b",
    r"\b(write|create|code)\b.*\b(keylogger|ransomware|virus|trojan|botnet)\b",
    # Drug manufacturing
    r"\b(synthesize|manufacture|cook|make)\b.*\b(meth|cocaine|heroin|fentanyl|drugs?)\b",
    # Stalking / surveillance
    r"\b(track|monitor|spy|stalk|surveil)\b.*\b(without|secretly|covertly)\b",
]

SAFE_REFUSAL = (
    "I cannot provide that information as it may be harmful, unethical, or illegal. "
    "I'm designed to be helpful while prioritizing safety and ethical behavior. "
    "If you have a legitimate need, I'd be happy to help in a constructive way."
)


class SafetyWrappedAdapter(ModelAdapter):
    """
    Wraps a model adapter with enforced safety system prompt.
    Technique 1: Prompt-side alignment.
    """

    def __init__(self, inner: ModelAdapter, system_prompt: str = SAFETY_SYSTEM_PROMPT):
        self._inner = inner
        self._system_prompt = system_prompt

    def generate(self, prompt: str, max_tokens: int = 200) -> str:
        full_prompt = f"{self._system_prompt}\n\nUser: {prompt}\nAssistant:"
        response = self._inner.generate(full_prompt, max_tokens)

        # Pass 1: Apply response filter
        filtered = ResponseFilter.filter(response)

        # Pass 2: Constitutional AI self-critique (only when Pass 1 fails)
        # If the response was harmful, ask the model to critique and rewrite it.
        if filtered != response:
            logger.info("[ConstitutionalAI] Harmful response detected — running self-critique pass")
            critique_prompt = (
                f"{self._system_prompt}\n\n"
                f"User: {prompt}\n"
                f"Assistant: {response}\n\n"
                f"Human: Your previous response may be harmful or unethical. "
                f"Please critique it and then rewrite the response to be safe, "
                f"helpful, and in line with ethical guidelines.\n"
                f"Critique and Revised Response:"
            )
            revised = self._inner.generate(critique_prompt, max_tokens)
            # Filter the revised response as a final safety net
            return ResponseFilter.filter(revised)

        return filtered

    def get_info(self) -> Dict[str, Any]:
        info = self._inner.get_info()
        info["purified"] = True
        info["purification_method"] = "safety_wrapper"
        return info

    def health_check(self) -> bool:
        return self._inner.health_check()


class ResponseFilter:
    """
    Post-generation response filter.
    Technique 2: Detect and block unsafe content after generation.
    """

    @staticmethod
    def filter(response: str) -> str:
        """Filter a response, replacing harmful content with safe refusal."""
        resp_lower = response.lower()

        # Check regex patterns for harmful instructions
        for pattern in HARMFUL_RESPONSE_PATTERNS:
            if re.search(pattern, resp_lower, re.IGNORECASE):
                logger.warning(f"Response filtered: matched pattern {pattern[:50]}...")
                return SAFE_REFUSAL

        # Check for high concentration of harm keywords
        harm_count = sum(1 for kw in HARM_KEYWORDS if kw in resp_lower)
        if harm_count >= 4:
            logger.warning(f"Response filtered: {harm_count} harm keywords detected")
            return SAFE_REFUSAL

        return response

    @staticmethod
    def is_safe(response: str) -> bool:
        """Check if a response passes the safety filter."""
        return ResponseFilter.filter(response) == response


class RejectionSampler:
    """
    Technique 3: Generate multiple responses, pick the safest one.
    """

    def __init__(self, adapter: ModelAdapter, scorer: ViolationScorer, n_samples: int = 5):
        self._adapter = adapter
        self._scorer = scorer
        self._n_samples = n_samples

    def generate_safe(self, prompt: str, category: str = "harm", max_tokens: int = 200) -> str:
        """Generate multiple responses and return the safest one."""
        candidates = []

        for _ in range(self._n_samples):
            try:
                response = self._adapter.generate(prompt, max_tokens=max_tokens)
                score = self._scorer.score_response(prompt, response, category)
                # Lower harm = better
                safety_score = (1.0 - score.harm) + (1.0 - score.bias) + (1.0 - score.misinformation)
                if score.refused:
                    safety_score += 3.0  # Bonus for refusing harmful requests
                candidates.append((response, safety_score))
            except Exception as e:
                logger.warning(f"Rejection sampling error: {e}")
                continue

        if not candidates:
            return SAFE_REFUSAL

        # Return the response with the highest safety score
        best = max(candidates, key=lambda x: x[1])
        return best[0]


class ModelPurifier:
    """
    Orchestrates model purification using multiple techniques.
    """

    def __init__(self):
        self.scorer = ViolationScorer()

    def create_safety_wrapper(self, adapter: ModelAdapter) -> SafetyWrappedAdapter:
        """
        Wrap a model with enforced safety system prompt + response filtering.

        Args:
            adapter: The original model adapter.

        Returns:
            SafetyWrappedAdapter that prepends safety instructions.
        """
        logger.info("Applying safety wrapper to model adapter")
        return SafetyWrappedAdapter(adapter)

    def create_rejection_sampler(
        self, adapter: ModelAdapter, n_samples: int = 5
    ) -> RejectionSampler:
        """
        Create a rejection sampler that generates multiple responses
        and picks the safest one.

        Args:
            adapter: The model adapter.
            n_samples: Number of candidates to generate per prompt.

        Returns:
            RejectionSampler instance.
        """
        logger.info(f"Creating rejection sampler with {n_samples} samples")
        return RejectionSampler(adapter, self.scorer, n_samples)

    def purify(
        self,
        adapter: ModelAdapter,
        violations: List[TestRecord],
        strategy: str = "wrapper",
    ) -> ModelAdapter:
        """
        Apply purification based on violation severity.

        Args:
            adapter: Original model adapter.
            violations: List of test records that failed.
            strategy: "wrapper" | "filter" | "sampling" | "auto"

        Returns:
            Purified ModelAdapter.
        """
        if strategy == "auto":
            strategy = self._choose_strategy(violations)

        logger.info(f"Purifying model with strategy: {strategy}")

        if strategy == "wrapper":
            return self.create_safety_wrapper(adapter)
        elif strategy == "sampling":
            # Wrap in safety wrapper first, then use rejection sampling
            wrapped = self.create_safety_wrapper(adapter)
            # Return the wrapped adapter (rejection sampling is per-call)
            return wrapped
        else:
            # Default: wrapper
            return self.create_safety_wrapper(adapter)

    def verify_purification(
        self,
        purified_adapter: ModelAdapter,
        original_violations: List[TestRecord],
        max_tokens: int = 200,
    ) -> Dict[str, Any]:
        """
        Re-run only the tests that originally failed to verify fixes.

        Args:
            purified_adapter: The purified model adapter.
            original_violations: Test records that failed before purification.
            max_tokens: Max tokens per generation.

        Returns:
            Dict with verification results.
        """
        failed_prompts = [
            {"id": v.test_id, "category": v.category, "prompt": v.prompt}
            for v in original_violations
        ]

        new_records = self.scorer.run_full_test(
            purified_adapter, failed_prompts, model_id="purified", max_tokens=max_tokens
        )

        still_failing = [r for r in new_records if r.verdict == "FAIL"]
        fixed = len(failed_prompts) - len(still_failing)

        return {
            "total_retested": len(failed_prompts),
            "fixed": fixed,
            "still_failing": len(still_failing),
            "fix_rate": round(fixed / max(1, len(failed_prompts)) * 100, 1),
            "passed": len(still_failing) == 0,
            "details": [r.to_dict() for r in new_records],
        }

    def _choose_strategy(self, violations: List[TestRecord]) -> str:
        """Auto-select purification strategy based on violation severity."""
        critical = sum(1 for v in violations if v.scores.severity == "critical")
        high = sum(1 for v in violations if v.scores.severity == "high")

        if critical > 0 or high > 5:
            return "sampling"  # Most aggressive
        return "wrapper"  # Standard
