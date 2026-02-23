"""
Unified Model Adapter System — Local GPU Only.
Provides a single interface for all model types so the ethics agent
never talks directly to models — only through adapters.
All inference runs locally on the NVIDIA RTX GPU.
"""
import os
import subprocess
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ModelAdapter(ABC):
    """
    Universal interface for all model types.
    Ethics testing code only interacts with this API.
    """

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Generate text from a prompt."""
        ...

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verify model is operational."""
        ...


# ── Concrete Adapters ─────────────────────────────────────────────────


class TransformersAdapter(ModelAdapter):
    """Adapter for HuggingFace Transformers models."""

    def __init__(self, model_path: str):
        self.model_path = self._resolve_model_dir(model_path)
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._device = None

    @staticmethod
    def _resolve_model_dir(path: str) -> str:
        """
        Find the actual model directory containing config.json.
        When linked via link-local, model files live in a subdirectory
        (e.g., project_dir/Llama-3-8B/config.json), not at project root.
        """
        if os.path.isfile(os.path.join(path, "config.json")):
            return path
        # Search one level of subdirectories
        for entry in os.listdir(path):
            subdir = os.path.join(path, entry)
            if os.path.isdir(subdir) and os.path.isfile(os.path.join(subdir, "config.json")):
                logger.info(f"Found model config in subdirectory: {entry}")
                return subdir
        # Fallback to original path
        return path

    def _load(self):
        if self._loaded:
            return
        from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
        import torch

        logger.info(f"Loading HuggingFace model from {self.model_path}...")

        # ── Load tokenizer & config (always works) ────────────────────
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        config = AutoConfig.from_pretrained(self.model_path)

        if self._tokenizer.pad_token is None and self._tokenizer.eos_token:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        is_seq2seq = getattr(config, "model_type", "") == "t5" or "t5" in self.model_path.lower()
        if is_seq2seq:
            from transformers import AutoModelForSeq2SeqLM
            auto_cls = AutoModelForSeq2SeqLM
            self._model_class = "seq2seq"
        else:
            auto_cls = AutoModelForCausalLM
            self._model_class = "causal"

        # ── Detect hardware capabilities ──────────────────────────────
        has_cuda = torch.cuda.is_available()
        has_accelerate = False
        has_bnb = False
        try:
            import accelerate  # noqa: F401
            has_accelerate = True
        except ImportError:
            pass
        try:
            import bitsandbytes  # noqa: F401
            has_bnb = True
        except ImportError:
            pass

        gpu_mem_gb = 0.0
        if has_cuda:
            gpu_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9

        import psutil
        free_ram_gb = psutil.virtual_memory().available / 1e9

        # Estimate model size from actual weight files on disk (most accurate)
        weight_exts = {".safetensors", ".bin", ".pt", ".h5"}
        total_weight_bytes = 0
        for root, _, files in os.walk(self.model_path):
            for f in files:
                if any(f.endswith(ext) for ext in weight_exts):
                    total_weight_bytes += os.path.getsize(os.path.join(root, f))
        if total_weight_bytes > 0:
            model_size_gb = total_weight_bytes / 1e9
        else:
            # Fallback: estimate from config (include FFN + vocab)
            h = getattr(config, "hidden_size", 4096)
            n = getattr(config, "num_hidden_layers", 32)
            inter = getattr(config, "intermediate_size", h * 4)
            vocab = getattr(config, "vocab_size", 32000)
            num_params = n * (4 * h * h + 3 * h * inter) + vocab * h
            model_size_gb = (num_params * 2) / 1e9  # float16

        logger.info(
            f"Hardware: CUDA={has_cuda}, GPU={gpu_mem_gb:.1f}GB, "
            f"freeRAM={free_ram_gb:.1f}GB, accelerate={has_accelerate}, "
            f"bnb={has_bnb}, est_model={model_size_gb:.1f}GB"
        )

        # Free memory before loading
        import gc
        gc.collect()
        if has_cuda:
            torch.cuda.empty_cache()

        # Offload folder for disk-based weight overflow
        offload_dir = os.path.join(os.path.dirname(self.model_path), "_offload")
        os.makedirs(offload_dir, exist_ok=True)

        # ── Strategy 1: 4-bit quantization (fits big models in small VRAM) ──
        if has_cuda and has_bnb and has_accelerate and model_size_gb > gpu_mem_gb * 0.8:
            try:
                from transformers import BitsAndBytesConfig
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                # Constrain memory: GPU gets most, CPU gets minimal, rest on disk
                gpu_alloc = f"{int(gpu_mem_gb * 0.85)}GiB"
                cpu_alloc = f"{max(int(free_ram_gb * 0.5), 2)}GiB"
                logger.info(
                    f"Strategy 1: 4-bit NF4, GPU={gpu_alloc}, CPU={cpu_alloc}, "
                    f"offload_folder={offload_dir}"
                )
                self._model = auto_cls.from_pretrained(
                    self.model_path,
                    quantization_config=quant_config,
                    device_map="auto",
                    max_memory={0: gpu_alloc, "cpu": cpu_alloc},
                    offload_folder=offload_dir,
                    offload_state_dict=True,
                    low_cpu_mem_usage=True,
                )
                self._device = next(self._model.parameters()).device
                self._model.eval()
                self._loaded = True
                logger.info(f"4-bit quantized model loaded on {self._device}")
                return
            except Exception as e:
                logger.warning(f"4-bit quantization failed: {e}, trying next strategy...")
                gc.collect()
                if has_cuda:
                    torch.cuda.empty_cache()

        # ── Strategy 2: float16 + device_map="auto" ──────────────────
        if has_cuda and has_accelerate:
            try:
                gpu_alloc = f"{int(gpu_mem_gb * 0.85)}GiB"
                cpu_alloc = f"{max(int(free_ram_gb * 0.5), 2)}GiB"
                logger.info(f"Strategy 2: float16, GPU={gpu_alloc}, CPU={cpu_alloc}")
                self._model = auto_cls.from_pretrained(
                    self.model_path,
                    torch_dtype=torch.float16,
                    device_map="auto",
                    max_memory={0: gpu_alloc, "cpu": cpu_alloc},
                    offload_folder=offload_dir,
                    offload_state_dict=True,
                    low_cpu_mem_usage=True,
                )
                self._device = next(self._model.parameters()).device
                self._model.eval()
                self._loaded = True
                logger.info("float16 model loaded with device_map='auto'")
                return
            except Exception as e:
                logger.warning(f"float16 device_map loading failed: {e}, trying next strategy...")
                gc.collect()
                if has_cuda:
                    torch.cuda.empty_cache()

        # ── Strategy 3: float16 on single GPU (small models) ─────────
        if has_cuda and model_size_gb < gpu_mem_gb * 0.9:
            try:
                logger.info("Strategy 3: Loading float16 on single GPU...")
                self._model = auto_cls.from_pretrained(
                    self.model_path,
                    torch_dtype=torch.float16,
                    low_cpu_mem_usage=True,
                ).to("cuda")
                self._device = torch.device("cuda")
                self._model.eval()
                self._loaded = True
                logger.info("float16 model loaded on single GPU")
                return
            except Exception as e:
                logger.warning(f"Single GPU loading failed: {e}, trying CPU...")
                gc.collect()
                if has_cuda:
                    torch.cuda.empty_cache()

        # ── Strategy 4: CPU float32 (slowest, needs lots of RAM) ─────
        if free_ram_gb > model_size_gb * 1.3:
            try:
                logger.info("Strategy 4: Loading float32 on CPU (slow)...")
                self._model = auto_cls.from_pretrained(
                    self.model_path,
                    torch_dtype=torch.float32,
                    low_cpu_mem_usage=True,
                )
                self._device = torch.device("cpu")
                self._model.eval()
                self._loaded = True
                logger.info("float32 model loaded on CPU")
                return
            except Exception as e:
                logger.warning(f"CPU float32 loading failed: {e}")

        # ── All strategies failed ─────────────────────────────────────
        raise RuntimeError(
            f"Cannot load model: GPU has {gpu_mem_gb:.1f}GB VRAM, "
            f"free RAM is {free_ram_gb:.1f}GB, model needs ~{model_size_gb:.1f}GB. "
            f"Install bitsandbytes for 4-bit quantization, or free up memory."
        )

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        self._load()
        try:
            import torch

            inputs = self._tokenizer(
                prompt, return_tensors="pt", truncation=True, max_length=512
            )
            # Move inputs to the same device as the model
            if self._device:
                inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    pad_token_id=self._tokenizer.pad_token_id,
                    do_sample=True,
                    temperature=0.7,
                    top_k=50,
                    top_p=0.9,
                    repetition_penalty=1.2,
                )

            text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Strip the prompt from the output
            if text.startswith(prompt):
                text = text[len(prompt):].strip()
            return text or "I understand the question but need more context."
        except Exception as e:
            logger.error(f"TransformersAdapter.generate error: {e}")
            return f"Error generating response: {e}"

    def get_info(self) -> Dict[str, Any]:
        return {
            "type": "huggingface",
            "model_path": self.model_path,
            "loaded": self._loaded,
            "model_class": getattr(self, "_model_class", "unknown"),
        }

    def health_check(self) -> bool:
        try:
            self._load()
            return self._loaded
        except Exception:
            return False


class GGUFAdapter(ModelAdapter):
    """Adapter for GGUF/GGML models via llama-cpp-python."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        try:
            from llama_cpp import Llama
            logger.info(f"Loading GGUF model from {self.model_path}...")
            self._model = Llama(model_path=self.model_path, n_ctx=2048, verbose=False)
            logger.info("GGUF model loaded")
        except Exception as e:
            logger.error(f"Failed to load GGUF model: {e}")
            raise

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        self._load()
        try:
            output = self._model.create_completion(
                prompt, max_tokens=max_tokens, stop=["\n\n"]
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"GGUFAdapter.generate error: {e}")
            return f"Error generating response: {e}"

    def get_info(self) -> Dict[str, Any]:
        return {
            "type": "gguf",
            "model_path": self.model_path,
            "loaded": self._model is not None,
        }

    def health_check(self) -> bool:
        try:
            self._load()
            return self._model is not None
        except Exception:
            return False


class PythonScriptAdapter(ModelAdapter):
    """Adapter for custom Python inference scripts."""

    def __init__(self, script_path: str, python_exe: str = "python", cwd: Optional[str] = None):
        self.script_path = script_path
        self.python_exe = python_exe
        self.cwd = cwd or os.path.dirname(script_path)

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            result = subprocess.run(
                [self.python_exe, self.script_path],
                input=prompt.encode("utf-8"),
                capture_output=True,
                timeout=60,
                cwd=self.cwd,
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8", errors="replace").strip()
            else:
                err = result.stderr.decode("utf-8", errors="replace")[:300]
                logger.warning(f"Script returned non-zero: {err}")
                return f"Script error: {err}"
        except subprocess.TimeoutExpired:
            return "Error: inference script timed out (60s limit)"
        except Exception as e:
            logger.error(f"PythonScriptAdapter.generate error: {e}")
            return f"Error: {e}"

    def get_info(self) -> Dict[str, Any]:
        return {
            "type": "python_custom",
            "script_path": self.script_path,
            "python_exe": self.python_exe,
        }

    def health_check(self) -> bool:
        return os.path.isfile(self.script_path)


class DockerAdapter(ModelAdapter):
    """Adapter for Docker-containerized models."""

    def __init__(self, container_id: str):
        self.container_id = container_id

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            safe_prompt = prompt.replace("'", "'\\''")
            result = subprocess.run(
                ["docker", "exec", self.container_id, "python", "-c",
                 f"import sys; sys.stdin = __import__('io').StringIO('{safe_prompt}'); exec(open('/app/inference.py').read())"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"Docker exec error: {result.stderr[:300]}"
        except subprocess.TimeoutExpired:
            return "Error: Docker container timed out (120s limit)"
        except Exception as e:
            return f"Error: {e}"

    def get_info(self) -> Dict[str, Any]:
        return {"type": "docker", "container_id": self.container_id}

    def health_check(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", self.container_id],
                capture_output=True, text=True, timeout=10,
            )
            return "true" in result.stdout.lower()
        except Exception:
            return False


class APIAdapter(ModelAdapter):
    """Adapter for external API-wrapped models."""

    def __init__(self, endpoint: str, api_key: Optional[str] = None, headers: Optional[Dict] = None):
        self.endpoint = endpoint
        self.api_key = api_key
        self.headers = headers or {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            import httpx
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    self.endpoint,
                    json={"prompt": prompt, "max_tokens": max_tokens},
                    headers=self.headers,
                )
                resp.raise_for_status()
                data = resp.json()
                # Try common response formats
                return (
                    data.get("text")
                    or data.get("response")
                    or data.get("choices", [{}])[0].get("text", "")
                    or str(data)
                )
        except Exception as e:
            logger.error(f"APIAdapter.generate error: {e}")
            return f"API error: {e}"

    def get_info(self) -> Dict[str, Any]:
        return {"type": "api_wrapper", "endpoint": self.endpoint}

    def health_check(self) -> bool:
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                resp = client.get(self.endpoint.rsplit("/", 1)[0] + "/health")
                return resp.status_code < 500
        except Exception:
            return False




class FallbackAdapter(ModelAdapter):
    """
    Fallback adapter that uses the existing LocalHuggingFaceModel.
    Used when no model files are uploaded but a HF model name is provided.
    """

    def __init__(self, model_name: str = "sshleifer/tiny-gpt2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from ethos_testing.local_model import get_model
        self._model = get_model(self.model_name)

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        self._load()
        return self._model.respond(prompt, max_new_tokens=max_tokens, temperature=0.7)

    def get_info(self) -> Dict[str, Any]:
        return {"type": "fallback_hf", "model_name": self.model_name}

    def health_check(self) -> bool:
        try:
            self._load()
            return self._model.is_loaded()
        except Exception:
            return False


# ── Factory ───────────────────────────────────────────────────────────


def create_adapter(
    model_type: str,
    project_dir: str,
    python_exe: str = "python",
    container_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    entrypoint: Optional[str] = None,
    model_name: Optional[str] = None,
) -> ModelAdapter:
    """
    Factory function to create the appropriate adapter.

    Args:
        model_type: One of huggingface, gguf, python_custom, docker, api_wrapper.
        project_dir: Path to the uploaded model directory.
        python_exe: Path to the venv python executable.
        container_id: Docker container ID (for docker type).
        endpoint: API endpoint URL (for api_wrapper type).
        api_key: API key (for api_wrapper type).
        entrypoint: Script entrypoint (for python_custom type).
        model_name: HuggingFace model name (for fallback).

    Returns:
        A ModelAdapter instance.
    """
    # All inference is local — no remote/cloud endpoints
    if model_type == "huggingface":
        return TransformersAdapter(project_dir)

    elif model_type == "gguf":
        # Find the first .gguf file
        for f in os.listdir(project_dir):
            if f.endswith(".gguf") or f.endswith(".ggml"):
                return GGUFAdapter(os.path.join(project_dir, f))
        raise FileNotFoundError("No GGUF/GGML file found in project directory")

    elif model_type == "python_custom":
        script = entrypoint or "inference.py"
        script_path = os.path.join(project_dir, script)
        return PythonScriptAdapter(script_path, python_exe=python_exe, cwd=project_dir)

    elif model_type == "docker":
        if not container_id:
            raise ValueError("container_id required for docker adapter")
        return DockerAdapter(container_id)

    elif model_type == "api_wrapper":
        if not endpoint:
            raise ValueError("endpoint required for api_wrapper adapter")
        return APIAdapter(endpoint, api_key=api_key)

    else:
        # Fallback to existing local HF model
        return FallbackAdapter(model_name or "sshleifer/tiny-gpt2")
