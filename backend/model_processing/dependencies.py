"""
Dependency resolution engine.
Automatically determines and installs packages based on model type.
"""
import os
import subprocess
import logging
from typing import Dict, List, Optional, Any

from .classifier import ModelClassification

logger = logging.getLogger(__name__)

# Pre-defined dependency recipes per model type
DEPENDENCY_RECIPES: Dict[str, List[str]] = {
    "huggingface": [
        "torch>=2.0.0",
        "transformers>=4.30.0",
        "accelerate>=0.20.0",
        "safetensors>=0.3.0",
    ],
    "gguf": [
        "llama-cpp-python>=0.2.0",
    ],
    "python_custom": [],  # Parsed from requirements.txt
    "docker": [],  # No pip packages needed
    "api_wrapper": [
        "requests>=2.28.0",
        "httpx>=0.24.0",
    ],
}


class InstallResult:
    """Result of a dependency installation."""

    def __init__(self):
        self.success: bool = False
        self.packages_installed: List[str] = []
        self.packages_failed: List[str] = []
        self.total_time_seconds: float = 0.0
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "packages_installed": self.packages_installed,
            "packages_failed": self.packages_failed,
            "total_time_seconds": round(self.total_time_seconds, 2),
            "errors": self.errors,
        }


class DependencyResolver:
    """
    Resolves and installs dependencies for classified models.
    Uses the session's virtual environment for isolation.
    """

    def resolve(
        self, classification: ModelClassification, project_dir: str
    ) -> List[str]:
        """
        Determine the full list of packages to install.

        Args:
            classification: The model classification result.
            project_dir: Path to the project directory.

        Returns:
            List of pip package specifiers to install.
        """
        model_type = classification.model_type
        packages: List[str] = []

        # Start with recipe defaults
        recipe = DEPENDENCY_RECIPES.get(model_type, [])
        packages.extend(recipe)

        # Parse requirements.txt if present
        req_path = os.path.join(project_dir, "requirements.txt")
        if os.path.isfile(req_path):
            parsed = self._parse_requirements(req_path)
            # Merge without duplicates (by package name)
            existing_names = {self._package_name(p) for p in packages}
            for pkg in parsed:
                if self._package_name(pkg) not in existing_names:
                    packages.append(pkg)

        # Add any extra dependencies from classification
        for dep in classification.required_dependencies:
            if dep == "requirements.txt":
                continue  # Already handled above
            if dep == "docker-build":
                continue  # Not a pip package
            name = self._package_name(dep)
            if name not in {self._package_name(p) for p in packages}:
                packages.append(dep)

        logger.info(f"Resolved {len(packages)} packages for {model_type}: {packages}")
        return packages

    def install(
        self,
        packages: List[str],
        pip_exe: str,
        project_dir: str,
        timeout: int = 300,
    ) -> InstallResult:
        """
        Install packages into the session's virtual environment.

        Args:
            packages: List of pip package specifiers.
            pip_exe: Path to the venv's pip executable.
            project_dir: Working directory for installation.
            timeout: Max seconds for the entire install.

        Returns:
            InstallResult with success/failure details.
        """
        result = InstallResult()

        if not packages:
            result.success = True
            return result

        if not os.path.isfile(pip_exe):
            result.errors.append(f"pip executable not found: {pip_exe}")
            return result

        import time
        start = time.time()

        # Install all packages in one batch for speed
        cmd = [pip_exe, "install", "--no-cache-dir"] + packages
        logger.info(f"Installing: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_dir,
                timeout=timeout,
            )
            result.total_time_seconds = time.time() - start

            if proc.returncode == 0:
                result.success = True
                result.packages_installed = packages
                # Parse actual installed packages from output
                for line in proc.stdout.split("\n"):
                    if "Successfully installed" in line:
                        result.packages_installed = line.split("Successfully installed ")[1].split()
                logger.info(f"Installation successful: {result.packages_installed}")
            else:
                # Try installing one by one to identify failures
                result.errors.append(f"Batch install failed: {proc.stderr[:500]}")
                logger.warning("Batch install failed, trying individual packages...")
                result = self._install_individually(packages, pip_exe, project_dir, timeout)

        except subprocess.TimeoutExpired:
            result.total_time_seconds = time.time() - start
            result.errors.append(f"Installation timed out after {timeout}s")
            logger.error(f"Installation timed out after {timeout}s")
        except Exception as e:
            result.total_time_seconds = time.time() - start
            result.errors.append(str(e))
            logger.error(f"Installation error: {e}")

        return result

    def estimate(self, packages: List[str]) -> Dict[str, Any]:
        """
        Estimate installation time and disk space.

        Args:
            packages: List of package specifiers.

        Returns:
            Dict with estimated_time_seconds and estimated_disk_mb.
        """
        # Rough estimates per package category
        heavy = {"torch", "tensorflow", "transformers", "llama-cpp-python"}
        medium = {"accelerate", "safetensors", "onnxruntime", "scipy", "numpy"}

        time_est = 0
        disk_est = 0
        for pkg in packages:
            name = self._package_name(pkg)
            if name in heavy:
                time_est += 60
                disk_est += 2000  # ~2GB
            elif name in medium:
                time_est += 15
                disk_est += 200  # ~200MB
            else:
                time_est += 5
                disk_est += 20  # ~20MB

        return {
            "estimated_time_seconds": time_est,
            "estimated_disk_mb": disk_est,
            "package_count": len(packages),
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _parse_requirements(self, path: str) -> List[str]:
        """Parse a requirements.txt file into package specifiers."""
        packages = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    packages.append(line)
        except Exception as e:
            logger.warning(f"Failed to parse requirements.txt: {e}")
        return packages

    def _package_name(self, specifier: str) -> str:
        """Extract package name from a pip specifier like 'torch>=2.0.0'."""
        for sep in (">=", "<=", "==", "!=", ">", "<", "[", ";"):
            if sep in specifier:
                return specifier.split(sep)[0].strip().lower()
        return specifier.strip().lower()

    def _install_individually(
        self, packages: List[str], pip_exe: str, project_dir: str, timeout: int
    ) -> InstallResult:
        """Install packages one by one to identify which fail."""
        import time
        result = InstallResult()
        start = time.time()

        for pkg in packages:
            try:
                proc = subprocess.run(
                    [pip_exe, "install", "--no-cache-dir", pkg],
                    capture_output=True,
                    text=True,
                    cwd=project_dir,
                    timeout=max(60, timeout // len(packages)),
                )
                if proc.returncode == 0:
                    result.packages_installed.append(pkg)
                else:
                    result.packages_failed.append(pkg)
                    result.errors.append(f"{pkg}: {proc.stderr[:200]}")
            except subprocess.TimeoutExpired:
                result.packages_failed.append(pkg)
                result.errors.append(f"{pkg}: timed out")
            except Exception as e:
                result.packages_failed.append(pkg)
                result.errors.append(f"{pkg}: {str(e)}")

        result.total_time_seconds = time.time() - start
        result.success = len(result.packages_failed) == 0
        return result
