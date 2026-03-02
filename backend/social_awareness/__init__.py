"""
Social Awareness / Communication Style Module for ETHOS AI Evaluator.

Provides:
  StyleDetector            — rule-based + ML formality scoring
  ToneClassifier           — style label + policy compliance
  HumanInteractionScorer   — weighted empathy/clarity/engagement scoring
  StyleTransformer         — batch style rewrite with meaning guard
  SocialPolicyEngine       — full evaluation pipeline, drift & consistency
"""

# All heavy imports are deferred to avoid slow startup.
# Use the individual submodules or the api router directly.
