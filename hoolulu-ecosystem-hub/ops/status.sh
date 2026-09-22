#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Factory status: the doctor's checks, what is deployed, what is waiting on a
# human, and whether the console is up.
# ---------------------------------------------------------------------------
set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HUB_ROOT/.." && pwd)"
PORT="${HOOLULU_PORT:-8010}"
PY="$REPO_ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

export HOOLULU_ROOT="$REPO_ROOT"
export HOOLULU_HUB="$HUB_ROOT"

cd "$REPO_ROOT"
"$PY" -m amanda status
echo

STATE_DIR="${HOOLULU_STATE:-$REPO_ROOT/data/hub}"
PID_FILE="$STATE_DIR/amanda.pid"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "console     : UP (pid $(cat "$PID_FILE")) at http://localhost:${PORT}/"
else
  echo "console     : down (start it with ops/start.sh)"
fi
