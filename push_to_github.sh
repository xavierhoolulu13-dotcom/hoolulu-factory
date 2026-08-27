#!/usr/bin/env bash
#
# push_to_github.sh — Create a GitHub repo and push the hoolulu-factory
#
# Usage:
#   cd ~/hoolulu-factory
#   bash push_to_github.sh                # creates private repo, pushes everything
#   bash push_to_github.sh --public       # creates public repo instead
#   bash push_to_github.sh --name my-repo  # custom repo name
#

set -e

REPO_NAME="hoolulu-factory"
VISIBILITY="private"
FACTORY_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --public)   VISIBILITY="public"; shift ;;
        --name)     REPO_NAME="$2"; shift 2 ;;
        *)          REPO_NAME="$1"; shift ;;
    esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  HOOLULU FACTORY → GITHUB"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Repo:     $REPO_NAME"
echo "  Visibility: $VISIBILITY"
echo "  Directory: $FACTORY_DIR"
echo ""

# ─── Check gh CLI ──────────────────────────────────
echo "[1/6] Checking GitHub CLI..."
if ! command -v gh &> /dev/null; then
    echo "✗ GitHub CLI (gh) not found."
    echo "  Install:  https://cli.github.com/"
    echo "  Then run: gh auth login"
    exit 1
fi

# Check auth
if ! gh auth status &> /dev/null; then
    echo "  Not authenticated. Starting login..."
    gh auth login
fi

USERNAME=$(gh api user --jq .login 2>/dev/null || echo "")
if [ -z "$USERNAME" ]; then
    echo "✗ Could not get GitHub username. Run 'gh auth login' first."
    exit 1
fi
echo "  ✓ Authenticated as @$USERNAME"

# ─── Git init ──────────────────────────────────────
echo ""
echo "[2/6] Setting up git..."
cd "$FACTORY_DIR"

if [ ! -d ".git" ]; then
    git init
    echo "  Initialized git repo."
else
    echo "  Git repo already exists."
fi

# ─── .gitignore ──────────────────────────────────
echo ""
echo "[3/6] Creating .gitignore..."
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
*.egg-info/
dist/
build/
venv/
.venv/

# Data & logs
data/
logs/
*.log
*.save

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Backups
*.tar.gz
*.bak
EOF
    echo "  Created .gitignore"
else
    echo "  .gitignore already exists."
fi

# ─── Stage & Commit ────────────────────────────────
echo ""
echo "[4/6] Staging and committing..."
git add -A
STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
echo "  $STAGED files staged."

if [ $STAGED -gt 0 ]; then
    git commit -m "feat: hoolulu-factory with coding agent + agent forge

  - Core factory modules (orchestrator, queues, memory, views)
  - CodingAgent — autonomous code generation, editing, and execution
  - AgentForge — meta agent builder (generates new specialized agents)
  - Coding queue, memory, view, and state machine modules
  - Freeze script for stable baseline snapshots
  - Web dashboard

  Authored by @$USERNAME
" 2>/dev/null || echo "  (already committed, nothing new)"
else
    echo "  (nothing to commit)"
fi

# ─── Create GitHub Repo ───────────────────────────
echo ""
echo "[5/6] Creating GitHub repo..."
FULL_NAME="$USERNAME/$REPO_NAME"

# Check if repo already exists
if gh repo view "$FULL_NAME" &> /dev/null 2>&1; then
    echo "  Repo $FULL_NAME already exists — will push to it."
else
    echo "  Creating $VISIBILITY repo: $FULL_NAME"
    if [ "$VISIBILITY" = "public" ]; then
        gh repo create "$REPO_NAME" --public --source=. --remote=origin --description "Hoolulu Factory — autonomous business automation with coding agent + meta agent forge"
    else
        gh repo create "$REPO_NAME" --private --source=. --remote=origin --description "Hoolulu Factory — autonomous business automation with coding agent + meta agent forge"
    fi
    echo "  ✓ Created: https://github.com/$FULL_NAME"
fi

# ─── Push ─────────────────────────────────────────
echo ""
echo "[6/6] Pushing to GitHub..."

# Set remote if not set
if ! git remote get-url origin &> /dev/null 2>&1; then
    git remote add origin "https://github.com/$FULL_NAME.git"
fi

# Get current branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
if [ "$BRANCH" = "" ]; then
    git checkout -b main 2>/dev/null || true
    BRANCH="main"
fi

git push -u origin "$BRANCH" 2>&1 | sed 's/^/  /'

# ─── Summary ──────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ PUSHED TO GITHUB"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Repo: https://github.com/$FULL_NAME"
echo "  Branch: $BRANCH"
echo "  Files: $STAGED"
echo ""
echo "  To clone elsewhere:"
echo "    gh repo clone $FULL_NAME"
echo ""
