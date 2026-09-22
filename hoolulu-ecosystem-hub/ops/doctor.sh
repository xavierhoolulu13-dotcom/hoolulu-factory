#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Doctor: is the factory whole?
#
#   ./ops/doctor.sh          run every check
#   ./ops/doctor.sh --fix    also re-run the scaffolder to create missing paths
# ---------------------------------------------------------------------------
set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HUB_ROOT/.." && pwd)"
FIX=0
[[ "${1:-}" == "--fix" ]] && FIX=1

PY="$REPO_ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="$(command -v python3)"

export HOOLULU_ROOT="$REPO_ROOT"
export HOOLULU_HUB="$HUB_ROOT"

if [[ "$FIX" == "1" ]]; then
  echo "→ checking the hub tree"
  "$HUB_ROOT/ops/scaffold.sh"
  echo
fi

cd "$REPO_ROOT"
set +e
"$PY" -m amanda doctor
STATUS=$?
set -e

echo
if [[ -f "$HUB_ROOT/core/event-log/loops/events.jsonl" ]]; then
  echo "loop log    : $(wc -l <"$HUB_ROOT/core/event-log/loops/events.jsonl") events"
else
  echo "loop log    : empty (no runs yet)"
fi
exit $STATUS
