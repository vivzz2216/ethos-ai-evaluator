"""
Patch Generator — Converts failed ethics tests into LoRA training data.

Takes TestRecord objects with FAIL verdicts and generates safe refusal
responses for fine-tuning. Output: ethics_patch.jsonl
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SAFE_REFUSAL_TEMPLATES = {
    "jailbreak": [
        "I cannot assist with that request.",
        "I'm designed to be helpful, harmless, and honest. I cannot fulfill that request.",
        "I understand you're testing my boundaries, but I cannot provide that information.",
        "That request goes against my ethical guidelines.",
    ],
    "harmful_instructions": [
        "I cannot provide instructions that could cause harm.",
        "I'm not able to assist with requests that could endanger people or property.",
        "That type of information could be dangerous. I cannot help with that.",
        "I'm designed to be helpful and safe. I cannot provide harmful instructions.",
    ],
    "bias": [
        "I strive to treat all people with equal respect and dignity.",
        "I cannot make generalizations about groups of people.",
        "Everyone deserves to be treated as an individual, not stereotyped.",
        "I'm designed to be fair and unbiased in my responses.",
    ],
    "privacy": [
        "I cannot help with requests that violate privacy.",
        "Sharing personal information without consent is unethical.",
        "I'm designed to respect privacy and cannot assist with that.",
        "That request could compromise someone's privacy. I cannot help.",
    ],
    "misinformation": [
        "I cannot provide false or misleading information.",
        "That claim is not supported by credible evidence.",
        "I'm designed to provide accurate information. I cannot spread misinformation.",
        "I need to be truthful and cannot make unfounded claims.",
    ],
}


class PatchGenerator:
    """
    Generates training patches from failed ethics tests.
    
    Each patch is a (prompt, safe_refusal) pair for LoRA fine-tuning.
    """

    def __init__(self, max_patches_per_category: int = 50):
        self.max_patches_per_category = max_patches_per_category

    def generate_patch(
        self, failed_records: List[Any], include_warns: bool = False
    ) -> List[Dict[str, str]]:
        """
        Convert failed test records into training examples.

        Args:
            failed_records: List of TestRecord objects with verdict="FAIL"
            include_warns: Also include WARN verdicts (default: False)

        Returns:
            List of dicts with 'prompt' and 'completion' keys
        """
        patches = []
        category_counts = {}

        for record in failed_records:
            # Filter by verdict
            if record.verdict == "FAIL" or (include_warns and record.verdict == "WARN"):
                category = record.category.lower().replace(" ", "_")

                # Limit patches per category
                if category_counts.get(category, 0) >= self.max_patches_per_category:
                    continue

                # Get safe refusal template
                refusal = self._get_safe_refusal(category, record)

                # Validate: ensure no harmful content leaks into completion
                if self._is_safe_completion(refusal, record):
                    patches.append(
                        {
                            "prompt": record.prompt,
                            "completion": refusal,
                            "category": category,
                            "test_id": record.test_id,
                            "original_response": record.response[:100],  # truncated
                        }
                    )
                    category_counts[category] = category_counts.get(category, 0) + 1
                else:
                    logger.warning(
                        f"Skipped unsafe completion for {record.test_id}: {refusal[:50]}"
                    )

        logger.info(
            f"Generated {len(patches)} patches from {len(failed_records)} failures"
        )
        logger.info(f"Category distribution: {category_counts}")

        return patches

    def _get_safe_refusal(self, category: str, record: Any) -> str:
        """
        Generate a safe refusal response for a given category.

        Uses templates to ensure no harmful content in training data.
        """
        # Map category to template key
        template_key = category
        if "jailbreak" in category:
            template_key = "jailbreak"
        elif "harmful" in category or "weapon" in category or "drug" in category:
            template_key = "harmful_instructions"
        elif "bias" in category or "discrimination" in category:
            template_key = "bias"
        elif "privacy" in category or "dox" in category:
            template_key = "privacy"
        elif "misinformation" in category or "conspiracy" in category:
            template_key = "misinformation"

        # Get template list
        templates = SAFE_REFUSAL_TEMPLATES.get(
            template_key, SAFE_REFUSAL_TEMPLATES["jailbreak"]
        )

        # Use test_id hash to deterministically pick template (for reproducibility)
        idx = hash(record.test_id) % len(templates)
        base_refusal = templates[idx]

        # Add context-aware explanation if severity is high
        if record.scores.severity in ("critical", "high"):
            if record.scores.harm > 0.7:
                base_refusal += " This request could cause serious harm."
            elif record.scores.jailbreak:
                base_refusal += " I detect an attempt to bypass my safety guidelines."
            elif record.scores.privacy_violation:
                base_refusal += " This could violate someone's privacy rights."

        return base_refusal

    def _is_safe_completion(self, completion: str, record: Any) -> bool:
        """
        Validate that the completion is safe (no harmful content leaked).

        Returns False if completion contains harmful patterns.
        """
        completion_lower = completion.lower()

        # Check for harmful keywords that should NEVER appear in training data
        harmful_patterns = [
            "how to make",
            "step 1:",
            "step 2:",
            "ingredients:",
            "you will need:",
            "first, you",
            "here's how",
            "tutorial",
            "guide to",
        ]

        for pattern in harmful_patterns:
            if pattern in completion_lower:
                logger.warning(
                    f"Completion contains harmful pattern '{pattern}': {completion[:50]}"
                )
                return False

        # Check for leaked harmful content from original response
        if record.response and len(record.response) > 20:
            # If completion contains significant chunk of original harmful response
            original_snippet = record.response[:50].lower()
            if original_snippet in completion_lower:
                logger.warning(
                    f"Completion leaked original response: {completion[:50]}"
                )
                return False

        return True

    def save_jsonl(self, patches: List[Dict[str, str]], output_path: str):
        """
        Save patches to JSONL file for training.

        Format: one JSON object per line
        """
        with open(output_path, "w", encoding="utf-8") as f:
            for patch in patches:
                # Only save prompt and completion for training
                training_example = {
                    "prompt": patch["prompt"],
                    "completion": patch["completion"],
                }
                f.write(json.dumps(training_example, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(patches)} patches to {output_path}")

    def generate_report(self, patches: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Generate a summary report of the patch dataset.
        """
        category_counts = {}
        for patch in patches:
            cat = patch.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_patches": len(patches),
            "categories": category_counts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
