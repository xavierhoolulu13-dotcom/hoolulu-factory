#!/usr/bin/env bash
# Start Hoolulu Offline. Defaults are fine for local use.
#
#   ./run.sh                          # http://localhost:8080
#   PORT=3000 ./run.sh                # different port
#   ./run.sh --token my-secret        # require a sync token (use this off localhost)
#
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"
PY="$(command -v python3 || command -v python)"

exec "$PY" server.py --port "$PORT" --host "$HOST" "$@"
