#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Stop Amanda. Safe to run when nothing is running.
# ---------------------------------------------------------------------------
set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HUB_ROOT/.." && pwd)"
STATE_DIR="${HOOLULU_STATE:-$REPO_ROOT/data/hub}"
PID_FILE="$STATE_DIR/amanda.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Amanda is not running (no pid file)"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "→ stopping Amanda (pid $PID)"
  kill "$PID"
  for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$PID" 2>/dev/null; then
    echo "  still alive — sending SIGKILL"
    kill -9 "$PID"
  fi
  echo "  stopped"
else
  echo "Amanda is not running (stale pid file)"
fi
rm -f "$PID_FILE"
