"""
LoRA Training Client — orchestrates training jobs on RunPod from the local backend.

Handles:
- Uploading patch datasets to RunPod
- Starting/polling LoRA training jobs
- Loading/unloading adapters on the remote model
"""
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
TRAINING_POLL_INTERVAL = 10
TRAINING_TIMEOUT = 1800


class LoRAClient:
    """
    HTTP client for managing LoRA training on a RunPod inference server.

    Usage:
        client = LoRAClient("https://pod-id-8080.proxy.runpod.net")
        client.upload_patch("ethics_patch.jsonl")
        job = client.start_training("Orenguteng/Llama-3-8B-Lexi-Uncensored", round_num=1)
        result = client.poll_training(timeout=1800)
        client.load_adapter("/workspace/adapters/round_1/adapter")
    """

    def __init__(self, endpoint: str, timeout: int = DEFAULT_TIMEOUT):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.endpoint}{path}"

    def health(self) -> Dict[str, Any]:
        """Check server health and loaded model info."""
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self._url("/health"))
            resp.raise_for_status()
            return resp.json()

    def is_healthy(self) -> bool:
        try:
            data = self.health()
            return data.get("status") == "ok"
        except Exception:
            return False

    def upload_patch(self, jsonl_path: str) -> Dict[str, Any]:
        """
        Upload an ethics_patch.jsonl file to the RunPod server.

        Args:
            jsonl_path: Local path to the JSONL file.

        Returns:
            Server response with upload status and entry count.
        """
        if not os.path.exists(jsonl_path):
            raise FileNotFoundError(f"Patch file not found: {jsonl_path}")

        file_size = os.path.getsize(jsonl_path)
        logger.info(f"Uploading patch file: {jsonl_path} ({file_size} bytes)")

        with httpx.Client(timeout=120) as client:
            with open(jsonl_path, "rb") as f:
                resp = client.post(
                    self._url("/upload_patch"),
                    files={"file": ("ethics_patch.jsonl", f, "application/jsonl")},
                )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Patch uploaded: {result.get('entries', 0)} entries")
            return result

    def start_training(
        self,
        base_model: str,
        round_num: int = 1,
        dataset_path: str = "/workspace/ethics_patch.jsonl",
        epochs: int = 3,
        lr: float = 2e-4,
        batch_size: int = 4,
        lora_r: int = 8,
        lora_alpha: int = 32,
    ) -> Dict[str, Any]:
        """
        Start a LoRA training job on RunPod.

        Args:
            base_model: HuggingFace model name.
            round_num: Training round number (for output directory naming).
            dataset_path: Path to dataset on RunPod.
            epochs: Number of training epochs.
            lr: Learning rate.
            batch_size: Per-device batch size.
            lora_r: LoRA rank.
            lora_alpha: LoRA alpha.

        Returns:
            Server response with job_id and config.
        """
        output_dir = f"/workspace/adapters/round_{round_num}"

        logger.info(
            f"Starting training: model={base_model}, round={round_num}, "
            f"epochs={epochs}, lr={lr}"
        )

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                self._url("/train"),
                json={
                    "base_model": base_model,
                    "dataset_path": dataset_path,
                    "output_dir": output_dir,
                    "epochs": epochs,
                    "lr": lr,
                    "batch_size": batch_size,
                    "lora_r": lora_r,
                    "lora_alpha": lora_alpha,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Training job started: {result.get('job_id')}")
            return result

    def get_training_status(self) -> Dict[str, Any]:
        """Get current training job status."""
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self._url("/train_status"))
            resp.raise_for_status()
            return resp.json()

    def poll_training(
        self,
        timeout: int = TRAINING_TIMEOUT,
        poll_interval: int = TRAINING_POLL_INTERVAL,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Poll training status until completion or timeout.

        Args:
            timeout: Max seconds to wait.
            poll_interval: Seconds between polls.
            on_progress: Optional callback(status_dict) called on each poll.

        Returns:
            Final training status dict.

        Raises:
            TimeoutError: If training exceeds timeout.
            RuntimeError: If training fails.
        """
        start = time.time()
        last_epoch = -1

        while time.time() - start < timeout:
            try:
                status = self.get_training_status()
            except Exception as e:
                logger.warning(f"Poll error (retrying): {e}")
                time.sleep(poll_interval)
                continue

            job_status = status.get("status", "idle")
            progress = status.get("progress", {})

            current_epoch = progress.get("epoch", 0)
            if current_epoch != last_epoch:
                loss = progress.get("loss", "?")
                logger.info(f"Training progress: epoch={current_epoch}, loss={loss}")
                last_epoch = current_epoch

            if on_progress:
                on_progress(status)

            if job_status == "completed":
                logger.info("Training completed successfully")
                return status

            if job_status == "failed":
                error = status.get("error", "Unknown error")
                raise RuntimeError(f"Training failed: {error}")

            time.sleep(poll_interval)

        raise TimeoutError(f"Training timed out after {timeout}s")

    def load_adapter(self, adapter_path: str) -> Dict[str, Any]:
        """
        Load a LoRA adapter on the remote server.

        Args:
            adapter_path: Path to adapter on RunPod filesystem.

        Returns:
            Server response with adapter info.
        """
        logger.info(f"Loading adapter: {adapter_path}")
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                self._url("/load_adapter"),
                json={"adapter_path": adapter_path},
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Adapter loaded: {result.get('status')}")
            return result

    def unload_adapter(self) -> Dict[str, Any]:
        """Unload the current adapter, revert to base model."""
        logger.info("Unloading adapter")
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self._url("/unload_adapter"))
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Adapter unloaded: {result.get('status')}")
            return result

    def get_adapter_path(self, round_num: int) -> str:
        """Get the expected adapter path for a given round."""
        return f"/workspace/adapters/round_{round_num}/adapter"

    def full_training_cycle(
        self,
        jsonl_path: str,
        base_model: str,
        round_num: int = 1,
        epochs: int = 3,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Run a complete training cycle: upload → train → poll → load adapter.

        Args:
            jsonl_path: Local path to ethics_patch.jsonl.
            base_model: HuggingFace model name.
            round_num: Training round number.
            epochs: Number of training epochs.
            on_progress: Optional progress callback.

        Returns:
            Dict with training result and adapter path.
        """
        upload_result = self.upload_patch(jsonl_path)
        logger.info(f"Upload: {upload_result.get('entries', 0)} entries")

        train_result = self.start_training(
            base_model=base_model,
            round_num=round_num,
            epochs=epochs,
        )
        job_id = train_result.get("job_id")
        logger.info(f"Training started: job_id={job_id}")

        final_status = self.poll_training(on_progress=on_progress)

        adapter_path = self.get_adapter_path(round_num)
        load_result = self.load_adapter(adapter_path)

        return {
            "job_id": job_id,
            "adapter_path": adapter_path,
            "training_result": final_status.get("result"),
            "adapter_loaded": load_result.get("status") == "adapter_loaded",
        }
