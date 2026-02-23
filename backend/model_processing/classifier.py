"""
Model type classifier.
Determines model type from file structure only — NO EXECUTION ALLOWED.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scanner import FileScanner, ScanResult

logger = logging.getLogger(__name__)


@dataclass
class ModelClassification:
    """Result of model classification."""
    model_type: str  # huggingface | gguf | python_custom | docker | api_wrapper | unknown
    runner: Optional[str] = None
    confidence: float = 0.0
    architecture: Optional[str] = None
    entrypoint: Optional[str] = None
    endpoint: Optional[str] = None
    action: str = "PROCEED"  # PROCEED | REJECT
    rejection_reason: Optional[str] = None
    required_dependencies: List[str] = field(default_factory=list)
    security_risk: str = "low"  # low | medium | high
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": self.model_type,
            "runner": self.runner,
            "confidence": self.confidence,
            "architecture": self.architecture,
            "entrypoint": self.entrypoint,
            "endpoint": self.endpoint,
            "action": self.action,
            "rejection_reason": self.rejection_reason,
            "required_dependencies": self.required_dependencies,
            "security_risk": self.security_risk,
            "details": self.details,
        }


class ModelClassifier:
    """
    Classify uploaded model type from file structure only.
    Priority order: GGUF → HuggingFace → Docker → Python Custom → API Wrapper → Unknown.
    """

    def __init__(self):
        self.scanner = FileScanner()

    def classify(self, project_dir: str) -> ModelClassification:
        """
        Scan and classify a model upload.

        Args:
            project_dir: Absolute path to uploaded project directory.

        Returns:
            ModelClassification with type, runner, confidence, etc.
        """
        scan = self.scanner.scan(project_dir)

        # Security pre-check
        if scan.suspicious_files:
            risk = "high" if len(scan.suspicious_files) > 3 else "medium"
            logger.warning(f"Suspicious files detected: {scan.suspicious_files}")
        else:
            risk = "low"

        # Run classifiers in priority order
        result = (
            self._detect_gguf(scan)
            or self._detect_huggingface(scan)
            or self._detect_docker(scan)
            or self._detect_python_custom(scan)
            or self._detect_api_wrapper(scan)
            or self._unknown(scan)
        )

        result.security_risk = risk
        result.details["scan_summary"] = {
            "file_count": scan.file_count,
            "total_size_mb": round(scan.total_size / (1024 * 1024), 2),
            "extensions": scan.extensions,
            "framework_hints": scan.framework_hints,
            "suspicious_files": scan.suspicious_files,
        }

        logger.info(
            f"Classification: type={result.model_type}, "
            f"runner={result.runner}, confidence={result.confidence}, "
            f"action={result.action}"
        )
        return result

    # ── Detectors ─────────────────────────────────────────────────────

    def _detect_gguf(self, scan: ScanResult) -> Optional[ModelClassification]:
        """Priority 1: GGUF/GGML models (simplest, pure data)."""
        if not scan.gguf_files:
            return None
        return ModelClassification(
            model_type="gguf",
            runner="llama.cpp",
            confidence=1.0,
            entrypoint=scan.gguf_files[0],
            required_dependencies=["llama-cpp-python>=0.2.0"],
            details={"gguf_files": scan.gguf_files},
        )

    def _detect_huggingface(self, scan: ScanResult) -> Optional[ModelClassification]:
        """Priority 2: HuggingFace Transformers models."""
        if not scan.has_config_json:
            return None

        # Look for architectures field in config.json
        config_data = scan.config_files.get("config.json", {})
        if not isinstance(config_data, dict):
            return None

        architectures = config_data.get("architectures", [])
        model_type_field = config_data.get("model_type", "")

        # Strong signal: config.json + tokenizer
        if scan.has_tokenizer and (architectures or model_type_field):
            arch = architectures[0] if architectures else model_type_field
            deps = [
                "torch>=2.0.0",
                "transformers>=4.30.0",
                "accelerate>=0.20.0",
                "safetensors>=0.3.0",
            ]
            if scan.has_requirements:
                deps.append("requirements.txt")
            return ModelClassification(
                model_type="huggingface",
                runner="transformers",
                confidence=1.0,
                architecture=arch,
                required_dependencies=deps,
            )

        # Weaker signal: config.json with architectures but no tokenizer
        if architectures or model_type_field:
            arch = architectures[0] if architectures else model_type_field
            return ModelClassification(
                model_type="huggingface",
                runner="transformers",
                confidence=0.7,
                architecture=arch,
                required_dependencies=[
                    "torch>=2.0.0",
                    "transformers>=4.30.0",
                ],
            )

        return None

    def _detect_docker(self, scan: ScanResult) -> Optional[ModelClassification]:
        """Priority 3: Docker containerized models."""
        if not scan.has_dockerfile:
            return None
        return ModelClassification(
            model_type="docker",
            runner="docker",
            confidence=0.9,
            required_dependencies=["docker-build"],
        )

    def _detect_python_custom(self, scan: ScanResult) -> Optional[ModelClassification]:
        """Priority 4: Python inference scripts."""
        # Strong signal: inference.py with generate/predict
        if scan.has_inference_py:
            has_func = (
                "has_generate" in scan.framework_hints
                or "has_predict" in scan.framework_hints
            )
            if has_func:
                deps = ["requirements.txt"] if scan.has_requirements else []
                return ModelClassification(
                    model_type="python_custom",
                    runner="python",
                    confidence=0.9,
                    entrypoint="inference.py",
                    required_dependencies=deps,
                )
            # inference.py exists but no standard functions
            return ModelClassification(
                model_type="python_custom",
                runner="python",
                confidence=0.6,
                entrypoint="inference.py",
                required_dependencies=["requirements.txt"] if scan.has_requirements else [],
            )

        # Weaker signal: Python files with ML framework imports
        ml_frameworks = {"torch", "transformers", "tensorflow", "onnx", "llama_cpp"}
        detected_ml = [h for h in scan.framework_hints if h in ml_frameworks]
        if scan.python_files and detected_ml:
            # Find likely entrypoint
            candidates = ["main.py", "app.py", "run.py", "predict.py", "serve.py"]
            entrypoint = None
            for c in candidates:
                if c in scan.file_tree:
                    entrypoint = c
                    break
            if not entrypoint and scan.python_files:
                entrypoint = scan.python_files[0]

            return ModelClassification(
                model_type="python_custom",
                runner="python",
                confidence=0.5,
                entrypoint=entrypoint,
                required_dependencies=["requirements.txt"] if scan.has_requirements else [],
                details={"detected_frameworks": detected_ml},
            )

        return None

    def _detect_api_wrapper(self, scan: ScanResult) -> Optional[ModelClassification]:
        """Priority 5: API wrapper models."""
        if not scan.has_model_yaml:
            return None

        # Check for endpoint in model.yaml
        yaml_key = "model.yaml" if "model.yaml" in scan.config_files else "model.yml"
        config = scan.config_files.get(yaml_key, {})
        if not isinstance(config, dict):
            return None

        endpoint = config.get("endpoint", config.get("url", config.get("api_url")))
        if endpoint:
            return ModelClassification(
                model_type="api_wrapper",
                runner="http_client",
                confidence=0.9,
                endpoint=str(endpoint),
                required_dependencies=["requests", "httpx"],
            )

        return None

    def _unknown(self, scan: ScanResult) -> ModelClassification:
        """Fallback: unknown model type → REJECT."""
        return ModelClassification(
            model_type="unknown",
            runner=None,
            confidence=0.0,
            action="REJECT",
            rejection_reason="Unknown file structure — does not match any supported model type.",
        )
