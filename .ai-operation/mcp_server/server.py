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
import json
import logging
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


# ── Initialize MCP Server ────────────────────────────────────────────────────
mcp = FastMCP("Vibe-Agent-Architect")

# --- Register Tool Categories ---
register_architect_tools(mcp, audit_fn=log_tool_call)

# Future categories (uncomment when ready):
# from tools.pipeline import register_pipeline_tools
# register_pipeline_tools(mcp, audit_fn=log_tool_call)

if __name__ == "__main__":
    mcp.run(transport="stdio")
