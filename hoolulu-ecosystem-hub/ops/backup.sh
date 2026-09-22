#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Back up everything the factory made and everything it remembers.
#
#   ./ops/backup.sh                   timestamped tar.gz in backups/
#   ./ops/backup.sh --out /mnt/usb    write somewhere else
#
# What is included: the database and approvals (data/hub), the builds, the
# deployments, the packages, and the loop log. Source code lives in git — this
# is the state that does not.
# ---------------------------------------------------------------------------
set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$HUB_ROOT/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR:-$REPO_ROOT/backups}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --out=*) OUT="${1#*=}"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$OUT"
ARCHIVE="$OUT/hoolulu-factory-$STAMP.tar.gz"

# Build the file list from what exists, so a fresh install still backs up.
INCLUDES=()
for path in data/hub builds deployed packages \
            "$HUB_ROOT/core/event-log/loops/events.jsonl"; do
  [[ -e "$REPO_ROOT/$path" || -e "$path" ]] && INCLUDES+=("$path")
done

if [[ ${#INCLUDES[@]} -eq 0 ]]; then
  echo "nothing to back up yet"
  exit 0
fi

cd "$REPO_ROOT"
tar -czf "$ARCHIVE" "${INCLUDES[@]}"
SIZE="$(du -h "$ARCHIVE" | cut -f1)"
echo "✓ backed up ${#INCLUDES[@]} path(s) → $ARCHIVE ($SIZE)"
