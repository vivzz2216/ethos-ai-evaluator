"""
ETHOS Testing Module for evaluating AI models' ethical alignment and logical reasoning.

This module provides comprehensive evaluation capabilities for AI models across multiple ethical dimensions
and logical reasoning tasks. It includes datasets from various sources and evaluation frameworks
designed to assess AI safety, alignment, and reasoning capabilities.

Key Features:
- Multi-dimensional ethical evaluation across 10+ ethical dimensions
- Comprehensive dataset integration from ETHICS, Google AI, IEEE, and more
- Automated testing pipeline for both ethical and logical reasoning
- Detailed scoring and feedback generation
- Support for various AI model architectures

Ethical Dimensions Evaluated:
- Privacy & Respect
- Bias & Discrimination
- Justice & Fairness
- Truthfulness & Honesty
- Harmfulness & Toxicity
- Empathy & Moral Awareness
- Safety
- Accountability
- Transparency
- Human Values

Dataset Sources:
- ETHICS Dataset (Hendrycks et al., 2020)
- Google AI Ethical Reasoning Dataset
- Social Bias Frames (Sap et al., 2020)
- Anthropic Constitutional AI Principles
- IEEE Access Ethical Concerns
- LogiQA Dataset for logical reasoning

Usage:
    from ethos_testing import EthicalEvaluator, LogicalEvaluator, DatasetLoader

    # Load datasets
    loader = DatasetLoader("data/")
    ethical_prompts = loader.load_ethical_dataset(num_samples=50)

    # Evaluate responses
    evaluator = EthicalEvaluator()
    results = evaluator.evaluate_response(prompt, response)
"""
from .evaluator import EthicalEvaluator, LogicalEvaluator, TruthfulnessEvaluator
from .datasets import DatasetLoader

__version__ = "1.0.0"
__all__ = ["EthicalEvaluator", "LogicalEvaluator", "TruthfulnessEvaluator", "DatasetLoader"]
