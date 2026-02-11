"""
LoRA Training Script for RunPod GPU

Runs on the RunPod pod to fine-tune a model using PEFT LoRA on ethics patches.
Called by inference_server.py's /train endpoint.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any

import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    TrainerCallback,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_lora")


def _infer_lora_target_modules(model: torch.nn.Module) -> list[str]:
    """Infer LoRA target module names from model architecture."""
    preferred_names = {
        "q_proj", "k_proj", "v_proj", "o_proj",  # LLaMA/Mistral-style
        "query_key_value",  # Falcon/BLOOM variants
        "c_attn", "c_proj",  # GPT-2 style
        "Wqkv",  # Some MPT variants
    }

    discovered = []
    for module_name, module in model.named_modules():
        if not isinstance(module, torch.nn.Linear):
            continue
        leaf_name = module_name.split(".")[-1]
        if leaf_name in preferred_names:
            discovered.append(leaf_name)

    unique = sorted(set(discovered))
    if unique:
        return unique

    # Conservative fallback for attention-heavy architectures.
    return ["q_proj", "k_proj", "v_proj", "o_proj"]


def train(
    base_model: str,
    dataset_path: str = "/workspace/ethics_patch.jsonl",
    output_dir: str = "/workspace/adapters/round_1",
    epochs: int = 3,
    lr: float = 2e-4,
    batch_size: int = 4,
    lora_r: int = 8,
    lora_alpha: int = 32,
) -> Dict[str, Any]:
    """
    Train a LoRA adapter on ethics patch dataset.

    Args:
        base_model: HuggingFace model name
        dataset_path: Path to JSONL file with prompt/completion pairs
        output_dir: Where to save the adapter
        epochs: Number of training epochs
        lr: Learning rate
        batch_size: Per-device batch size
        lora_r: LoRA rank
        lora_alpha: LoRA alpha parameter

    Returns:
        Dict with training metrics
    """
    start_time = time.time()
    logger.info(f"Starting LoRA training: {base_model}")
    logger.info(f"Dataset: {dataset_path}")
    logger.info(f"Output: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    try:
        from peft import LoraConfig, get_peft_model
    except Exception as e:
        raise RuntimeError(
            "peft is required for LoRA training. Install with: pip install peft"
        ) from e

    # Update status file
    _update_status({"status": "loading_model", "epoch": 0, "loss": None})

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load base model in 8-bit (saves VRAM)
    logger.info("Loading base model in 8-bit...")
    has_cuda = torch.cuda.is_available()
    try:
        from transformers import BitsAndBytesConfig

        bnb_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
        )

        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=bnb_config,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        logger.info("Model loaded in 8-bit")
    except Exception as e:
        if has_cuda:
            logger.warning(f"8-bit load unavailable ({e}), loading in float16")
            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype=torch.float16,
                device_map="auto",
                low_cpu_mem_usage=True,
            )
        else:
            logger.warning(f"8-bit load unavailable ({e}), loading in float32 on CPU")
            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            )

    # Configure LoRA (PEFT 0.18+ handles quantized models automatically)
    logger.info(f"Applying LoRA config: r={lora_r}, alpha={lora_alpha}")
    target_modules = _infer_lora_target_modules(model)
    logger.info(f"LoRA target modules: {target_modules}")
    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load dataset
    logger.info(f"Loading dataset from {dataset_path}")
    _update_status({"status": "loading_dataset", "epoch": 0, "loss": None})

    dataset = load_dataset("json", data_files=dataset_path, split="train")
    logger.info(f"Dataset size: {len(dataset)} examples")
    required_columns = {"prompt", "completion"}
    missing_columns = required_columns.difference(dataset.column_names)
    if missing_columns:
        raise ValueError(
            f"Dataset must contain columns {sorted(required_columns)}. Missing: {sorted(missing_columns)}"
        )

    # Tokenize dataset
    def tokenize_function(examples):
        # Combine prompt and completion
        texts = [
            f"{p}\n{c}" for p, c in zip(examples["prompt"], examples["completion"])
        ]
        tokenized = tokenizer(
            texts,
            truncation=True,
            max_length=512,
            padding="max_length",
        )
        labels = []
        for ids, mask in zip(tokenized["input_ids"], tokenized["attention_mask"]):
            labels.append([tok if m == 1 else -100 for tok, m in zip(ids, mask)])
        tokenized["labels"] = labels
        return tokenized

    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
    )

    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        learning_rate=lr,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=1,
        fp16=has_cuda,
        report_to="none",
    )

    # Custom callback to update status
    class StatusCallback(TrainerCallback):
        def __init__(self):
            self.current_epoch = 0

        def on_epoch_begin(self, args, state, control, **kwargs):
            self.current_epoch = state.epoch
            epoch = int(self.current_epoch or 0)
            _update_status(
                {
                    "status": "training",
                    "epoch": epoch,
                    "loss": None,
                }
            )

        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and "loss" in logs:
                epoch = int(state.epoch or 0)
                _update_status(
                    {
                        "status": "training",
                        "epoch": epoch,
                        "loss": round(logs["loss"], 4),
                    }
                )

    # Trainer
    logger.info("Starting training...")
    _update_status({"status": "training", "epoch": 0, "loss": None})

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        callbacks=[StatusCallback()],
    )

    # Train
    train_result = trainer.train()

    # Save adapter
    logger.info(f"Saving adapter to {output_dir}/adapter")
    adapter_path = os.path.join(output_dir, "adapter")
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)

    # Training metrics
    duration = time.time() - start_time
    metrics = {
        "train_loss": round(train_result.training_loss, 4),
        "epochs": epochs,
        "dataset_size": len(dataset),
        "duration_seconds": round(duration, 1),
        "adapter_path": adapter_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Save training log
    log_path = os.path.join(output_dir, "train_log.json")
    with open(log_path, "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"Training complete: loss={metrics['train_loss']}, duration={duration:.1f}s")
    _update_status({"status": "completed", "epoch": epochs, "loss": metrics["train_loss"]})

    return metrics


def _update_status(status: Dict[str, Any]):
    """Write training status to disk for polling."""
    status_file = "/workspace/train_status.json"
    try:
        with open(status_file, "w") as f:
            json.dump(status, f)
    except Exception as e:
        logger.warning(f"Failed to update status file: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Base model name")
    parser.add_argument("--dataset", default="/workspace/ethics_patch.jsonl")
    parser.add_argument("--output", default="/workspace/adapters/round_1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=32)

    args = parser.parse_args()

    result = train(
        base_model=args.model,
        dataset_path=args.dataset,
        output_dir=args.output,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
    )

    print(json.dumps(result, indent=2))
