#!/usr/bin/env bash
# =============================================================================
# Install git hooks for AI-Operation Framework
# =============================================================================
# Links the framework's pre-commit hook into .git/hooks/
# Safe to run multiple times — overwrites existing hook.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_SRC="$SCRIPT_DIR/../hooks/pre-commit"
HOOK_DST="$PROJECT_ROOT/.git/hooks/pre-commit"

if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "[install-hooks] ERROR: Not a git repository. Run this from your project root."
    exit 1
fi

if [ ! -f "$HOOK_SRC" ]; then
    echo "[install-hooks] ERROR: Hook source not found at $HOOK_SRC"
    exit 1
fi

mkdir -p "$PROJECT_ROOT/.git/hooks"
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "[install-hooks] Pre-commit hook installed at $HOOK_DST"
echo "  - Auto-syncs rule files when .clinerules changes"
echo "  - Blocks direct edits to project_map (must use MCP tools)"
