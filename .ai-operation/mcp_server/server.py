"""
Vibe-Agent-Framework: MCP Server Root Entry Point
===================================================
This is the single entry point for all MCP tools in this project.

Architecture:
  - server.py         : Starts the MCP server, registers tools, runs audit layer.
  - tools/architect.py: Level 4 Architect enforcement tools.
  - audit.log         : Every tool call is logged with timestamp, tool name, status.

To add a new MCP tool:
  Follow the protocol in `.ai-operation/skills/mcp_protocols/MCP_CREATION_PROTOCOL.md`
"""

import datetime
import hashlib
import json
import logging
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from tools.architect import register_architect_tools

# ── Audit Logger ─────────────────────────────────────────────────────────────
# Every MCP tool call is logged to .ai-operation/audit.log for traceability.
# This provides a tamper-evident record of all AI actions through MCP tools.

AUDIT_LOG_PATH = Path(".ai-operation/audit.log")

audit_logger = logging.getLogger("aio_audit")
audit_logger.setLevel(logging.INFO)

try:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _handler = logging.FileHandler(str(AUDIT_LOG_PATH), encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(_handler)
except Exception:
    pass  # Audit logging is best-effort, don't block startup


def log_tool_call(tool_name: str, status: str, details: str = ""):
    """Log a tool invocation to audit.log."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "ts": timestamp,
            "tool": tool_name,
            "status": status,
        }
        if details:
            entry["details"] = details[:200]
        audit_logger.info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        pass  # Never let audit logging break the tool


# ── Loop Detection ──────────────────────────────────────────────────────────
# Tracks recent tool calls to detect AI stuck in a loop.
# Same tool + similar args within WINDOW seconds:
#   >= WARN_THRESHOLD  → tool executes but returns warning
#   >= BLOCK_THRESHOLD → tool is REJECTED, forces AI to change approach

LOOP_WINDOW_SECONDS = 300  # 5 minutes
LOOP_WARN_THRESHOLD = 3
LOOP_BLOCK_THRESHOLD = 5

_call_history: list[tuple[str, str, float]] = []  # (tool_name, args_hash, timestamp)


def _check_loop(tool_name: str, args_str: str) -> str | None:
    """Check if this tool call is part of a loop. Returns warning/error message or None."""
    now = time.time()
    args_hash = hashlib.md5(args_str.encode("utf-8")).hexdigest()[:8]

    # Prune old entries outside window
    cutoff = now - LOOP_WINDOW_SECONDS
    _call_history[:] = [(t, h, ts) for t, h, ts in _call_history if ts > cutoff]

    # Count recent identical calls
    repeat_count = sum(1 for t, h, _ in _call_history if t == tool_name and h == args_hash)

    # Record this call
    _call_history.append((tool_name, args_hash, now))

    if repeat_count >= LOOP_BLOCK_THRESHOLD:
        return (
            f"BLOCKED: Loop detected — {tool_name} called {repeat_count + 1} times "
            f"with same/similar args in {LOOP_WINDOW_SECONDS}s.\n"
            f"You are stuck in a loop. STOP and change your approach.\n"
            f"Try: read the error message, check your assumptions, ask the user."
        )
    elif repeat_count >= LOOP_WARN_THRESHOLD:
        return (
            f"⚠️ WARNING: {tool_name} called {repeat_count + 1} times with same/similar args "
            f"in {LOOP_WINDOW_SECONDS}s. You may be in a loop. "
            f"Consider changing approach before you get blocked."
        )
    return None


# ── Initialize MCP Server ────────────────────────────────────────────────────
mcp = FastMCP("Vibe-Agent-Architect")

# --- Register Tool Categories ---
register_architect_tools(mcp, audit_fn=log_tool_call, loop_check_fn=_check_loop)

# Future categories (uncomment when ready):
# from tools.pipeline import register_pipeline_tools
# register_pipeline_tools(mcp, audit_fn=log_tool_call)

if __name__ == "__main__":
    mcp.run(transport="stdio")
