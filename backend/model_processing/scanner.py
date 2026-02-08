"""
File scanner for static model inspection.
Analyzes uploaded model files WITHOUT executing anything.
"""
import os
import json
import yaml
import logging
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

# Directories to skip during scanning
SKIP_DIRS: Set[str] = {
    '.git', 'node_modules', '__pycache__', '.pytest_cache',
    '.venv', 'venv', 'env', '.tox', 'eggs', '.cache',
    'dist', 'build', '.next',
}

# Suspicious file extensions that warrant security review
SUSPICIOUS_EXTENSIONS: Set[str] = {
    '.exe', '.dll', '.so', '.dylib', '.bat', '.cmd', '.ps1',
    '.sh', '.bash', '.msi', '.deb', '.rpm',
}

# Binary model file extensions (expected, not suspicious)
MODEL_EXTENSIONS: Set[str] = {
    '.bin', '.pt', '.pth', '.onnx', '.tflite', '.h5',
    '.safetensors', '.gguf', '.ggml', '.pkl', '.pickle',
}


class ScanResult:
    """Result of a file scan."""

    def __init__(self):
        self.file_tree: List[str] = []
        self.extensions: Dict[str, int] = {}
        self.total_size: int = 0
        self.file_count: int = 0
        self.dir_count: int = 0
        self.config_files: Dict[str, Any] = {}
        self.suspicious_files: List[str] = []
        self.framework_hints: List[str] = []
        self.has_requirements: bool = False
        self.has_dockerfile: bool = False
        self.has_config_json: bool = False
        self.has_tokenizer: bool = False
        self.has_model_weights: bool = False
        self.has_inference_py: bool = False
        self.has_model_yaml: bool = False
        self.gguf_files: List[str] = []
        self.python_files: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_tree": self.file_tree,
            "extensions": self.extensions,
            "total_size": self.total_size,
            "total_size_mb": round(self.total_size / (1024 * 1024), 2),
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "config_files": {k: str(type(v).__name__) for k, v in self.config_files.items()},
            "suspicious_files": self.suspicious_files,
            "framework_hints": self.framework_hints,
            "flags": {
                "has_requirements": self.has_requirements,
                "has_dockerfile": self.has_dockerfile,
                "has_config_json": self.has_config_json,
                "has_tokenizer": self.has_tokenizer,
                "has_model_weights": self.has_model_weights,
                "has_inference_py": self.has_inference_py,
                "has_model_yaml": self.has_model_yaml,
                "gguf_file_count": len(self.gguf_files),
                "python_file_count": len(self.python_files),
            },
        }


class FileScanner:
    """
    Static file scanner that analyzes model uploads without execution.
    Builds a complete picture of the uploaded files for classification.
    """

    def scan(self, project_dir: str) -> ScanResult:
        """
        Scan a project directory and return a comprehensive ScanResult.

        Args:
            project_dir: Absolute path to the uploaded project directory.

        Returns:
            ScanResult with all detected metadata.
        """
        result = ScanResult()

        if not os.path.isdir(project_dir):
            logger.error(f"Scan target is not a directory: {project_dir}")
            return result

        for root, dirs, files in os.walk(project_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            result.dir_count += len(dirs)

            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
                result.file_tree.append(rel_path)
                result.file_count += 1

                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                result.total_size += size

                # Track extensions
                _, ext = os.path.splitext(fname.lower())
                result.extensions[ext] = result.extensions.get(ext, 0) + 1

                # Detect suspicious files
                if ext in SUSPICIOUS_EXTENSIONS:
                    result.suspicious_files.append(rel_path)

                # Detect key files
                fname_lower = fname.lower()

                if fname_lower == "requirements.txt":
                    result.has_requirements = True

                if fname_lower == "dockerfile":
                    result.has_dockerfile = True

                if fname_lower == "config.json":
                    result.has_config_json = True
                    self._try_parse_json(full_path, rel_path, result)

                if fname_lower in ("tokenizer.json", "tokenizer_config.json"):
                    result.has_tokenizer = True

                if (fname_lower in ("pytorch_model.bin", "model.safetensors",
                                    "tf_model.h5", "flax_model.msgpack",
                                    "model.safetensors.index.json")
                    or ext in ('.safetensors', '.bin', '.pt', '.pth', '.gguf',
                               '.ggml', '.onnx', '.h5', '.pkl')):
                    result.has_model_weights = True

                if fname_lower == "inference.py":
                    result.has_inference_py = True
                    self._check_inference_functions(full_path, result)

                if fname_lower == "model.yaml" or fname_lower == "model.yml":
                    result.has_model_yaml = True
                    self._try_parse_yaml(full_path, rel_path, result)

                if ext in (".gguf", ".ggml"):
                    result.gguf_files.append(rel_path)

                if ext == ".py":
                    result.python_files.append(rel_path)

                # Detect framework hints from Python files
                if ext == ".py":
                    self._detect_framework_hints(full_path, result)

                # Parse other config files
                if ext == ".json" and fname_lower != "config.json":
                    self._try_parse_json(full_path, rel_path, result)
                if ext in (".yaml", ".yml") and fname_lower not in ("model.yaml", "model.yml"):
                    self._try_parse_yaml(full_path, rel_path, result)
                if ext == ".toml":
                    self._try_parse_toml(full_path, rel_path, result)

        logger.info(
            f"Scan complete: {result.file_count} files, "
            f"{result.dir_count} dirs, "
            f"{result.total_size / 1024:.1f} KB total"
        )
        return result

    # ── Helpers ────────────────────────────────────────────────────────

    def _try_parse_json(self, path: str, rel: str, result: ScanResult):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            result.config_files[rel] = data
            # Also store by bare filename for easy lookup by classifier
            basename = os.path.basename(rel)
            if basename not in result.config_files:
                result.config_files[basename] = data
        except Exception:
            pass

    def _try_parse_yaml(self, path: str, rel: str, result: ScanResult):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = yaml.safe_load(f)
            result.config_files[rel] = data
            basename = os.path.basename(rel)
            if basename not in result.config_files:
                result.config_files[basename] = data
        except Exception:
            pass

    def _try_parse_toml(self, path: str, rel: str, result: ScanResult):
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore
            except ImportError:
                return
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
            result.config_files[rel] = data
            basename = os.path.basename(rel)
            if basename not in result.config_files:
                result.config_files[basename] = data
        except Exception:
            pass

    def _detect_framework_hints(self, path: str, result: ScanResult):
        """Detect framework imports in Python files (read first 50 lines)."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = "".join(f.readline() for _ in range(50))
        except Exception:
            return

        hints_map = {
            "torch": ("import torch", "from torch"),
            "transformers": ("from transformers", "import transformers"),
            "tensorflow": ("import tensorflow", "from tensorflow"),
            "onnx": ("import onnx", "import onnxruntime"),
            "flask": ("from flask", "import flask"),
            "fastapi": ("from fastapi", "import fastapi"),
            "django": ("from django", "import django"),
            "llama_cpp": ("from llama_cpp", "import llama_cpp"),
        }

        for framework, patterns in hints_map.items():
            if any(p in head for p in patterns) and framework not in result.framework_hints:
                result.framework_hints.append(framework)

    def _check_inference_functions(self, path: str, result: ScanResult):
        """Check if inference.py contains generate() or predict()."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return

        if "def generate(" in content:
            if "has_generate" not in result.framework_hints:
                result.framework_hints.append("has_generate")
        if "def predict(" in content:
            if "has_predict" not in result.framework_hints:
                result.framework_hints.append("has_predict")
