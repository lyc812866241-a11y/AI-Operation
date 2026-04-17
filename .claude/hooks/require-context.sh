#!/bin/bash
# =============================================================================
# Cognitive Gate — PreToolUse Hook
# =============================================================================
# Blocks Edit/Write/Bash until AI confirms reading project context.
# After 30 file operations, flag expires and AI must re-confirm.
#
# This is a PHYSICAL ENFORCEMENT — AI cannot bypass it.
# =============================================================================

FLAG_FILE=".ai-operation/.session_confirmed"
MAX_OPS=30

# Read hook input
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Always allow read-only tools (AI needs these to read corrections.md)
case "$TOOL_NAME" in
    Read|Glob|Grep|WebSearch|WebFetch)
        exit 0
        ;;
esac

# Always allow MCP tools (including aio__confirm_read + aio__force_architect_save)
if echo "$TOOL_NAME" | grep -q "^mcp__\|^aio__"; then
    exit 0
fi

# ── Project map lockdown ─────────────────────────────────────────────
# Block Edit/Write/NotebookEdit that targets .ai-operation/docs/project_map/*.
# These files are AI long-term memory and must only be mutated through the
# MCP save protocol (aio__force_architect_save) -- direct Edit/Write bypasses
# the self-audit, diff preview, and program-level verification that give the
# save its integrity.
case "$TOOL_NAME" in
    Edit|Write|NotebookEdit|MultiEdit)
        TARGET_PATH=$(echo "$INPUT" | python -c "
import sys, json
data = json.load(sys.stdin).get('tool_input', {})
print(data.get('file_path') or data.get('notebook_path') or '')
" 2>/dev/null)
        # Normalize Windows backslashes to forward slashes for match
        NORM_PATH=$(echo "$TARGET_PATH" | tr '\\\\' '/')
        if echo "$NORM_PATH" | grep -qE "(^|/)\.ai-operation/docs/project_map/"; then
            TS=$(date '+%Y-%m-%d %H:%M:%S')
            AUDIT_LOG=".ai-operation/audit.log"
            mkdir -p "$(dirname "$AUDIT_LOG")"
            SHORT="${NORM_PATH:0:200}"
            echo "{\"ts\":\"$TS\",\"tool\":\"PROJECT_MAP_LOCKDOWN\",\"status\":\"BLOCKED\",\"details\":\"$TOOL_NAME on $SHORT\"}" >> "$AUDIT_LOG" 2>/dev/null
            echo "BLOCKED: project_map files must be updated through MCP tools." >&2
            echo "Use aio__force_architect_save (or aio__force_project_bootstrap_write for init)." >&2
            echo "Direct $TOOL_NAME on $NORM_PATH bypasses diff preview + self-audit + program verification." >&2
            exit 2
        fi
        ;;
esac

# Bootstrap exception: if corrections.md has no SESSION_KEY, the cognitive gate
# hasn't been initialized yet (fresh install or manual upgrade). Allow operations
# so [初始化项目] or [存档] can run and set up the key. Once SESSION_KEY exists,
# the gate is fully enforced.
CORRECTIONS=".ai-operation/docs/project_map/corrections.md"
if [ -f "$CORRECTIONS" ] && grep -q "SESSION_KEY:" "$CORRECTIONS"; then
    # Gate is initialized — enforce it
    if [ ! -f "$FLAG_FILE" ]; then
        echo "BLOCKED: Context not loaded. Read corrections.md and call aio__confirm_read(session_key=...) first." >&2
        exit 2
    fi
else
    # Gate not initialized — allow operations (bootstrap mode)
    exit 0
fi

# Check operation counter
COUNTER=$(cat "$FLAG_FILE" 2>/dev/null || echo "0")
if [ "$COUNTER" -ge "$MAX_OPS" ] 2>/dev/null; then
    echo "BLOCKED: 30 file operations reached. Re-read corrections.md and call aio__confirm_read again." >&2
    exit 2
fi

# Increment counter for Edit/Write/Bash operations
case "$TOOL_NAME" in
    Edit|Write|Bash|NotebookEdit)
        NEW_COUNTER=$((COUNTER + 1))
        echo "$NEW_COUNTER" > "$FLAG_FILE"
        ;;
esac

exit 0
