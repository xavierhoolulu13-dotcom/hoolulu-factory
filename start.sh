#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Hoolulu Factory Agent — one click launcher.
#
#   ./start.sh            start the agent on port 8000
#   ./start.sh --demo     wipe pipeline data, load demo leads, then start
#   ./start.sh --port 9000
#
# Creates .venv on first run. Nothing here needs sudo.
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
VENV="$ROOT/.venv"
PORT="${HOOLULU_PORT:-8000}"
DEMO=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --demo) DEMO=1; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 1; }

# --- virtualenv ------------------------------------------------------------
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "→ creating virtualenv in .venv"
  "$PYTHON" -m venv "$VENV"
fi

PY="$VENV/bin/python"
if ! "$PY" -c "import flask" >/dev/null 2>&1; then
  echo "→ installing dependencies (flask)"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r "$ROOT/requirements.txt"
fi

# --- factory bootstrap -----------------------------------------------------
"$PY" - <<'PY'
from agent import factory
info = factory.init_db()
print(f"→ database ready: {info['db']} ({len(info['tables'])} tables)")
PY

if [[ "$DEMO" == "1" ]]; then
  "$PY" - <<'PY'
from agent import factory
factory.reset_demo(confirm=True)
print("→ demo data:", factory.seed_demo(6)["created"], "leads loaded")
PY
fi

export HOOLULU_PORT="$PORT"
export PYTHONUNBUFFERED=1

echo
echo "  Hoolulu Factory Agent"
echo "  → http://0.0.0.0:${PORT}"
echo "  → press Ctrl+C to stop"
echo
exec "$PY" -m agent.server
