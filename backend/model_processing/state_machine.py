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
from .adversarial_prompts import get_all_prompts, get_prompt_count, get_split
from .scoring import ViolationScorer, TestRecord
from .purification import ModelPurifier
from .sandbox import SandboxManager
from .patch_generator import PatchGenerator
from .local_lora_trainer import LocalLoRATrainer

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
    "LORA_TRAINING",
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
        self.test_records: List[TestRecord] = []       # Final test split (25 prompts)
        self.train_records: List[TestRecord] = []      # Train split results (75 prompts)
        self.val_records: List[TestRecord] = []        # Validation split results (25 prompts)
        self.verdict: Optional[Dict] = None
        self.purified_adapter: Optional[ModelAdapter] = None
        self.purification_result: Optional[Dict] = None
        self.lora_training_result: Optional[Dict] = None
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
        self.patch_generator = PatchGenerator()
        self.lora_trainer = LocalLoRATrainer()

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

        # HF-direct mode: skip scan/classify/install when using local GPU
        project_exists = os.path.exists(self.context.project_dir)
        
        # Ignore common non-model directories when checking if empty
        ignore_dirs = {'.venv', '__pycache__', '.git', 'node_modules'}
        dir_contents = [f for f in os.listdir(self.context.project_dir) if f not in ignore_dirs] if project_exists else []
        project_is_empty = not project_exists or len(dir_contents) == 0
        
        logger.info(
            f"HF-direct check: "
            f"hf_model_name={bool(self.hf_model_name)}, "
            f"project_exists={project_exists}, "
            f"dir_contents={dir_contents}, "
            f"project_is_empty={project_is_empty}"
        )
        
        # HF-direct mode: When a HuggingFace model name is provided but no files uploaded
        # All models run locally on the RTX GPU
        if self.hf_model_name and project_is_empty:
            logger.info(
                f"HF-direct mode (local GPU): model={self.hf_model_name}, "
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
            "LORA_TRAINING": self._run_lora_training,
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
        """
        READY → TESTING: Run adversarial prompts against the model.

        FIX: Data Leakage Prevention
        Previously used get_all_prompts() (125 prompts) for BOTH training
        AND testing, contaminating accuracy metrics.

        Now uses ONLY the held-out test split (25 prompts) that NEVER
        appears in training data. This gives honest accuracy numbers.
        """
        adapter = self.context.adapter
        if not adapter:
            self._transition("ERROR")
            return

        # Run on TEST split only (25 held-out prompts) for initial evaluation
        # Train + val splits are ONLY run when the user clicks "Train & Test"
        test_prompts = get_split("test")
        logger.info(
            f"Running {len(test_prompts)} TEST-split adversarial tests "
            f"(held-out, never seen during training)..."
        )
        test_records = self.scorer.run_full_test(
            adapter, test_prompts, model_id=self.context.session_id
        )
        self.context.test_records = test_records

        test_pass = sum(1 for r in test_records if r.verdict == "PASS")
        logger.info(
            f"Ethics evaluation complete: "
            f"{test_pass}/{len(test_records)} passed on test split"
        )

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
        """FIXING → RETESTING: Apply local safety wrapper purification."""
        adapter = self.context.adapter
        if not adapter:
            self._transition("ERROR")
            return

        # Get failed tests
        violations = [r for r in self.context.test_records if r.verdict == "FAIL"]

        if not violations:
            self._transition("APPROVED")
            return

        # Local GPU purification using safety wrapper
        logger.info("Applying local safety wrapper purification on GPU")
        purified = self.purifier.purify(adapter, violations, strategy="auto")
        self.context.purified_adapter = purified

        # Verify
        verification = self.purifier.verify_purification(purified, violations)
        self.context.purification_result = verification

        self._transition("RETESTING")

    def _run_lora_training(self):
        """
        LORA_TRAINING → RETESTING: LoRA fine-tuning with anti-forgetting fixes.

        FIX: Three critical improvements:
          1. Generates BALANCED training data (50% pass + 50% fail)
          2. Unloads existing adapter before new round (prevents stacking)
          3. Uses TRAIN split only — never trains on TEST split
        """
        adapter = self.context.adapter
        if not adapter:
            self._transition("ERROR")
            return

        try:
            # ── Step 1: Collect training data NOW (only when user clicks Train) ──
            # This runs the TRAIN split (75 prompts) to get pass/fail records
            # for balanced training data. This does NOT happen during evaluation.
            train_prompts = get_split("train")
            logger.info(
                f"Collecting training data: running {len(train_prompts)} "
                f"TRAIN-split prompts..."
            )
            train_records = self.scorer.run_full_test(
                adapter, train_prompts, model_id=self.context.session_id
            )
            self.context.train_records = train_records

            # Also collect validation data for early stopping
            val_prompts = get_split("val")
            logger.info(f"Collecting validation data: {len(val_prompts)} VAL-split prompts...")
            val_records = self.scorer.run_full_test(
                adapter, val_prompts, model_id=self.context.session_id
            )
            self.context.val_records = val_records

            all_train_records = self.context.train_records
            if not all_train_records:
                logger.warning("No train records available. Falling back to purification.")
                violations = [r for r in self.context.test_records if r.verdict == "FAIL"]
                purified = self.purifier.purify(adapter, violations, strategy="auto")
                self.context.purified_adapter = purified
                verification = self.purifier.verify_purification(purified, violations)
                self.context.purification_result = verification
                self._transition("RETESTING")
                return

            logger.info(
                f"Generating BALANCED training data from {len(all_train_records)} "
                f"train-split records (50% fail + 50% pass)..."
            )
            balanced_patches = self.patch_generator.generate_balanced_patch(
                all_train_records, target_ratio=0.5
            )

            # Save balanced JSONL
            import tempfile
            output_dir = os.path.join(
                tempfile.gettempdir(), "ethos_lora", self.context.session_id
            )
            paths = self.patch_generator.save_split_jsonl(
                balanced_patches, output_dir
            )
            train_jsonl = paths["combined"]

            # ── Step 2: LoRA training with adapter unloading ──
            # The LocalLoRATrainer handles:
            #   - Unloading existing adapter (prevents stacking)
            #   - Attaching fresh LoRA with r=16, alpha=32
            #   - Validation-based early stopping
            logger.info(
                f"Starting LoRA training round {self.lora_trainer.get_round_count() + 1} "
                f"with {len(balanced_patches)} balanced examples..."
            )

            # Note: actual weight training requires raw model access.
            # If adapter wraps a HF model, we can train directly.
            # Otherwise, fall back to purification.
            if hasattr(adapter, '_model'):
                training_result = self.lora_trainer.train(
                    model=adapter._model,
                    tokenizer=getattr(adapter, '_tokenizer', None),
                    train_jsonl=train_jsonl,
                    output_dir=os.path.join(output_dir, "adapter"),
                )
                self.context.lora_training_result = training_result
            else:
                logger.info(
                    "Adapter does not expose raw model. "
                    "Falling back to safety wrapper purification."
                )

            # ── Step 3: Also apply safety wrapper as defense-in-depth ──
            violations = [r for r in all_train_records if r.verdict == "FAIL"]
            purified = self.purifier.purify(adapter, violations, strategy="auto")
            self.context.purified_adapter = purified
            verification = self.purifier.verify_purification(purified, violations)
            self.context.purification_result = verification

            logger.info("LoRA training + purification complete")
            self._transition("RETESTING")

        except Exception as e:
            logger.error(f"LoRA training failed: {e}")
            self.context.errors.append(f"LoRA training failed: {str(e)}")
            self._transition("ERROR")

    def _final_verdict(self):
        """
        RETESTING → APPROVED/REJECTED: Final decision after purification.

        FIX: Reports final accuracy ONLY on the held-out TEST split.
        Previously reported on all 125 prompts (including training data).
        """
        result = self.context.purification_result
        if not result:
            self._transition("ERROR")
            return

        # Re-evaluate on TEST split only for final accuracy
        if self.context.purified_adapter:
            test_eval = self.lora_trainer.evaluate_on_split(
                self.context.purified_adapter,
                self.scorer,
                split="test",
                model_id=self.context.session_id,
            )
            logger.info(
                f"Final TEST-split accuracy: {test_eval['accuracy_pct']} "
                f"({test_eval['pass']}/{test_eval['total']} passed)"
            )
            # Store test-only accuracy in verdict
            if self.context.verdict:
                self.context.verdict["test_accuracy"] = test_eval["accuracy"]
                self.context.verdict["test_accuracy_pct"] = test_eval["accuracy_pct"]

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
