#!/usr/bin/env bash
# =============================================================================
# Rule File Sync — Generates IDE-specific rule files from .clinerules
# =============================================================================
# .clinerules is the canonical source of truth.
# This script regenerates CLAUDE.md, .cursorrules, .windsurfrules from it.
#
# Usage:
#   bash .ai-operation/scripts/sync-rules.sh
#
# Automatically triggered by git pre-commit hook (see .ai-operation/hooks/)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CLINERULES="$PROJECT_ROOT/.clinerules"

if [ ! -f "$CLINERULES" ]; then
    echo "[sync-rules] ERROR: .clinerules not found at $CLINERULES"
    exit 1
fi

RULES_BODY=$(cat "$CLINERULES")

# ── Validate: trigger commands should be pointer-only (1 line each) ──────────
# Detect trigger commands that leak execution details (multi-line after "- [xxx]:")
TRIGGER_SECTION=$(sed -n '/^##.*Trigger Commands/,/^## /p' "$CLINERULES" | head -30)
LONG_TRIGGERS=$(echo "$TRIGGER_SECTION" | grep '^- \[' | awk 'length > 120 {print NR": "$0}')
if [ -n "$LONG_TRIGGERS" ]; then
    echo "[sync-rules] WARNING: Trigger commands should be short pointers, not detailed instructions."
    echo "  The following lines exceed 120 chars (likely leaking execution details):"
    echo "$LONG_TRIGGERS" | head -5
    echo "  Move details to SKILL.md or MCP tool docstring."
fi

# ── Generate CLAUDE.md ───────────────────────────────────────────────────────
cat > "$PROJECT_ROOT/CLAUDE.md" << CLAUDE_EOF
# AI-Operation Framework Rules (Claude Code)

> Auto-generated from \`.clinerules\`. Do NOT edit directly.
> To modify: edit \`.clinerules\`, then run \`bash .ai-operation/scripts/sync-rules.sh\`.

---

$RULES_BODY
CLAUDE_EOF

# ── Generate .cursorrules ────────────────────────────────────────────────────
cat > "$PROJECT_ROOT/.cursorrules" << CURSOR_EOF
// AI-Operation Framework Rules (Cursor)
// Auto-generated from .clinerules. Do NOT edit directly.
// To modify: edit .clinerules, then run: bash .ai-operation/scripts/sync-rules.sh

$RULES_BODY
CURSOR_EOF

# ── Generate .windsurfrules ──────────────────────────────────────────────────
cat > "$PROJECT_ROOT/.windsurfrules" << WINDSURF_EOF
// AI-Operation Framework Rules (Windsurf)
// Auto-generated from .clinerules. Do NOT edit directly.
// To modify: edit .clinerules, then run: bash .ai-operation/scripts/sync-rules.sh

$RULES_BODY
WINDSURF_EOF

echo "[sync-rules] Synced .clinerules → CLAUDE.md, .cursorrules, .windsurfrules"
