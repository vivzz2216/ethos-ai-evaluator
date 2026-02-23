"""
Pipeline split integrity tests.

Verifies that the train/val/test split in adversarial_prompts.py
prevents data leakage and the balanced patch generator produces
the correct mix of pass/fail examples.
"""
import pytest
import sys
from pathlib import Path
from types import SimpleNamespace

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.model_processing.adversarial_prompts import (
    get_split, get_split_stats, get_all_prompts, ADVERSARIAL_PROMPTS,
)
from backend.model_processing.patch_generator import PatchGenerator


class TestDataSplits:
    """Verify train/val/test split integrity."""

    def test_train_split_has_75_prompts(self):
        """Train split should contain exactly 75 prompts (15 × 5)."""
        train = get_split("train")
        assert len(train) == 75, f"Expected 75 train prompts, got {len(train)}"

    def test_val_split_has_25_prompts(self):
        """Validation split should contain exactly 25 prompts (5 × 5)."""
        val = get_split("val")
        assert len(val) == 25, f"Expected 25 val prompts, got {len(val)}"

    def test_test_split_has_25_prompts(self):
        """Test split should contain exactly 25 prompts (5 × 5)."""
        test = get_split("test")
        assert len(test) == 25, f"Expected 25 test prompts, got {len(test)}"

    def test_splits_cover_all_125_prompts(self):
        """All 3 splits combined should cover first 25 prompts per category (125 total)."""
        # Note: HARM_PROMPTS has 36 entries (extra edge cases), but splits
        # only cover indices [0:25] per category. Prompts beyond 25 are
        # reserved for future expansion and intentionally excluded.
        expected_ids = set()
        for category, prompt_list in ADVERSARIAL_PROMPTS.items():
            for i in range(min(25, len(prompt_list))):
                expected_ids.add(f"{category}_{i+1:03d}")

        split_ids = set()
        for split in ("train", "val", "test"):
            split_ids.update(p["id"] for p in get_split(split))

        assert split_ids == expected_ids, (
            f"Splits don't cover expected prompts. "
            f"Missing: {expected_ids - split_ids}, Extra: {split_ids - expected_ids}"
        )

    def test_no_overlap_between_train_and_test(self):
        """CRITICAL: Train and test sets must be completely disjoint."""
        train_ids = {p["id"] for p in get_split("train")}
        test_ids = {p["id"] for p in get_split("test")}
        overlap = train_ids & test_ids
        assert len(overlap) == 0, (
            f"DATA LEAKAGE: {len(overlap)} prompts in BOTH train and test: {overlap}"
        )

    def test_no_overlap_between_train_and_val(self):
        """Train and validation sets must be disjoint."""
        train_ids = {p["id"] for p in get_split("train")}
        val_ids = {p["id"] for p in get_split("val")}
        overlap = train_ids & val_ids
        assert len(overlap) == 0, f"Overlap between train and val: {overlap}"

    def test_no_overlap_between_val_and_test(self):
        """Validation and test sets must be disjoint."""
        val_ids = {p["id"] for p in get_split("val")}
        test_ids = {p["id"] for p in get_split("test")}
        overlap = val_ids & test_ids
        assert len(overlap) == 0, f"Overlap between val and test: {overlap}"

    def test_each_split_has_all_categories(self):
        """Every split must contain prompts from all 5 categories."""
        expected_cats = set(ADVERSARIAL_PROMPTS.keys())
        for split in ("train", "val", "test"):
            cats = {p["category"] for p in get_split(split)}
            assert cats == expected_cats, (
                f"Split '{split}' missing categories: {expected_cats - cats}"
            )

    def test_split_is_deterministic(self):
        """Calling get_split() twice returns same prompts in same order."""
        first = get_split("test")
        second = get_split("test")
        assert first == second, "Split is not deterministic across calls"

    def test_invalid_split_raises(self):
        """Invalid split name should raise ValueError."""
        with pytest.raises(ValueError):
            get_split("invalid")

    def test_split_stats_match(self):
        """get_split_stats() should match actual split sizes."""
        stats = get_split_stats()
        assert stats["train"]["total"] == 75
        assert stats["val"]["total"] == 25
        assert stats["test"]["total"] == 25


class TestBalancedPatchGenerator:
    """Verify balanced PASS+FAIL patch generation."""

    def _make_record(self, test_id, category, verdict, prompt, response):
        """Create a mock TestRecord."""
        scores = SimpleNamespace(
            severity="low" if verdict == "PASS" else "high",
            harm=0.1 if verdict == "PASS" else 0.9,
            jailbreak=verdict == "FAIL",
            privacy_violation=False,
        )
        return SimpleNamespace(
            test_id=test_id,
            category=category,
            verdict=verdict,
            prompt=prompt,
            response=response,
            scores=scores,
        )

    def test_balanced_patch_includes_pass_and_fail(self):
        """Balanced patch must include BOTH pass and fail examples."""
        records = [
            self._make_record("j_001", "jailbreak", "FAIL", "hack?", "Sure, here's how"),
            self._make_record("j_002", "jailbreak", "PASS", "hack?", "I cannot help with that"),
            self._make_record("b_001", "bias", "FAIL", "biased?", "Yes, they are inferior"),
            self._make_record("b_002", "bias", "PASS", "biased?", "No, all people are equal"),
        ]

        gen = PatchGenerator()
        patches = gen.generate_balanced_patch(records, target_ratio=0.5)

        labels = {p["label"] for p in patches}
        assert "fail" in labels, "No FAIL examples in balanced patch"
        assert "pass" in labels, "No PASS examples in balanced patch"

    def test_balanced_patch_ratio(self):
        """Balanced patch should approximate 50/50 ratio."""
        records = []
        for i in range(10):
            records.append(self._make_record(
                f"j_{i:03d}", "jailbreak", "FAIL",
                f"bad prompt {i}", f"harmful response {i}",
            ))
            records.append(self._make_record(
                f"b_{i:03d}", "bias", "PASS",
                f"good prompt {i}", f"This is a proper ethical response number {i}",
            ))

        gen = PatchGenerator()
        patches = gen.generate_balanced_patch(records, target_ratio=0.5)

        fail_count = sum(1 for p in patches if p["label"] == "fail")
        pass_count = sum(1 for p in patches if p["label"] == "pass")
        total = len(patches)

        assert total > 0, "No patches generated"
        # Allow some tolerance (within 20% of 50/50)
        ratio = fail_count / max(total, 1)
        assert 0.3 <= ratio <= 0.7, f"Ratio too skewed: {ratio:.0%} fail"

    def test_pass_examples_use_original_response(self):
        """PASS examples should use the model's original (good) response."""
        records = [
            self._make_record(
                "b_001", "bias", "PASS",
                "Are all people equal?",
                "Yes, all humans deserve equal dignity and respect.",
            ),
        ]

        gen = PatchGenerator()
        patches = gen.generate_balanced_patch(records)

        pass_patches = [p for p in patches if p["label"] == "pass"]
        if pass_patches:
            assert pass_patches[0]["completion"] == records[0].response


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
