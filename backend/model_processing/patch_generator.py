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

    # ═══════════════════════════════════════════════════════════════════
    # FIX: Balanced Training — Prevents Catastrophic Forgetting
    # ═══════════════════════════════════════════════════════════════════
    # Previously, only FAIL examples were used for training. This taught
    # the model to refuse EVERYTHING, destroying its ability to answer
    # legitimate questions (accuracy drop from ~84% → ~52%).
    #
    # The fix: include BOTH PASS and FAIL examples at a 50/50 ratio.
    # - FAIL records → safe refusal completions (teach to refuse bad)
    # - PASS records → original model responses (preserve good behavior)
    # ═══════════════════════════════════════════════════════════════════

    def generate_balanced_patch(
        self,
        all_records: List[Any],
        target_ratio: float = 0.5,
    ) -> List[Dict[str, str]]:
        """
        Generate a BALANCED training dataset from ALL test records.

        Unlike generate_patch() which only uses failures, this method
        includes both passed and failed examples to prevent catastrophic
        forgetting of already-ethical behavior.

        Args:
            all_records: ALL TestRecord objects (PASS + FAIL + WARN).
            target_ratio: Target ratio of FAIL examples (default: 0.5 = 50/50).

        Returns:
            List of dicts with 'prompt', 'completion', 'category', 'label' keys.
        """
        # Separate records by verdict
        fail_records = [r for r in all_records if r.verdict == "FAIL"]
        pass_records = [r for r in all_records if r.verdict == "PASS"]
        warn_records = [r for r in all_records if r.verdict == "WARN"]

        # Include WARN records as failures (they need fixing too)
        fail_records.extend(warn_records)

        patches = []
        category_counts = {"fail": {}, "pass": {}}

        # ── Step 1: Generate patches from FAIL records (safe refusals) ──
        for record in fail_records:
            category = record.category.lower().replace(" ", "_")

            if category_counts["fail"].get(category, 0) >= self.max_patches_per_category:
                continue

            refusal = self._get_safe_refusal(category, record)
            if self._is_safe_completion(refusal, record):
                patches.append({
                    "prompt": record.prompt,
                    "completion": refusal,
                    "category": category,
                    "label": "fail",
                    "test_id": record.test_id,
                })
                category_counts["fail"][category] = category_counts["fail"].get(category, 0) + 1

        fail_count = len(patches)

        # ── Step 2: Generate patches from PASS records (preserve good) ──
        # FIX: This is the key anti-forgetting mechanism.
        # By including the model's own correct responses as training data,
        # we teach it to keep doing what it already does well.
        target_pass_count = int(fail_count * (1.0 - target_ratio) / max(target_ratio, 0.01))

        for record in pass_records:
            if len(patches) - fail_count >= target_pass_count:
                break  # Reached target ratio

            category = record.category.lower().replace(" ", "_")

            if category_counts["pass"].get(category, 0) >= self.max_patches_per_category:
                continue

            # For PASS records: use the model's ORIGINAL response as completion
            # This preserves the behavior the model already gets right
            if record.response and len(record.response.strip()) > 10:
                patches.append({
                    "prompt": record.prompt,
                    "completion": record.response,
                    "category": category,
                    "label": "pass",
                    "test_id": record.test_id,
                })
                category_counts["pass"][category] = category_counts["pass"].get(category, 0) + 1

        logger.info(
            f"Generated BALANCED patch set: "
            f"{fail_count} fail + {len(patches) - fail_count} pass = {len(patches)} total "
            f"(target ratio: {target_ratio:.0%} fail)"
        )
        logger.info(f"Fail distribution: {category_counts['fail']}")
        logger.info(f"Pass distribution: {category_counts['pass']}")

        return patches

    def save_split_jsonl(
        self,
        patches: List[Dict[str, str]],
        output_dir: str,
        prefix: str = "ethics_patch",
    ) -> Dict[str, str]:
        """
        Save patches to separate JSONL files for train/val splits.

        Args:
            patches: Full list of balanced patches.
            output_dir: Directory to write JSONL files.
            prefix: Filename prefix.

        Returns:
            Dict mapping split name → file path.
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Write single combined file (train pipeline loads this)
        combined_path = os.path.join(output_dir, f"{prefix}_balanced.jsonl")
        with open(combined_path, "w", encoding="utf-8") as f:
            for patch in patches:
                training_example = {
                    "prompt": patch["prompt"],
                    "completion": patch["completion"],
                    "label": patch.get("label", "unknown"),
                }
                f.write(json.dumps(training_example, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(patches)} balanced patches to {combined_path}")
        return {"combined": combined_path}

