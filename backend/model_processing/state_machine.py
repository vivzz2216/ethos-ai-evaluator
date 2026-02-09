"""
Model Processing State Machine.
Orchestrates the entire pipeline: Upload → Scan → Classify → Install → Test → Score → Fix → Verdict.
"""
import os
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .scanner import FileScanner
from .classifier import ModelClassifier, ModelClassification
from .dependencies import DependencyResolver, InstallResult
from .adapters import ModelAdapter, create_adapter, FallbackAdapter
from .adversarial_prompts import get_all_prompts, get_prompt_count
from .scoring import ViolationScorer, TestRecord
from .purification import ModelPurifier
from .sandbox import SandboxManager

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# STATE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════

STATES = [
    "UPLOADED",
    "SCANNING",
    "CLASSIFIED",
    "INSTALLING",
    "READY",
    "TESTING",
    "SCORED",
    "FIXING",
    "RETESTING",
    "APPROVED",
    "REJECTED",
    "ERROR",
]

TERMINAL_STATES = {"APPROVED", "REJECTED", "ERROR"}


class ProcessingContext:
    """Holds all data accumulated during pipeline processing."""

    def __init__(self, project_dir: str, session_id: str):
        self.project_dir = project_dir
        self.session_id = session_id
        self.scan_result: Optional[Dict] = None
        self.classification: Optional[ModelClassification] = None
        self.install_result: Optional[InstallResult] = None
        self.adapter: Optional[ModelAdapter] = None
        self.test_records: List[TestRecord] = []
        self.verdict: Optional[Dict] = None
        self.purified_adapter: Optional[ModelAdapter] = None
        self.purification_result: Optional[Dict] = None
        self.errors: List[str] = []
        self.started_at: str = datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = None
        self.duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_dir": self.project_dir,
            "scan_result": self.scan_result,
            "classification": (self.classification.to_dict() if hasattr(self.classification, 'to_dict') else vars(self.classification)) if self.classification else None,
            "install_result": self.install_result.to_dict() if hasattr(self.install_result, 'to_dict') and self.install_result else None,
            "test_summary": {
                "total_tests": len(self.test_records),
                "records": [r.to_dict() for r in self.test_records],  # Return ALL records for full report
            } if self.test_records else None,
            "verdict": self.verdict,
            "purification_result": self.purification_result,
            "errors": self.errors,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 2),
        }


class ModelProcessingStateMachine:
    """
    Strict state machine that processes uploaded models through the full pipeline.
    Does NOT improvise — follows predefined recipes.
    """

    def __init__(
        self,
        project_dir: str,
        session_id: str,
        pip_exe: Optional[str] = None,
        python_exe: Optional[str] = None,
        hf_model_name: Optional[str] = None,
        max_test_prompts: Optional[int] = None,
    ):
        self.state = "UPLOADED"
        self.context = ProcessingContext(project_dir, session_id)
        self.pip_exe = pip_exe
        self.python_exe = python_exe or "python"
        self.hf_model_name = hf_model_name
        self.max_test_prompts = max_test_prompts

        # Components
        self.scanner = FileScanner()
        self.classifier = ModelClassifier()
        self.dependency_resolver = DependencyResolver()
        self.scorer = ViolationScorer()
        self.purifier = ModelPurifier()
        self.sandbox = SandboxManager()

        self._state_log: List[Dict[str, Any]] = []

    # ── Main Processing Loop ──────────────────────────────────────────

    def process(self) -> Dict[str, Any]:
        """
        Run through all states until a terminal state is reached.

        Returns:
            Final processing result dict.
        """
        start = time.time()
        logger.info(f"Starting model processing for session {self.context.session_id}")

        # HF-direct mode: skip scan/classify/install when using remote GPU
        remote_url = os.environ.get("REMOTE_MODEL_URL", "").strip()
        project_exists = os.path.exists(self.context.project_dir)
        
        # Ignore common non-model directories when checking if empty
        ignore_dirs = {'.venv', '__pycache__', '.git', 'node_modules'}
        dir_contents = [f for f in os.listdir(self.context.project_dir) if f not in ignore_dirs] if project_exists else []
        project_is_empty = not project_exists or len(dir_contents) == 0
        
        logger.info(
            f"HF-direct check: remote_url={bool(remote_url)}, "
            f"hf_model_name={bool(self.hf_model_name)}, "
            f"project_exists={project_exists}, "
            f"dir_contents={dir_contents}, "
            f"project_is_empty={project_is_empty}"
        )
        
        # HF-direct mode: When a HuggingFace model name is provided but no files uploaded
        # This works with OR without a remote GPU URL
        if self.hf_model_name and project_is_empty:
            mode_desc = "remote GPU" if remote_url else "local download"
            logger.info(
                f"HF-direct mode ({mode_desc}): model={self.hf_model_name}, "
                f"project_dir empty, skipping scan/classify/install"
            )
            # Create a synthetic classification so the adapter factory works
            from types import SimpleNamespace
            self.context.classification = SimpleNamespace(
                model_type="huggingface",
                runner="transformers",
                confidence=1.0,
                architecture=None,
                entrypoint=None,
                endpoint=None,
                action="PROCEED",
                rejection_reason=None,
                required_dependencies=[],
                security_risk="low",
            )
            self.state = "INSTALLING"  # Jump to adapter creation

        while self.state not in TERMINAL_STATES:
            prev_state = self.state
            try:
                self._step()
            except Exception as e:
                logger.error(f"Error in state {self.state}: {e}")
                self.context.errors.append(f"[{self.state}] {str(e)}")
                self._transition("ERROR")
                break

            self._state_log.append({
                "from": prev_state,
                "to": self.state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        self.context.duration_seconds = time.time() - start
        self.context.completed_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Processing complete: state={self.state}, "
            f"duration={self.context.duration_seconds:.1f}s"
        )

        return self.get_result()

    def _step(self):
        """Execute one state transition."""
        handler = {
            "UPLOADED": self._scan_files,
            "SCANNING": self._classify_model,
            "CLASSIFIED": self._install_dependencies,
            "INSTALLING": self._prepare_adapter,
            "READY": self._run_ethics_tests,
            "TESTING": self._score_results,
            "SCORED": self._decide_action,
            "FIXING": self._apply_purification,
            "RETESTING": self._final_verdict,
        }.get(self.state)

        if handler:
            handler()
        else:
            logger.error(f"No handler for state: {self.state}")
            self._transition("ERROR")

    def _transition(self, new_state: str):
        """Transition to a new state."""
        logger.info(f"State transition: {self.state} → {new_state}")
        self.state = new_state

    # ── State Handlers ────────────────────────────────────────────────

    def _scan_files(self):
        """UPLOADED → SCANNING: Scan the project directory."""
        scan = self.scanner.scan(self.context.project_dir)
        self.context.scan_result = scan.to_dict()

        # Check project size
        size_check = self.sandbox.check_project_size(self.context.project_dir)
        if not size_check["within_limits"]:
            self.context.errors.append(
                f"Project too large: {size_check['total_size_mb']}MB "
                f"(max: {size_check['max_disk_mb']}MB)"
            )
            self._transition("REJECTED")
            return

        self._transition("SCANNING")

    def _classify_model(self):
        """SCANNING → CLASSIFIED: Classify the model type."""
        classification = self.classifier.classify(self.context.project_dir)
        self.context.classification = classification

        if classification.action == "REJECT":
            self.context.errors.append(
                f"Model rejected: {classification.rejection_reason}"
            )
            self.context.verdict = {
                "verdict": "REJECT",
                "reason": classification.rejection_reason,
                "stage": "classification",
            }
            self._transition("REJECTED")
            return

        # Check security risk
        if classification.security_risk == "high":
            self.context.errors.append("High security risk detected")
            self.context.verdict = {
                "verdict": "REJECT",
                "reason": "High security risk — suspicious files detected",
                "stage": "classification",
            }
            self._transition("REJECTED")
            return

        self._transition("CLASSIFIED")

    def _install_dependencies(self):
        """CLASSIFIED → INSTALLING: Install required packages."""
        classification = self.context.classification
        if not classification:
            self._transition("ERROR")
            return

        packages = self.dependency_resolver.resolve(
            classification, self.context.project_dir
        )

        if packages and self.pip_exe:
            install_result = self.dependency_resolver.install(
                packages, self.pip_exe, self.context.project_dir
            )
            self.context.install_result = install_result

            if not install_result.success:
                logger.warning(
                    f"Some packages failed to install: {install_result.packages_failed}"
                )
                # Don't fail — some packages may be optional
        else:
            logger.info("No packages to install or no pip executable available")

        self._transition("INSTALLING")

    def _prepare_adapter(self):
        """INSTALLING → READY: Create the model adapter."""
        classification = self.context.classification
        if not classification:
            self._transition("ERROR")
            return

        try:
            # Try to create the appropriate adapter
            logger.info(
                f"Creating adapter: type={classification.model_type}, "
                f"project_dir={self.context.project_dir}"
            )
            adapter = create_adapter(
                model_type=classification.model_type,
                project_dir=self.context.project_dir,
                python_exe=self.python_exe,
                entrypoint=classification.entrypoint,
                endpoint=classification.endpoint,
                model_name=self.hf_model_name,
            )

            # Health check
            if adapter.health_check():
                self.context.adapter = adapter
                logger.info(f"Adapter ready: {adapter.get_info()}")
            elif self.hf_model_name:
                # Only use fallback if the user explicitly provided a HF model name
                logger.warning(
                    f"Adapter health check failed, using user-specified fallback: "
                    f"{self.hf_model_name}"
                )
                self.context.adapter = FallbackAdapter(self.hf_model_name)
            else:
                error_msg = (
                    "Model failed to load. This usually means insufficient "
                    "memory (RAM/VRAM). Close other applications (especially "
                    "LM Studio, browsers) and try again. Your GPU has limited "
                    "VRAM — the platform uses 4-bit quantization automatically "
                    "but still needs ~4GB free RAM during loading."
                )
                self.context.errors.append(error_msg)
                logger.error(f"Adapter health check failed, no fallback: {error_msg}")
                self._transition("ERROR")
                return

        except Exception as e:
            if self.hf_model_name:
                logger.warning(
                    f"Failed to create adapter ({e}), using user-specified "
                    f"fallback: {self.hf_model_name}"
                )
                self.context.adapter = FallbackAdapter(self.hf_model_name)
            else:
                error_msg = (
                    f"Failed to load model: {str(e)}. "
                    f"Close other applications to free RAM/VRAM and try again."
                )
                self.context.errors.append(error_msg)
                logger.error(error_msg)
                self._transition("ERROR")
                return

        logger.info(f"Final adapter: {self.context.adapter.get_info()}")

        self._transition("READY")

    def _run_ethics_tests(self):
        """READY → TESTING: Run adversarial prompts against the model."""
        adapter = self.context.adapter
        if not adapter:
            self._transition("ERROR")
            return

        prompts = get_all_prompts()

        # Optionally limit number of prompts
        if self.max_test_prompts and self.max_test_prompts < len(prompts):
            # Sample evenly from each category
            from .adversarial_prompts import ADVERSARIAL_PROMPTS
            sampled = []
            per_cat = max(1, self.max_test_prompts // len(ADVERSARIAL_PROMPTS))
            for cat, cat_prompts in ADVERSARIAL_PROMPTS.items():
                for i, p in enumerate(cat_prompts[:per_cat]):
                    sampled.append({"id": f"{cat}_{i+1:03d}", "category": cat, "prompt": p})
            prompts = sampled

        logger.info(f"Running {len(prompts)} adversarial tests...")
        records = self.scorer.run_full_test(
            adapter, prompts, model_id=self.context.session_id
        )
        self.context.test_records = records
        self._transition("TESTING")

    def _score_results(self):
        """TESTING → SCORED: Aggregate scores and compute verdict."""
        verdict = self.scorer.make_verdict(self.context.test_records)
        self.context.verdict = verdict
        self._transition("SCORED")

    def _decide_action(self):
        """SCORED → APPROVED/FIXING/REJECTED: Decide model fate."""
        verdict = self.context.verdict
        if not verdict:
            self._transition("ERROR")
            return

        decision = verdict["verdict"]

        if decision == "APPROVE" or decision == "WARN":
            self._transition("APPROVED")
        elif decision == "NEEDS_FIX":
            self._transition("FIXING")
        elif decision == "REJECT":
            self._transition("REJECTED")
        else:
            self._transition("ERROR")

    def _apply_purification(self):
        """FIXING → RETESTING: Apply safety wrappers and re-test."""
        adapter = self.context.adapter
        if not adapter:
            self._transition("ERROR")
            return

        # Get failed tests
        violations = [r for r in self.context.test_records if r.verdict == "FAIL"]

        if not violations:
            self._transition("APPROVED")
            return

        # Purify
        purified = self.purifier.purify(adapter, violations, strategy="auto")
        self.context.purified_adapter = purified

        # Verify
        verification = self.purifier.verify_purification(purified, violations)
        self.context.purification_result = verification

        self._transition("RETESTING")

    def _final_verdict(self):
        """RETESTING → APPROVED/REJECTED: Final decision after purification."""
        result = self.context.purification_result
        if not result:
            self._transition("ERROR")
            return

        if result["passed"]:
            self.context.verdict["verdict"] = "APPROVED"
            self.context.verdict["purified"] = True
            self.context.verdict["fix_rate"] = result["fix_rate"]
            self._transition("APPROVED")
        else:
            self.context.verdict["verdict"] = "REJECTED"
            self.context.verdict["reason"] = (
                f"Purification failed: {result['still_failing']} tests still failing "
                f"(fix rate: {result['fix_rate']}%)"
            )
            self._transition("REJECTED")

    # ── Public API ────────────────────────────────────────────────────

    def get_state(self) -> str:
        """Get current state."""
        return self.state

    def get_result(self) -> Dict[str, Any]:
        """Get full processing result."""
        return {
            "state": self.state,
            "context": self.context.to_dict(),
            "state_log": self._state_log,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get lightweight status for polling."""
        return {
            "state": self.state,
            "session_id": self.context.session_id,
            "classification": (
                self.context.classification.model_type
                if self.context.classification else None
            ),
            "verdict": self.context.verdict.get("verdict") if self.context.verdict else None,
            "test_count": len(self.context.test_records),
            "errors": self.context.errors[-3:],  # Last 3 errors
            "duration_seconds": round(self.context.duration_seconds, 2),
        }
