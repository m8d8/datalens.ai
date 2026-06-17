"""
Shared helpers for license-based CLI AI providers (cursor-agent, gh copilot, claude).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Sequence


def find_executable(*names: str) -> str | None:
    """Return the first executable found on PATH or common install locations."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    home_local = os.path.expanduser("~/.local/bin")
    for name in names:
        candidate = os.path.join(home_local, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def run_cli_prompt(
    cmd: Sequence[str],
    *,
    timeout: int = 180,
    cwd: str | None = None,
) -> tuple[bool, str, str]:
    """
    Run a CLI command and return (success, stdout, stderr).
    """
    try:
        result = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=os.environ.copy(),
        )
        ok = result.returncode == 0
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if not ok and not out:
            return False, "", err or f"exit code {result.returncode}"
        return ok, out, err
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return False, "", "Command not found"
    except OSError as e:
        return False, "", str(e)


def cli_status_ok(cmd: Sequence[str], *, timeout: int = 15) -> bool:
    """Return True if a status/login check command succeeds."""
    ok, out, _ = run_cli_prompt(cmd, timeout=timeout)
    if not ok:
        return False
    lowered = out.lower()
    return "logged in" in lowered or "✓" in out or "authenticated" in lowered or bool(out)
