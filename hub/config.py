"""Every path and setting the hub knows about.

Resolution order for anything configurable: environment variable, then the
sensible default. With no environment at all the hub still runs — offline,
deterministic, and inside the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- roots -----------------------------------------------------------------
REPO_ROOT = Path(os.environ.get("HOOLULU_ROOT", Path(__file__).resolve().parents[1]))
HUB_ROOT = Path(os.environ.get("HOOLULU_HUB", REPO_ROOT / "hoolulu-ecosystem-hub"))

SWARM_FILE = Path(os.environ.get("HOOLULU_SWARM", REPO_ROOT / "agents" / "factory.yaml"))
DEPLOYMENTS_FILE = Path(
    os.environ.get("HOOLULU_DEPLOYMENTS", HUB_ROOT / "deployments.yaml")
)
CONTRACTS_DIR = HUB_ROOT / "core" / "contracts"
EVENT_LOG = HUB_ROOT / "core" / "event-log" / "loops" / "events.jsonl"
EVIDENCE_DIR = HUB_ROOT / "commercial-reasoning" / "evidence" / "schemas"
TEMPLATES_DIR = HUB_ROOT / "factory" / "templates"

# --- working state (all gitignored) ----------------------------------------
BUILD_ROOT = Path(os.environ.get("HOOLULU_BUILDS", REPO_ROOT / "builds"))
DEPLOY_ROOT = Path(os.environ.get("HOOLULU_DEPLOYED", REPO_ROOT / "deployed"))
PACKAGE_ROOT = Path(os.environ.get("HOOLULU_PACKAGES", REPO_ROOT / "packages"))
STATE_DIR = Path(os.environ.get("HOOLULU_STATE", REPO_ROOT / "data" / "hub"))
APPROVALS_FILE = STATE_DIR / "approvals.jsonl"
DEPLOYMENTS_DB = STATE_DIR / "deployments.json"

# --- offline brain ---------------------------------------------------------
OFFLINE_URL = os.environ.get("HOOLULU_OFFLINE_URL", "http://localhost:8080/v1")
OFFLINE_MODEL = os.environ.get("HOOLULU_OFFLINE_MODEL", "local")
OFFLINE_TIMEOUT = float(os.environ.get("HOOLULU_OFFLINE_TIMEOUT", "20"))
MODELS_DIR = Path(
    os.environ.get(
        "HOOLULU_MODELS_DIR",
        Path.home() / "models",
    )
)

# --- operator interface ----------------------------------------------------
PORT = int(os.environ.get("HOOLULU_PORT", "8010"))
HOST = os.environ.get("HOOLULU_HOST", "0.0.0.0")
PUBLIC_URL = os.environ.get("HOOLULU_PUBLIC_URL", f"http://localhost:{PORT}").rstrip("/")

# --- guardrails ------------------------------------------------------------
TIER = os.environ.get("HOOLULU_TIER", "development").strip().lower()
OPERATOR = os.environ.get("HOOLULU_OPERATOR", "operator")

# --- skills ----------------------------------------------------------------
SKILLS_DIR = Path(
    os.environ.get("HOOLULU_SKILLS_DIR", Path.home() / ".markus" / "skills")
).expanduser()

# --- optional network adapters (all off unless configured) -----------------
SEARXNG_URL = os.environ.get("SEARXNG_URL", "").rstrip("/")
FIRECRAWL_URL = os.environ.get("FIRECRAWL_URL", "").rstrip("/")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

def runtime_dirs() -> tuple:
    """The writable directories, resolved now (not at import) so that HOOLULU_*
    overrides and tests take effect."""
    return (BUILD_ROOT, DEPLOY_ROOT, PACKAGE_ROOT, STATE_DIR)


def ensure_dirs() -> None:
    """Create every working directory. Safe to call on every command."""
    for path in runtime_dirs():
        path.mkdir(parents=True, exist_ok=True)
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)


def rel(path: Path | str) -> str:
    """Repo-relative path for display, so output never leaks absolute paths."""
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve()))
    except (ValueError, OSError):
        return str(path)


def public_url(slug: str) -> str:
    """The URL a deployed product is served at.

    Left relative when ``HOOLULU_PUBLIC_URL`` is empty, which is what you want
    behind a proxy with an unknown external host: the link then works from
    whatever origin the console is being viewed on.
    """
    return f"{PUBLIC_URL}/p/{slug}/" if PUBLIC_URL else f"/p/{slug}/"
