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

# Always allow MCP tools (including aio__confirm_read)
if echo "$TOOL_NAME" | grep -q "^mcp__\|^aio__"; then
    exit 0
fi

# Check if session has been confirmed
if [ ! -f "$FLAG_FILE" ]; then
    echo "BLOCKED: Context not loaded. Read corrections.md and call aio__confirm_read(session_key=...) first." >&2
    exit 2
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
