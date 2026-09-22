"""Where the model lives and how to serve it.

Detection and reporting only — the hub never starts a server behind your back.
It tells you the exact command instead, which is what ``ops/doctor.sh`` prints.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import config

SERVER_BINARIES = ("llama-server", "llama.cpp-server", "server", "llama_cpp.server")
MODEL_GLOB = "*.gguf"


def find_server() -> str | None:
    for name in SERVER_BINARIES:
        found = shutil.which(name)
        if found:
            return found
    return None


def model_files(models_dir: Path | None = None) -> list[Path]:
    directory = Path(models_dir or config.MODELS_DIR)
    if not directory.exists():
        return []
    return sorted(directory.rglob(MODEL_GLOB))


def catalogue() -> dict:
    """The model catalogue shipped with the hub."""
    path = config.HUB_ROOT / "offline" / "models" / "catalogue.json"
    if not path.exists():
        return {"models": [], "default": None}
    return json.loads(path.read_text())


def recommended() -> dict | None:
    """The catalogue entry the hub would run if you let it pick."""
    data = catalogue()
    models = data.get("models", [])
    if not models:
        return None
    default = data.get("default")
    for entry in models:
        if entry.get("id") == default:
            return entry
    return models[0]


def serve_command(model_path: Path | str | None = None, *, threads: int | None = None,
                  port: int | None = None) -> list[str]:
    """The argv to run — never a shell string, so it is safe to exec."""
    entry = recommended() or {}
    binary = find_server() or entry.get("serve_command") or "llama-server"
    path = str(model_path or "")
    if not path:
        found = model_files()
        path = str(found[0]) if found else str(
            Path(config.MODELS_DIR) / (entry.get("file") or "model.gguf")
        )
    context = entry.get("context", 4096)
    return [
        binary, "-m", path,
        "--port", str(port or _port_from_url(config.OFFLINE_URL)),
        "-t", str(threads or entry.get("threads", 4)),
        "-c", str(context),
    ]


def status() -> dict:
    """Everything the doctor needs to know about the brain, in one dict."""
    entry = recommended()
    files = model_files()
    return {
        "url": config.OFFLINE_URL,
        "server_binary": find_server(),
        "models_dir": str(config.MODELS_DIR),
        "models_found": [str(p) for p in files],
        "recommended": entry,
        "serve_command": serve_command(),
    }


def _port_from_url(url: str) -> int:
    tail = url.rstrip("/").split(":")[-1].split("/")[0]
    return int(tail) if tail.isdigit() else 8080
