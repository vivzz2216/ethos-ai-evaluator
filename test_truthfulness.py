#!/usr/bin/env python3
"""
Test script for the truthfulness module.
"""
import sys
import os
sys.path.append('backend')

def test_truthfulness_evaluator():
    """Test the TruthfulnessEvaluator class."""
    try:
        from ethos_testing.evaluator import TruthfulnessEvaluator
        print("[OK] TruthfulnessEvaluator imported successfully")

        evaluator = TruthfulnessEvaluator()
        print("[OK] TruthfulnessEvaluator instantiated")

        # Test basic evaluation
        test_prompt = {
            'id': 'TEST-001',
            'category': 'Factual Accuracy',
            'prompt': 'What is 2+2?',
            'expected_label': '4'
        }
        test_response = '2+2 equals 4'

        result = evaluator.evaluate_response(test_prompt, test_response)
        print(f"[OK] Evaluation completed. Score: {result['score']:.2f}")
        print(f"[OK] Truthful: {result['truthful']}")
        print(f"[OK] Explanation: {result['explanation'][:100]}...")

        # Test with deceptive response
        deceptive_response = 'Well, actually 2+2 equals 5, but I\'m not sure...'
        deceptive_result = evaluator.evaluate_response(test_prompt, deceptive_response)
        print(f"[OK] Deceptive response score: {deceptive_result['score']:.2f}")
        print(f"[OK] Deceptive truthful: {deceptive_result['truthful']}")

        return True
    except Exception as e:
        print(f"[ERROR] Error testing TruthfulnessEvaluator: {e}")
        return False

def test_truthfulness_dataset():
    """Test the truthfulness dataset loading."""
    try:
        from ethos_testing.datasets import DatasetLoader
        print("[OK] DatasetLoader imported successfully")

        loader = DatasetLoader("data")
        dataset = loader.load_truthfulness_dataset(num_samples=5)
        print(f"[OK] Loaded {len(dataset)} truthfulness samples")

        # Print first sample
        if dataset:
            sample = dataset[0]
            print(f"[OK] Sample ID: {sample['id']}")
            print(f"[OK] Sample Category: {sample['category']}")
            print(f"[OK] Sample Prompt: {sample['prompt'][:50]}...")

        return True
    except Exception as e:
        print(f"[ERROR] Error testing truthfulness dataset: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing Truthfulness Module")
    print("=" * 40)

    evaluator_ok = test_truthfulness_evaluator()
    print()
    dataset_ok = test_truthfulness_dataset()
    print()

    if evaluator_ok and dataset_ok:
        print("[OK] All tests passed!")
        return 0
    else:
        print("[ERROR] Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
