#!/usr/bin/env bash
#
# freeze_factory.sh — Snapshot the hoolulu-factory as a stable baseline.
#
# Usage:
#   cd ~/hoolulu-factory
#   bash freeze_factory.sh           # freeze current state
#   bash freeze_factory.sh --audit   # audit first, then freeze
#   bash freeze_factory.sh --tag v1.0-stable  # custom tag
#
# What it does:
#   1. (optional) Runs a quick audit of all .py files
#   2. Initializes git if needed
#   3. Stages and commits everything
#   4. Tags the commit as the "frozen spine"
#   5. Creates a tarball backup
#

set -e

FACTORY_DIR="$(cd "$(dirname "$0")" && pwd)"
TAG="${3:-v1.0-frozen-spine}"
BACKUP_DIR="${FACTORY_DIR}/../hoolulu-factory-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  HOOLULU FACTORY FREEZER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── Audit Mode ────────────────────────────────────
if [ "$1" = "--audit" ]; then
    echo "[1/5] Auditing Python files..."
    echo ""
    ERRORS=0
    for f in "$FACTORY_DIR"/*.py; do
        RESULT=$(python3 -c "
import py_compile, sys
try:
    py_compile.compile('$f', doraise=True)
    print('✓')
except py_compile.PyCompileError as e:
    print(f'✗ {e}')
" 2>&1)
        BASENAME=$(basename "$f")
        if echo "$RESULT" | grep -q "^✓"; then
            echo "  ✓ $BASENAME"
        else
            echo "  ✗ $BASENAME — $RESULT"
            ERRORS=$((ERRORS + 1))
        fi
    done
    echo ""
    if [ $ERRORS -gt 0 ]; then
        echo "⚠ Found $ERRORS file(s) with syntax errors."
        echo "  Fix them before freezing, or run without --audit to skip."
        read -p "Continue anyway? (y/N) " -r
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    else
        echo "✓ All Python files compile cleanly."
    fi
    echo ""
fi

# ─── Git Init ──────────────────────────────────────
echo "[2/5] Setting up git..."
if [ ! -d "$FACTORY_DIR/.git" ]; then
    git init "$FACTORY_DIR"
    echo "  Initialized new git repo."
else
    echo "  Git repo exists."
fi

cd "$FACTORY_DIR"

# Create .gitignore if missing
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'GITIGNORE'
__pycache__/
*.pyc
*.pyo
data/
logs/
*.log
*.save
.DS_Store
.env
venv/
.venv/
GITIGNORE
    echo "  Created .gitignore"
fi

# ─── Stage & Commit ────────────────────────────────
echo ""
echo "[3/5] Staging files..."
git add -A
STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
echo "  $STAGED files staged."

echo ""
echo "[4/5] Committing..."
git commit -m "freeze: hoolulu-factory frozen spine ($TIMESTAMP)

  This commit marks the stable baseline.
  Do NOT modify files on this spine.
  Build forward from here.

  Tag: $TAG
  Date: $(date)
  Audit: $([ "$1" = "--audit" ] && echo "passed" || echo "skipped")
" --allow-empty 2>/dev/null || echo "  (nothing new to commit)"

# ─── Tag ──────────────────────────────────────────
echo ""
echo "[5/5] Tagging as frozen spine..."
if git tag | grep -q "^${TAG}$"; then
    echo "  Tag '$TAG' exists. Creating timestamped variant..."
    TAG="${TAG}-${TIMESTAMP}"
fi
git tag -a "$TAG" -m "Frozen spine baseline — do not modify. Build forward from here."
echo "  Tagged: $TAG"

# ─── Backup ───────────────────────────────────────
echo ""
echo "Creating tarball backup..."
mkdir -p "$BACKUP_DIR"
TARBALL="$BACKUP_DIR/hoolulu-factory_${TIMESTAMP}.tar.gz"
tar -czf "$TARBALL" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='logs' \
    --exclude='data' \
    -C "$(dirname "$FACTORY_DIR")" "$(basename "$FACTORY_DIR")" 2>/dev/null
echo "  Backup: $TARBALL"

# ─── Summary ──────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ FACTORY FROZEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Tag:     $TAG"
echo "  Commit:  $(git rev-parse --short HEAD)"
echo "  Backup:  $TARBALL"
echo ""
echo "  To restore this baseline:"
echo "    git checkout $TAG"
echo ""
echo "  To list frozen states:"
echo "    git tag -l"
echo ""
