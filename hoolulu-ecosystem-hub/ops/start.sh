#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Start Amanda — the operator interface and the product host.
#
#   ./ops/start.sh                 start on $HOOLULU_PORT (default 8010)
#   ./ops/start.sh --port 9000     start on another port
#   ./ops/start.sh --foreground    stay attached (Ctrl+C stops it)
#
# Idempotent: refuses to start a second copy while one is already running.
# ---------------------------------------------------------------------------
set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HUB_ROOT/.." && pwd)"
PORT="${HOOLULU_PORT:-8010}"
FOREGROUND=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --port=*) PORT="${1#*=}"; shift ;;
    --foreground|-f) FOREGROUND=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

PY="$REPO_ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

STATE_DIR="${HOOLULU_STATE:-$REPO_ROOT/data/hub}"
PID_FILE="$STATE_DIR/amanda.pid"
LOG_FILE="$STATE_DIR/amanda.log"
mkdir -p "$STATE_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Amanda is already running (pid $(cat "$PID_FILE")) on port $PORT"
  echo "  console : http://localhost:${PORT}/"
  exit 0
fi

export HOOLULU_ROOT="$REPO_ROOT"
export HOOLULU_HUB="$HUB_ROOT"
export HOOLULU_PORT="$PORT"
export PYTHONUNBUFFERED=1

echo "→ starting Amanda on port $PORT"
if [[ "$FOREGROUND" == "1" ]]; then
  exec "$PY" -m amanda serve --port "$PORT"
fi

cd "$REPO_ROOT"
nohup "$PY" -m amanda serve --port "$PORT" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 2

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "  console  : http://localhost:${PORT}/"
  echo "  products : http://localhost:${PORT}/p/"
  echo "  log      : $LOG_FILE"
  echo "  pid      : $(cat "$PID_FILE")"
else
  echo "✗ failed to start — tail $LOG_FILE" >&2
  exit 1
fi
