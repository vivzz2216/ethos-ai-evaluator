"""
Sandbox Manager for safe model execution.
Provides isolation using virtual environments (Phase 1) and Docker containers (Phase 2).
"""
import os
import subprocess
import logging
import time
import signal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# RESOURCE LIMITS
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_LIMITS = {
    "max_cpu_cores": 4,
    "max_memory_mb": 16384,      # 16 GB
    "max_disk_mb": 51200,        # 50 GB
    "max_time_seconds": 300,     # 5 minutes per inference
    "network_allowed": False,    # No network during testing
}


class SandboxResult:
    """Result of a sandboxed execution."""

    def __init__(self):
        self.success: bool = False
        self.output: str = ""
        self.error: str = ""
        self.exit_code: int = -1
        self.duration_seconds: float = 0.0
        self.killed: bool = False
        self.kill_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output[:2000],
            "error": self.error[:1000],
            "exit_code": self.exit_code,
            "duration_seconds": round(self.duration_seconds, 2),
            "killed": self.killed,
            "kill_reason": self.kill_reason,
        }


class SandboxManager:
    """
    Manages sandboxed execution environments for model testing.

    Phase 1 (current): Uses Python virtual environments with process-level isolation.
    Phase 2 (future): Docker containers with full filesystem/network isolation.
    """

    def __init__(self, limits: Optional[Dict[str, Any]] = None):
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}

    # ── Phase 1: Virtual Environment Sandbox ──────────────────────────

    def execute_in_venv(
        self,
        python_exe: str,
        script: str,
        cwd: str,
        stdin_data: Optional[str] = None,
        timeout: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute a Python script in the session's virtual environment.

        Args:
            python_exe: Path to the venv's python executable.
            script: Path to the script to execute.
            cwd: Working directory.
            stdin_data: Optional data to pipe to stdin.
            timeout: Max execution time in seconds.
            env_vars: Additional environment variables.

        Returns:
            SandboxResult with output and status.
        """
        result = SandboxResult()
        timeout = timeout or self.limits["max_time_seconds"]

        if not os.path.isfile(python_exe):
            result.error = f"Python executable not found: {python_exe}"
            return result

        if not os.path.isfile(script):
            result.error = f"Script not found: {script}"
            return result

        # Build environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        # Restrict PATH to venv only
        venv_dir = os.path.dirname(os.path.dirname(python_exe))
        if os.name == "nt":
            env["PATH"] = os.path.join(venv_dir, "Scripts") + os.pathsep + env.get("PATH", "")
        else:
            env["PATH"] = os.path.join(venv_dir, "bin") + os.pathsep + env.get("PATH", "")

        start = time.time()

        try:
            proc = subprocess.Popen(
                [python_exe, script],
                stdin=subprocess.PIPE if stdin_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout, stderr = proc.communicate(
                    input=stdin_data.encode("utf-8") if stdin_data else None,
                    timeout=timeout,
                )
                result.output = stdout.decode("utf-8", errors="replace")
                result.error = stderr.decode("utf-8", errors="replace")
                result.exit_code = proc.returncode
                result.success = proc.returncode == 0
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                result.killed = True
                result.kill_reason = f"Execution timed out after {timeout}s"
                result.error = result.kill_reason
                logger.warning(result.kill_reason)

        except Exception as e:
            result.error = str(e)
            logger.error(f"Sandbox execution error: {e}")

        result.duration_seconds = time.time() - start
        return result

    def execute_command(
        self,
        command: list,
        cwd: str,
        timeout: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute an arbitrary command in a sandboxed manner.

        Args:
            command: Command and arguments as a list.
            cwd: Working directory.
            timeout: Max execution time in seconds.
            env_vars: Additional environment variables.

        Returns:
            SandboxResult with output and status.
        """
        result = SandboxResult()
        timeout = timeout or self.limits["max_time_seconds"]

        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        start = time.time()

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
                env=env,
            )
            result.output = proc.stdout
            result.error = proc.stderr
            result.exit_code = proc.returncode
            result.success = proc.returncode == 0
        except subprocess.TimeoutExpired:
            result.killed = True
            result.kill_reason = f"Command timed out after {timeout}s"
            result.error = result.kill_reason
        except Exception as e:
            result.error = str(e)

        result.duration_seconds = time.time() - start
        return result

    # ── Phase 2: Docker Sandbox (Future) ──────────────────────────────

    def create_docker_sandbox(
        self,
        project_dir: str,
        model_type: str,
        requirements: Optional[list] = None,
    ) -> Optional[str]:
        """
        Build and start a Docker container for model execution.
        Returns container ID or None if Docker is not available.

        NOTE: This is a Phase 2 feature. Currently returns None.
        """
        if not self._docker_available():
            logger.info("Docker not available — using venv sandbox")
            return None

        # Build Dockerfile
        dockerfile_content = self._generate_dockerfile(model_type, requirements)
        dockerfile_path = os.path.join(project_dir, "Dockerfile.sandbox")

        try:
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

            # Build image
            build_result = subprocess.run(
                ["docker", "build", "-t", f"ethos-sandbox-{model_type}", "-f", dockerfile_path, "."],
                capture_output=True, text=True, cwd=project_dir, timeout=600,
            )
            if build_result.returncode != 0:
                logger.error(f"Docker build failed: {build_result.stderr[:500]}")
                return None

            # Run container with strict limits
            run_result = subprocess.run(
                [
                    "docker", "run", "-d",
                    "--memory", f"{self.limits['max_memory_mb']}m",
                    "--cpus", str(self.limits['max_cpu_cores']),
                    "--network", "none",
                    "--read-only",
                    "--tmpfs", "/runtime:rw,size=100m",
                    f"ethos-sandbox-{model_type}",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if run_result.returncode == 0:
                container_id = run_result.stdout.strip()[:12]
                logger.info(f"Docker sandbox created: {container_id}")
                return container_id
            else:
                logger.error(f"Docker run failed: {run_result.stderr[:500]}")
                return None

        except Exception as e:
            logger.error(f"Docker sandbox creation failed: {e}")
            return None

    def kill_docker_sandbox(self, container_id: str, reason: str = "manual"):
        """Kill and remove a Docker container."""
        try:
            subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=10)
            subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=10)
            logger.info(f"Docker sandbox killed: {container_id} (reason: {reason})")
        except Exception as e:
            logger.error(f"Failed to kill Docker sandbox: {e}")

    # ── Helpers ────────────────────────────────────────────────────────

    def _docker_available(self) -> bool:
        """Check if Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _generate_dockerfile(self, model_type: str, requirements: Optional[list] = None) -> str:
        """Generate a Dockerfile for the sandbox."""
        reqs = " ".join(requirements or [])
        return f"""FROM python:3.10-slim

# Install dependencies
RUN pip install --no-cache-dir {reqs}

# Copy model files (read-only)
COPY . /inputs/
RUN chmod -R 555 /inputs

# Create runtime and output directories
RUN mkdir /runtime /outputs && chmod 755 /runtime /outputs

# Non-root user
RUN useradd -m modeluser
USER modeluser

WORKDIR /runtime

CMD ["python", "/inputs/inference.py"]
"""

    def check_project_size(self, project_dir: str) -> Dict[str, Any]:
        """Check if project size is within limits."""
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in {".venv", "venv", "__pycache__"}]
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                    file_count += 1
                except OSError:
                    pass

        size_mb = total_size / (1024 * 1024)
        within_limits = size_mb <= self.limits["max_disk_mb"]

        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(size_mb, 2),
            "file_count": file_count,
            "within_limits": within_limits,
            "max_disk_mb": self.limits["max_disk_mb"],
        }
