"""Central configuration for the Hoolulu Agent.

Every path is resolved relative to the repository root so the agent behaves
identically whether it is launched from the repo, from ``~/hoolulu-factory``,
or from a checkout somewhere else. ``HOOLULU_ROOT`` overrides everything.
"""

import os

# agent/config.py -> agent/ -> repository root
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
)

FACTORY_ROOT = os.path.abspath(
    os.environ.get("HOOLULU_ROOT", os.path.expanduser("~/hoolulu-factory"))
)

# The legacy scripts hard-code ~/hoolulu-factory/data/hoolulu.db. Keep the
# agent pointed at the same database when that location is the checkout, and
# otherwise fall back to a database inside the repo.
_legacy_db = os.path.join(FACTORY_ROOT, "data", "hoolulu.db")
_repo_db = os.path.join(REPO_ROOT, "data", "hoolulu.db")

if os.path.abspath(FACTORY_ROOT) == REPO_ROOT or os.path.exists(FACTORY_ROOT):
    DB_PATH = os.environ.get("HOOLULU_DB", _legacy_db)
else:
    DB_PATH = os.environ.get("HOOLULU_DB", _repo_db)

DB_PATH = os.path.abspath(DB_PATH)

DATA_DIR = os.path.abspath(os.path.dirname(DB_PATH))
LOG_DIR = os.path.abspath(os.path.join(FACTORY_ROOT, "logs"))
SYSTEM_LOG = os.path.join(LOG_DIR, "system.log")
AUDIT_LOG = os.path.join(LOG_DIR, "agent_audit.log")
MEMORY_PATH = os.path.join(DATA_DIR, "memory", "history.json")

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(AGENT_DIR, "templates")
STATIC_DIR = os.path.join(AGENT_DIR, "static")

HOST = os.environ.get("HOOLULU_HOST", "0.0.0.0")
PORT = int(os.environ.get("HOOLULU_PORT", "8000"))

# --- LLM settings -----------------------------------------------------------
# The agent always works without a key (LocalBrain). A key upgrades reasoning
# quality. Nothing is ever written to disk from here.
LLM_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
LLM_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("HOOLULU_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = float(os.environ.get("HOOLULU_LLM_TIMEOUT", "45"))

# --- Safety rails -----------------------------------------------------------
COMMAND_TIMEOUT = int(os.environ.get("HOOLULU_CMD_TIMEOUT", "30"))
MAX_READ_BYTES = 400_000
MAX_WRITE_BYTES = 400_000

# Directories the agent may never write into.
FORBIDDEN_DIRS = (".git", ".venv", "node_modules", "__pycache__", "data")


def ensure_dirs():
    """Create the factory folder skeleton the legacy scripts expect."""
    created = []
    for folder in (
        "core",
        "agents",
        "skills",
        "config",
        "data",
        "tasks",
        "logs",
        "backups",
    ):
        path = os.path.join(FACTORY_ROOT, folder)
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            created.append(folder)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    return created
