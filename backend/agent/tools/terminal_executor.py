"""
Terminal command execution tool for the AI agent.
Runs commands in the workspace with safety checks.
"""
import os
import subprocess
import platform
from typing import Optional

BLOCKED_COMMANDS = {
    'rm -rf /', 'rm -rf ~', 'del /f /s /q c:\\',
    'format', 'mkfs', 'dd if=', ':(){:|:&};:',
    'shutdown', 'reboot', 'halt', 'poweroff',
}

DANGEROUS_PATTERNS = [
    'rm -rf', 'del /f /s', 'rmdir /s',
    'chmod 777', 'curl | sh', 'wget | sh',
    'sudo rm', 'reg delete', 'reg add',
]


def is_dangerous(command: str) -> Optional[str]:
    """Check if a command is potentially dangerous. Returns warning message or None."""
    cmd_lower = command.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return f"BLOCKED: '{blocked}' is a destructive system command"
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return f"WARNING: Command contains dangerous pattern '{pattern}'. Requires user approval."
    return None


def run_command(workspace_root: str, command: str, timeout: int = 30) -> dict:
    """Execute a terminal command in the workspace directory."""
    danger = is_dangerous(command)
    if danger and 'BLOCKED' in danger:
        return {"success": False, "error": danger}

    try:
        is_win = platform.system() == 'Windows'
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        output = result.stdout[-5000:] if len(result.stdout) > 5000 else result.stdout
        stderr = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
        return {
            "success": result.returncode == 0,
            "command": command,
            "exit_code": result.returncode,
            "stdout": output,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s", "command": command}
    except Exception as e:
        return {"success": False, "error": str(e), "command": command}


def get_environment_info(workspace_root: str) -> dict:
    """Get information about the current environment."""
    info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "cwd": workspace_root,
    }
    # Check for common tools
    checks = {
        'node': 'node --version',
        'npm': 'npm --version',
        'python': 'python --version',
        'git': 'git --version',
        'pip': 'pip --version',
    }
    for tool, cmd in checks.items():
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5, cwd=workspace_root)
            info[tool] = r.stdout.strip() if r.returncode == 0 else 'not found'
        except Exception:
            info[tool] = 'not found'
    return {"success": True, "environment": info}
