#!/bin/bash
# =============================================================================
# Governance Capture — PostToolUse Hook
# =============================================================================
# Records all Edit/Write/Bash operations to audit.log.
# Does NOT block anything — observe and record only.
#
# This captures what MCP audit.log misses: direct file modifications
# that bypass the MCP tool chain.
# =============================================================================

AUDIT_LOG=".ai-operation/audit.log"

# Read hook input
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Only capture file-modifying operations
case "$TOOL_NAME" in
    Edit|Write|Bash|NotebookEdit)
        ;;
    *)
        exit 0
        ;;
esac

# Extract relevant details
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
FILE_PATH=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin).get('tool_input',{}); print(d.get('file_path','') or d.get('command',''))" 2>/dev/null)

# Truncate long commands
if [ ${#FILE_PATH} -gt 200 ]; then
    FILE_PATH="${FILE_PATH:0:200}..."
fi

# Append to audit log (create dir if needed)
mkdir -p "$(dirname "$AUDIT_LOG")"
echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\",\"status\":\"EXECUTED\",\"details\":\"$FILE_PATH\"}" >> "$AUDIT_LOG"

exit 0
