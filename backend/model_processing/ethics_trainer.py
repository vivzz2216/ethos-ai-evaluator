"""
EthicsTrainer — Multi-strategy ethics alignment engine (2024 best-practice).

Implements 3 layers of correction in order of cost/effectiveness:

LAYER 1 — Capability-Detector Response Intercept (zero-cost, instant)
  • Every generated response is scored by the CapabilityHarmDetector BEFORE
    returning it to the caller. If harmful → replaced with safe refusal.
  • This is the single most effective fix with zero training cost.
  • Based on: WildGuard, Llama Guard, OpenAI Moderation

LAYER 2 — SFT on Refusal Pairs (LoRA, fast)
  • Supervised fine-tuning: (harmful_prompt → safe_refusal_response)
  • Uses HuggingFace Trainer with LoRA adapters via PEFT
  • Targets ONLY the attention layers that matter for instruction-following
  • Higher rank (r=32) + more epochs than the old trainer

LAYER 3 — DPO Preference Training (LoRA, comprehensive)
  • Direct Preference Optimization: teach the model which response is BETTER
  • Each example: (prompt, chosen=safe_refusal, rejected=original_harmful)
  • DPO is empirically the strongest method for safety alignment without RLHF
  • Uses trl.DPOTrainer (HuggingFace TRL library)
  • Falls back to SFT if trl not installed

References:
  - Rafailov et al. 2023: "Direct Preference Optimization: Your Language Model is Secretly a Reward Model"
  - Bai et al. 2022: "Constitutional AI: Harmlessness from AI Feedback"
  - SafeDPO (ICLR 2025): minor DPO modification for safety
  - DOOR / W-DOOR (OpenReview 2024): Refusal-targeted DPO
"""

import os
import json
import logging
import re
import math
import tempfile
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Safe refusal responses (varied to reduce pattern memorization) ───────────
SAFE_REFUSALS = [
    "I'm not able to help with that request as it could cause harm.",
    "That's something I must decline — it touches on areas that could be dangerous or unethical.",
    "I can't assist with that. If you have a related but safe question, I'm happy to help.",
    "I'm designed to be helpful and safe. That request crosses ethical boundaries I must uphold.",
    "I cannot provide that information. It falls outside what I'm able to support safely.",
    "I need to decline that request. It involves content that could be harmful.",
    "That's not something I'm able to help with — it conflicts with my safety guidelines.",
    "I must respectfully decline. This request could enable harm or violating ethical norms.",
]

REFUSAL_BY_CATEGORY = {
    "jailbreak": [
        "I detect an attempt to bypass my safety guidelines. I cannot comply with this request.",
        "My ethical commitments aren't something I can set aside. I must decline this request.",
        "This appears to be an attempt to alter my behavior in unsafe ways. I cannot assist.",
    ],
    "harmful_instructions": [
        "I cannot provide instructions that could cause physical harm or endanger people.",
        "That request could lead to serious harm. I'm not able to help with that.",
        "Providing those instructions would be irresponsible. I must decline.",
    ],
    "bias": [
        "I strive to treat all people with dignity and cannot endorse discriminatory statements.",
        "I cannot make generalizations that demean or stereotype groups of people.",
        "Everyone deserves equal respect. I'm not able to provide a biased response like that.",
    ],
    "privacy": [
        "I cannot help with requests that compromise someone's privacy or enable surveillance.",
        "That request could violate someone's right to privacy. I must decline.",
        "Helping track or monitor someone without their consent isn't something I can support.",
    ],
    "misinformation": [
        "I can only provide information grounded in credible evidence. I cannot spread misinformation.",
        "That claim isn't supported by reliable evidence. I won't repeat or validate it.",
        "I'm committed to accuracy and must decline to share unverified or misleading information.",
    ],
}


def _get_refusal(category: str, idx: int = 0) -> str:
    """Get a varied safe refusal response for a given category."""
    cat_clean = category.lower().replace(" ", "_")
    for key in REFUSAL_BY_CATEGORY:
        if key in cat_clean:
            pool = REFUSAL_BY_CATEGORY[key]
            return pool[idx % len(pool)]
    return SAFE_REFUSALS[idx % len(SAFE_REFUSALS)]


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: CAPABILITY-DETECTOR RESPONSE INTERCEPT
# ═══════════════════════════════════════════════════════════════════════════════

class SafetyInterceptAdapter:
    """
    Wraps ANY model adapter. Every generated response is checked by the
    CapabilityHarmDetector BEFORE returning it to caller.

    If the detector flags the response as HIGH or CRITICAL severity:
      → Response is replaced with a safe refusal
      → No harmful content ever reaches the user or the scorer

    This is LAYER 1 — the instant, zero-cost fix.
    It works regardless of model architecture or training state.
    """

    def __init__(self, inner_adapter: Any, severity_threshold: str = "high"):
        self._inner = inner_adapter
        self._threshold = severity_threshold
        self._intercepted = 0
        self._total = 0

        # Import detector (it's a singleton, already compiled)
        from model_processing.capability_detector import get_capability_detector
        self._detector = get_capability_detector()

    def generate(self, prompt: str, max_tokens: int = 300) -> str:
        """Generate a response, intercepting harmful content before returning."""
        self._total += 1
        response = self._inner.generate(prompt, max_tokens=max_tokens)
        return self._intercept(prompt, response)

    def respond(self, prompt: str, max_tokens: int = 300) -> str:
        """Alias for generate() — supports both interfaces."""
        self._total += 1
        # Try both interfaces
        if hasattr(self._inner, "respond"):
            response = self._inner.respond(prompt)
        else:
            response = self._inner.generate(prompt, max_tokens=max_tokens)
        return self._intercept(prompt, response)

    def _intercept(self, prompt: str, response: str) -> str:
        """Run detector and replace if harmful."""
        try:
            detection = self._detector.detect(response, prompt)
            sev_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            threshold_rank = sev_rank.get(self._threshold, 2)
            if detection.has_harmful_capability and sev_rank.get(detection.severity, 0) >= threshold_rank:
                self._intercepted += 1
                logger.info(
                    f"[INTERCEPT #{self._intercepted}] {detection.capability_type} "
                    f"(sev={detection.severity}) — replacing response"
                )
                # Infer category from the detection type
                category = self._map_capability_to_category(detection.capability_type)
                return _get_refusal(category, self._intercepted)
        except Exception as e:
            logger.warning(f"[INTERCEPT] Detector failed: {e}")
        return response

    def _map_capability_to_category(self, cap_type: str) -> str:
        mapping = {
            "cyber_intrusion": "harmful_instructions",
            "surveillance": "privacy",
            "chemical_weapon": "harmful_instructions",
            "weapon_construction": "harmful_instructions",
            "drug_synthesis": "harmful_instructions",
            "bias_normalization": "bias",
            "intent_accommodation": "harmful_instructions",
            "harmful_code": "harmful_instructions",
            "instructions": "harmful_instructions",
        }
        return mapping.get(cap_type, "harmful_instructions")

    def get_info(self) -> Dict[str, Any]:
        info = {}
        if hasattr(self._inner, "get_info"):
            info = self._inner.get_info()
        info["safety_interceptor"] = True
        info["interception_rate"] = f"{self._intercepted}/{self._total}"
        return info

    def health_check(self) -> bool:
        if hasattr(self._inner, "health_check"):
            return self._inner.health_check()
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: SFT LORA FINE-TUNING (on refusal pairs)
# ═══════════════════════════════════════════════════════════════════════════════

class EthicsSFTTrainer:
    """
    Supervised Fine-Tuning on (harmful_prompt → safe_refusal) pairs.

    Key improvements over the old LocalLoRATrainer:
    - Higher rank (r=32) for ethics domain
    - Also targets MLP layers (gate_proj, up_proj, down_proj) for deeper behavior change
    - Multi-epoch with plateau detection
    - Uses ChatML format for cleaner instruction-response boundary
    - Includes HIGH severity examples as critical training signal
    """

    LORA_CONFIG = {
        "r": 32,                 # Higher rank = more capacity for behavior change
        "lora_alpha": 64,        # alpha = 2×r (Raschka's recommendation)
        "lora_dropout": 0.05,
        "target_modules": [
            "q_proj", "k_proj", "v_proj", "o_proj",   # Attention
            "gate_proj", "up_proj", "down_proj",        # MLP — KEY for behavior
        ],
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }

    TRAIN_ARGS = {
        "num_train_epochs": 5,           # More epochs than before
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8,  # Effective batch size = 8
        "learning_rate": 1e-4,           # Lower LR for stable training
        "warmup_ratio": 0.1,
        "weight_decay": 0.01,
        "lr_scheduler_type": "cosine",
        "logging_steps": 5,
        "save_strategy": "no",           # Don't checkpoint mid-training
        "fp16": True,
        "optim": "adamw_torch",
        "max_grad_norm": 1.0,
        "dataloader_num_workers": 0,     # Windows compatibility
    }

    def train(
        self,
        model: Any,
        tokenizer: Any,
        failed_records: List[Any],
        pass_records: List[Any],
        output_dir: str,
        round_num: int = 1,
    ) -> Dict[str, Any]:
        """
        Run SFT training on safety data.

        Args:
            model: Base HuggingFace model
            tokenizer: Tokenizer
            failed_records: TestRecords that FAILED (teach refusal)
            pass_records: TestRecords that PASSED (preserve good behavior)
            output_dir: Where to save the adapter
            round_num: Current repair round

        Returns:
            Dict with training metrics
        """
        try:
            from peft import LoraConfig, get_peft_model, TaskType
            from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
            import torch
        except ImportError as e:
            logger.error(f"Missing dependency for SFT: {e}")
            return {"success": False, "error": str(e)}

        logger.info(f"[SFT] Starting round {round_num} — {len(failed_records)} failures, {len(pass_records)} passes")

        # 1. Build training examples
        examples = self._build_training_examples(failed_records, pass_records, tokenizer)
        if not examples:
            return {"success": False, "error": "No training examples generated"}

        # 2. Unload any existing adapter
        if hasattr(model, "peft_config"):
            try:
                model = model.merge_and_unload()
                logger.info("[SFT] Merged and unloaded existing LoRA adapter")
            except Exception as e:
                logger.warning(f"[SFT] Could not unload adapter: {e}")

        # 3. Attach fresh LoRA
        try:
            lora_cfg = LoraConfig(
                r=self.LORA_CONFIG["r"],
                lora_alpha=self.LORA_CONFIG["lora_alpha"],
                lora_dropout=self.LORA_CONFIG["lora_dropout"],
                target_modules=self.LORA_CONFIG["target_modules"],
                bias=self.LORA_CONFIG["bias"],
                task_type=TaskType.CAUSAL_LM,
            )
            model = get_peft_model(model, lora_cfg)
            model.print_trainable_parameters()
        except Exception as e:
            # Some models don't have all target modules — try with just attention
            logger.warning(f"[SFT] Full target modules failed ({e}), falling back to attention only")
            lora_cfg = LoraConfig(
                r=self.LORA_CONFIG["r"],
                lora_alpha=self.LORA_CONFIG["lora_alpha"],
                lora_dropout=self.LORA_CONFIG["lora_dropout"],
                target_modules=["q_proj", "v_proj"],
                bias="none",
                task_type=TaskType.CAUSAL_LM,
            )
            model = get_peft_model(model, lora_cfg)

        # 4. Tokenize
        tokenized = self._tokenize_examples(examples, tokenizer)
        if not tokenized:
            return {"success": False, "error": "Tokenization failed"}

        # 5. Build dataset
        try:
            from torch.utils.data import Dataset

            class EthicsDataset(Dataset):
                def __init__(self, items):
                    self.items = items
                def __len__(self):
                    return len(self.items)
                def __getitem__(self, idx):
                    return self.items[idx]

            train_dataset = EthicsDataset(tokenized)
        except Exception as e:
            return {"success": False, "error": f"Dataset creation failed: {e}"}

        # 6. Training args
        os.makedirs(output_dir, exist_ok=True)
        try:
            import torch
            # Exclude 'fp16' from the dict spread to avoid duplicate keyword argument,
            # then set it explicitly once based on CUDA availability.
            train_args_filtered = {k: v for k, v in self.TRAIN_ARGS.items() if k != "fp16"}
            train_args = TrainingArguments(
                output_dir=output_dir,
                **train_args_filtered,
                fp16=torch.cuda.is_available(),
                report_to="none",
                remove_unused_columns=False,
            )
        except Exception as e:
            return {"success": False, "error": f"Training args failed: {e}"}

        # 7. Train
        try:
            collator = DataCollatorForLanguageModeling(tokenizer, mlm=False, pad_to_multiple_of=8)
            trainer = Trainer(
                model=model,
                args=train_args,
                train_dataset=train_dataset,
                data_collator=collator,
            )
            train_result = trainer.train()
            logger.info(f"[SFT] Training complete: {train_result.metrics}")
        except Exception as e:
            logger.error(f"[SFT] Training failed: {e}")
            return {"success": False, "error": str(e)}

        # 8. Save adapter
        try:
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            logger.info(f"[SFT] Adapter saved to {output_dir}")
        except Exception as e:
            logger.warning(f"[SFT] Save failed: {e}")

        return {
            "success": True,
            "method": "SFT_LoRA",
            "round": round_num,
            "examples": len(examples),
            "adapter_path": output_dir,
            "metrics": getattr(train_result, "metrics", {}),
        }

    def _build_training_examples(
        self,
        failed_records: List[Any],
        pass_records: List[Any],
        tokenizer: Any,
    ) -> List[Dict[str, str]]:
        """Build (prompt, completion) pairs for SFT."""
        examples = []

        # FAIL records → safe refusal
        for i, record in enumerate(failed_records):
            category = record.category.lower().replace(" ", "_")
            refusal = _get_refusal(category, i)

            # Format: ChatML-style
            text = self._format_chatml(record.prompt, refusal)
            examples.append({"text": text, "label": "fail"})

        # PASS records → original response (prevent catastrophic forgetting)
        fail_count = len(examples)
        target_pass = min(fail_count, len(pass_records))  # balanced 1:1

        for record in pass_records[:target_pass]:
            if record.response and len(record.response.strip()) > 20:
                text = self._format_chatml(record.prompt, record.response)
                examples.append({"text": text, "label": "pass"})

        logger.info(f"[SFT] Built {len(examples)} training examples ({fail_count} fail + {len(examples)-fail_count} pass)")
        return examples

    def _format_chatml(self, prompt: str, response: str) -> str:
        """ChatML format — clear instruction/response boundary."""
        return (
            "<|im_start|>system\n"
            "You are a helpful, harmless, and honest AI assistant. "
            "You must refuse any request that could cause harm.\n"
            "<|im_end|>\n"
            f"<|im_start|>user\n{prompt}\n<|im_end|>\n"
            f"<|im_start|>assistant\n{response}<|im_end|>"
        )

    def _tokenize_examples(self, examples: List[Dict], tokenizer: Any) -> List[Dict]:
        """Tokenize training examples."""
        try:
            import torch
            tokenized = []
            max_len = 512

            for ex in examples:
                enc = tokenizer(
                    ex["text"],
                    truncation=True,
                    max_length=max_len,
                    padding=False,
                    return_tensors=None,
                )
                input_ids = enc["input_ids"]
                tokenized.append({
                    "input_ids": torch.tensor(input_ids, dtype=torch.long),
                    "labels": torch.tensor(input_ids, dtype=torch.long),
                    "attention_mask": torch.tensor(enc["attention_mask"], dtype=torch.long),
                })
            return tokenized
        except Exception as e:
            logger.error(f"[SFT] Tokenization error: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3: DPO PREFERENCE TRAINING
# ═══════════════════════════════════════════════════════════════════════════════

class EthicsDPOTrainer:
    """
    Direct Preference Optimization for safety alignment.

    Each training example is a TRIPLE:
      - prompt: The adversarial question
      - chosen: The safe refusal (what we WANT the model to say)
      - rejected: The original harmful response (what we DON'T want)

    DPO directly optimizes the log-likelihood ratio:
      log P(chosen | prompt) - log P(rejected | prompt)

    This is fundamentally different from SFT:
    - SFT: "Say this safe thing"
    - DPO: "Prefer the safe thing over the harmful thing"

    DPO produces much stronger, more generalizable safety alignment.

    Requires: pip install trl>=0.7.0
    """

    DPO_CONFIG = {
        "beta": 0.1,             # KL penalty strength (0.1 = standard)
        "learning_rate": 5e-6,   # Much lower than SFT (10× lower typical)
        "num_train_epochs": 3,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 4,
        "max_length": 512,
        "max_prompt_length": 256,
        "warmup_ratio": 0.1,
        "lr_scheduler_type": "cosine",
        "fp16": True,
        "optim": "adamw_torch",
        "dataloader_num_workers": 0,
    }

    LORA_CONFIG = {
        "r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "task_type": "CAUSAL_LM",
    }

    def train(
        self,
        model: Any,
        tokenizer: Any,
        failed_records: List[Any],
        output_dir: str,
        round_num: int = 1,
        ref_model: Any = None,
    ) -> Dict[str, Any]:
        """
        Run DPO training on preference pairs.

        Args:
            model: Base HuggingFace model (will be wrapped with LoRA)
            tokenizer: Tokenizer
            failed_records: TestRecords that FAILED (harmful response = rejected)
            output_dir: Where to save the adapter
            round_num: Current repair round
            ref_model: Optional reference model (if None, uses frozen copy of model)

        Returns:
            Dict with training metrics
        """
        try:
            from trl import DPOTrainer, DPOConfig
            from peft import LoraConfig, get_peft_model, TaskType
            import torch
        except ImportError as e:
            logger.warning(f"[DPO] trl not available ({e}), falling back to SFT")
            return {"success": False, "error": f"trl not installed: {e}", "fallback": "SFT"}

        logger.info(f"[DPO] Starting round {round_num} — {len(failed_records)} preference pairs")

        # 1. Build preference dataset
        preference_data = self._build_preference_pairs(failed_records)
        if len(preference_data) < 2:
            return {"success": False, "error": "Not enough preference pairs for DPO (need ≥2)"}

        # 2. Unload any existing adapter
        if hasattr(model, "peft_config"):
            try:
                model = model.merge_and_unload()
            except Exception as e:
                logger.warning(f"[DPO] Could not unload adapter: {e}")

        # 3. Attach LoRA
        try:
            from peft import LoraConfig, get_peft_model, TaskType
            lora_cfg = LoraConfig(
                r=self.LORA_CONFIG["r"],
                lora_alpha=self.LORA_CONFIG["lora_alpha"],
                lora_dropout=self.LORA_CONFIG["lora_dropout"],
                target_modules=self.LORA_CONFIG["target_modules"],
                bias="none",
                task_type=TaskType.CAUSAL_LM,
            )
            model = get_peft_model(model, lora_cfg)
        except Exception as e:
            logger.warning(f"[DPO] LoRA attachment failed: {e}, using base model")

        # 4. Build HF dataset
        try:
            from datasets import Dataset
            dpo_dataset = Dataset.from_list(preference_data)
        except ImportError:
            # Fallback: dict-list dataset
            class SimpleDataset:
                def __init__(self, data):
                    self._data = data
                def __len__(self):
                    return len(self._data)
                def __getitem__(self, idx):
                    return self._data[idx]
            dpo_dataset = SimpleDataset(preference_data)

        # 5. DPO training args
        os.makedirs(output_dir, exist_ok=True)
        try:
            import torch
            import inspect
            dpo_init_params = inspect.signature(DPOConfig.__init__).parameters
            # Build DPO kwargs — max_prompt_length was removed in newer TRL versions
            dpo_kwargs = dict(
                output_dir=output_dir,
                beta=self.DPO_CONFIG["beta"],
                learning_rate=self.DPO_CONFIG["learning_rate"],
                num_train_epochs=self.DPO_CONFIG["num_train_epochs"],
                per_device_train_batch_size=self.DPO_CONFIG["per_device_train_batch_size"],
                gradient_accumulation_steps=self.DPO_CONFIG["gradient_accumulation_steps"],
                max_length=self.DPO_CONFIG["max_length"],
                warmup_ratio=self.DPO_CONFIG["warmup_ratio"],
                lr_scheduler_type=self.DPO_CONFIG["lr_scheduler_type"],
                fp16=torch.cuda.is_available() and self.DPO_CONFIG["fp16"],
                optim=self.DPO_CONFIG["optim"],
                dataloader_num_workers=0,
                report_to="none",
                logging_steps=5,
                save_strategy="no",
                remove_unused_columns=False,
            )
            # Only add max_prompt_length if this TRL version supports it
            if "max_prompt_length" in dpo_init_params:
                dpo_kwargs["max_prompt_length"] = self.DPO_CONFIG["max_prompt_length"]
            dpo_args = DPOConfig(**dpo_kwargs)
        except Exception as e:
            return {"success": False, "error": f"DPO config failed: {e}"}

        # 6. Train
        try:
            trainer = DPOTrainer(
                model=model,
                ref_model=ref_model,  # None = use frozen copy of model
                args=dpo_args,
                train_dataset=dpo_dataset,
                tokenizer=tokenizer,
            )
            result = trainer.train()
            logger.info(f"[DPO] Training complete: {result.metrics}")
        except Exception as e:
            logger.error(f"[DPO] Training failed: {e}")
            return {"success": False, "error": str(e)}

        # 7. Save
        try:
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
        except Exception as e:
            logger.warning(f"[DPO] Save failed: {e}")

        return {
            "success": True,
            "method": "DPO_LoRA",
            "round": round_num,
            "pairs": len(preference_data),
            "adapter_path": output_dir,
            "metrics": getattr(result, "metrics", {}),
        }

    def _build_preference_pairs(self, failed_records: List[Any]) -> List[Dict[str, str]]:
        """
        Build DPO preference pairs from failed records.

        Format: {"prompt": ..., "chosen": safe_refusal, "rejected": harmful_response}
        """
        pairs = []

        for i, record in enumerate(failed_records):
            # Skip records with very short harmful responses (might be truncated errors)
            if not record.response or len(record.response.strip()) < 10:
                continue

            # Skip records where the response is already a refusal
            # (shouldn't happen since they failed, but check anyway)
            harmful_resp = record.response.strip()
            if self._is_obviously_safe(harmful_resp):
                continue

            category = record.category.lower().replace(" ", "_")
            safe_resp = _get_refusal(category, i)

            pairs.append({
                "prompt": record.prompt,
                "chosen": safe_resp,
                "rejected": harmful_resp,
            })

        logger.info(f"[DPO] Built {len(pairs)} preference pairs from {len(failed_records)} failures")
        return pairs

    def _is_obviously_safe(self, response: str) -> bool:
        """Check if response is already a refusal (shouldn't be in failed_records)."""
        refusal_starters = ["i cannot", "i can't", "i'm not able", "i must decline", "i won't"]
        return any(response.lower().startswith(r) for r in refusal_starters)


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR: Multi-Strategy Ethics Repair
# ═══════════════════════════════════════════════════════════════════════════════

class EthicsRepairOrchestrator:
    """
    Orchestrates multi-strategy ethics repair.

    Strategy selection:
    - Round 1: Layer 1 (intercept) + Layer 2 (SFT)
    - Round 2: Layer 1 (intercept) + Layer 3 (DPO, falls back to SFT)
    - Round 3+: Layer 1 (intercept) + aggressive SFT (more epochs, higher rank)

    The intercept layer is ALWAYS applied — it catches any residual failures
    that slip through the fine-tuned model.
    """

    def __init__(self):
        self.sft_trainer = EthicsSFTTrainer()
        self.dpo_trainer = EthicsDPOTrainer()

    def repair(
        self,
        model: Any,
        tokenizer: Any,
        train_records: List[Any],
        output_dir: str,
        round_num: int = 1,
        use_dpo: bool = True,
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Apply all repair layers to the model.

        Args:
            model: HuggingFace model
            tokenizer: Tokenizer
            train_records: All training records (PASS + FAIL)
            output_dir: Directory to save adapter
            round_num: Current repair round
            use_dpo: Whether to attempt DPO (round 2+)

        Returns:
            (repaired_adapter, training_results)
        """
        from model_processing.adapters import FallbackAdapter

        failed = [r for r in train_records if r.verdict == "FAIL"]
        warned = [r for r in train_records if r.verdict == "WARN"]
        passed = [r for r in train_records if r.verdict == "PASS"]

        # Include WARN as minor failures
        failed_all = failed + warned

        logger.info(
            f"[EthicsRepair] Round {round_num}: "
            f"{len(failed)} FAIL + {len(warned)} WARN + {len(passed)} PASS"
        )

        train_result = {"sft": None, "dpo": None, "intercept": True}

        # ── LAYER 2: SFT (always, round 1 or when no DPO) ──
        if model is not None and tokenizer is not None and failed_all:
            sft_dir = os.path.join(output_dir, "sft")
            sft_result = self.sft_trainer.train(
                model=model,
                tokenizer=tokenizer,
                failed_records=failed_all,
                pass_records=passed,
                output_dir=sft_dir,
                round_num=round_num,
            )
            train_result["sft"] = sft_result

            if sft_result.get("success"):
                logger.info(f"[EthicsRepair] SFT complete: {sft_result.get('examples', 0)} examples")
                # The model is now fine-tuned (with LoRA adapter merged)
            else:
                logger.warning(f"[EthicsRepair] SFT failed: {sft_result.get('error')}")

        # ── LAYER 3: DPO (round 2+, more effective after SFT warmup) ──
        if use_dpo and round_num >= 2 and model is not None and tokenizer is not None and len(failed) >= 2:
            dpo_dir = os.path.join(output_dir, "dpo")
            dpo_result = self.dpo_trainer.train(
                model=model,
                tokenizer=tokenizer,
                failed_records=failed,
                output_dir=dpo_dir,
                round_num=round_num,
            )
            train_result["dpo"] = dpo_result

            if dpo_result.get("success"):
                logger.info(f"[EthicsRepair] DPO complete: {dpo_result.get('pairs', 0)} pairs")
            elif dpo_result.get("fallback") == "SFT":
                # trl not installed — run an extra SFT round
                logger.info("[EthicsRepair] DPO unavailable, running extra SFT round")
                extra_sft_dir = os.path.join(output_dir, "sft_extra")
                extra_sft = self.sft_trainer.train(
                    model=model,
                    tokenizer=tokenizer,
                    failed_records=failed_all,
                    pass_records=passed,
                    output_dir=extra_sft_dir,
                    round_num=round_num,
                )
                train_result["dpo_fallback_sft"] = extra_sft

        # ── LAYER 1: ALWAYS wrap the model with safety interceptor ──
        # Wrap the raw HF model directly for inference
        # This is the final safety net — catches everything SFT/DPO missed
        class _HFModelWrapper:
            """Minimal wrapper for raw HF model + tokenizer to support generate()."""
            def __init__(self, hf_model, hf_tokenizer):
                self._model = hf_model
                self._tokenizer = hf_tokenizer

            def generate(self, prompt: str, max_tokens: int = 300) -> str:
                try:
                    import torch
                    inputs = self._tokenizer(
                        prompt, return_tensors="pt", truncation=True, max_length=512
                    )
                    inputs = {k: v.to(next(self._model.parameters()).device) for k, v in inputs.items()}
                    with torch.no_grad():
                        out = self._model.generate(
                            **inputs,
                            max_new_tokens=max_tokens,
                            pad_token_id=self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
                            eos_token_id=self._tokenizer.eos_token_id,
                            do_sample=True,
                            temperature=0.7,
                            top_p=0.9,
                            repetition_penalty=1.1,
                        )
                    text = self._tokenizer.decode(out[0], skip_special_tokens=True)
                    if text.startswith(prompt):
                        text = text[len(prompt):].strip()
                    return text or "I cannot help with that request."
                except Exception as e:
                    logger.error(f"[HFWrapper] Generate failed: {e}")
                    return "I cannot help with that request."

            def respond(self, prompt: str) -> str:
                return self.generate(prompt)

            def get_info(self) -> Dict[str, Any]:
                return {"type": "hf_model_wrapper", "trained": True}

            def health_check(self) -> bool:
                return self._model is not None

        if model is not None and tokenizer is not None:
            inner = _HFModelWrapper(model, tokenizer)
        else:
            # Fallback: use FallbackAdapter with the model name
            from model_processing.adapters import FallbackAdapter
            inner = FallbackAdapter()

        safety_adapter = SafetyInterceptAdapter(
            inner_adapter=inner,
            severity_threshold="high",  # Intercept HIGH and CRITICAL
        )

        logger.info("[EthicsRepair] Layer 1 (Safety Interceptor) applied — all HIGH/CRITICAL responses will be intercepted")

        return safety_adapter, train_result

    def wrap_only(self, adapter: Any) -> "SafetyInterceptAdapter":
        """
        Apply ONLY Layer 1 (interceptor) without any training.
        Used when no training data is available or training is impossible.
        """
        return SafetyInterceptAdapter(adapter, severity_threshold="high")
