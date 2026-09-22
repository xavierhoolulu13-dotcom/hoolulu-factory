"""Running generated code without handing it a shell.

An argument list, a timeout, a working directory inside the repo, and the
interpreter itself — never ``shell=True``, never a string the code can inject
into. Used for Python products and for the smoke tests QA runs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .. import config

DEFAULT_TIMEOUT = 30


class SandboxViolation(RuntimeError):
    """Raised before a subprocess is ever launched."""


def inside_repo(path: Path | str) -> Path:
    """Resolve ``path`` and prove it is inside the repository root."""
    resolved = Path(path).resolve()
    root = config.REPO_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise SandboxViolation(f"{resolved} is outside {root}")
    return resolved


def run_python(script: Path | str, *args: str, timeout: int = DEFAULT_TIMEOUT,
               cwd: Path | str | None = None) -> dict:
    """Run one Python file inside the repo. Returns a result dict, never raises."""
    script = inside_repo(script)
    if script.suffix != ".py":
        raise SandboxViolation("only .py files can be run through the sandbox")
    workdir = inside_repo(cwd or script.parent)
    argv = [sys.executable, "-I", str(script), *args]
    try:
        done = subprocess.run(argv, cwd=str(workdir), capture_output=True, text=True,
                              timeout=timeout, env=_env())
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "timed_out": True,
                "stdout": "", "stderr": f"timed out after {timeout}s", "argv": argv}
    except OSError as exc:
        return {"ok": False, "exit_code": None, "timed_out": False,
                "stdout": "", "stderr": str(exc), "argv": argv}
    return {
        "ok": done.returncode == 0,
        "exit_code": done.returncode,
        "timed_out": False,
        "stdout": (done.stdout or "")[:8000],
        "stderr": (done.stderr or "")[:8000],
        "argv": argv,
    }


def _env() -> dict:
    import os

    env = {k: v for k, v in os.environ.items() if k.startswith(("HOOLULU_", "PATH", "HOME"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env
