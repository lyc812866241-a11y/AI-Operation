#!/bin/bash
# =============================================================================
# Dangerous Command Guard — PreToolUse Hook
# =============================================================================
# Blocks destructive Bash commands that could cause irreversible damage.
# Intercepts: rm -rf, DROP TABLE, git force-push, git reset --hard, etc.
#
# Safe exceptions: rm -rf of known build artifacts (node_modules, dist, etc.)
#
# This is a PHYSICAL ENFORCEMENT — AI cannot bypass it.
# Inspired by gstack's careful/check-careful.sh pattern, hardened for AIO.
# =============================================================================

# Read hook input
INPUT=$(cat)

# Parse JSON with Python (cross-platform, no jq dependency)
TOOL_NAME=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Only check Bash commands
if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

COMMAND=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

# No command = nothing to check
if [ -z "$COMMAND" ]; then
    exit 0
fi

# ── Safe exceptions (known build artifact cleanup) ──────────────────────
SAFE_RM_TARGETS="node_modules|dist|build|__pycache__|\.pytest_cache|\.mypy_cache|\.next|\.nuxt|\.cache|\.tox|\.egg-info|venv|\.venv|coverage|\.coverage|htmlcov|tmp|temp"

# Check if rm -rf command only targets safe directories
if echo "$COMMAND" | grep -qE "rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--force\s+--recursive|-[a-zA-Z]*f[a-zA-Z]*r)"; then
    RM_ARGS=$(echo "$COMMAND" | sed 's/rm\s\+\(-[a-zA-Z]*\s*\)*//')
    ALL_SAFE=true
    for arg in $RM_ARGS; do
        if echo "$arg" | grep -qE "^-"; then continue; fi
        BASE=$(basename "$arg" 2>/dev/null || echo "$arg")
        if ! echo "$BASE" | grep -qE "^($SAFE_RM_TARGETS)$"; then
            ALL_SAFE=false
            break
        fi
    done
    if [ "$ALL_SAFE" = true ]; then
        exit 0
    fi
fi

# ── Dangerous pattern detection ─────────────────────────────────────────
BLOCKED=""
REASON=""

# 1. Recursive force delete (non-safe targets)
if echo "$COMMAND" | grep -qE "rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--force\s+--recursive|-[a-zA-Z]*f[a-zA-Z]*r)"; then
    BLOCKED="rm -rf"
    REASON="Recursive force delete can destroy entire directories irreversibly"
fi

# 2. SQL destructive operations
if echo "$COMMAND" | grep -qiE "(DROP\s+(TABLE|DATABASE|SCHEMA))|(TRUNCATE\s+TABLE)|(DELETE\s+FROM\s+\S+\s*$)"; then
    BLOCKED="SQL destructive"
    REASON="DROP/TRUNCATE/unfiltered DELETE destroys data irreversibly"
fi

# 3. Git force push
if echo "$COMMAND" | grep -qE "git\s+push\s+.*(-f|--force)"; then
    BLOCKED="git force-push"
    REASON="Force push overwrites remote history, potentially losing others' work"
fi

# 4. Git reset --hard
if echo "$COMMAND" | grep -qE "git\s+reset\s+--hard"; then
    BLOCKED="git reset --hard"
    REASON="Hard reset discards all uncommitted changes irreversibly"
fi

# 5. Git checkout/restore that discards changes
if echo "$COMMAND" | grep -qE "git\s+(checkout|restore)\s+--?\s*\."; then
    BLOCKED="git discard all"
    REASON="Discards all uncommitted changes in working directory"
fi

# 6. Git clean -f (delete untracked files)
if echo "$COMMAND" | grep -qE "git\s+clean\s+(-[a-zA-Z]*f|-[a-zA-Z]*d[a-zA-Z]*f)"; then
    BLOCKED="git clean -f"
    REASON="Deletes untracked files permanently"
fi

# 7. Kill signals to unrelated processes
if echo "$COMMAND" | grep -qE "kill\s+-9\s+-1|killall|pkill\s"; then
    BLOCKED="mass kill"
    REASON="Killing processes broadly can crash the system"
fi

# 8. Disk format / partition operations
if echo "$COMMAND" | grep -qE "mkfs\.|fdisk|format\s+[A-Z]:|diskpart"; then
    BLOCKED="disk format"
    REASON="Disk formatting destroys all data on the target"
fi

# 9. System path delete
if echo "$COMMAND" | grep -qE "rm\s+.*(/etc/|/usr/|/var/|C:\\\\Windows|C:\\\\Program)"; then
    BLOCKED="system path delete"
    REASON="Deleting system paths can break the OS"
fi

# ── Block or allow ──────────────────────────────────────────────────────
if [ -n "$BLOCKED" ]; then
    # Log to audit
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    AUDIT_LOG=".ai-operation/audit.log"
    mkdir -p "$(dirname "$AUDIT_LOG")"
    CMD_SHORT="${COMMAND:0:150}"
    echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"DANGEROUS_BLOCKED\",\"status\":\"BLOCKED\",\"details\":\"$BLOCKED: $CMD_SHORT\"}" >> "$AUDIT_LOG"

    # Output JSON to block via hookSpecificOutput
    echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"Dangerous command blocked: $BLOCKED. $REASON. Command: ${CMD_SHORT}\"}}"
    exit 2
fi

exit 0
