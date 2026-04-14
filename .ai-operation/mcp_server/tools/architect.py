"""
Architect Enforcement Tools (AI-Operation Framework)
=====================================================
MCP tools that enforce Level 4 Architect protocols.
All tool names use the `aio__` namespace prefix to avoid conflicts
with user project MCP tools.

The AI cannot bypass these tools. It MUST call them to complete the operation.
This is the "AI creates its own shackles and wears them" mechanism.

This file is the thin entry point. Tool implementations are split across:
  - save.py: aio__force_architect_save, aio__force_architect_save_confirm
  - read.py: aio__force_architect_read, aio__detail_read, aio__detail_list
  - bootstrap.py: aio__force_project_bootstrap_write
  - workflow.py: aio__force_taskspec_submit, aio__force_taskspec_approve,
                 aio__force_fast_track, aio__force_architect_report, aio__force_test_runner
  - inventory.py: aio__inventory_append, aio__inventory_consolidate
  - cleanup.py: aio__force_garbage_collection
  - audit.py: aio__audit_project_map
"""

from mcp.server.fastmcp import FastMCP
from .save import register_save_tools
from .read import register_read_tools
from .bootstrap import register_bootstrap_tools
from .workflow import register_workflow_tools
from .inventory import register_inventory_tools
from .cleanup import register_cleanup_tools
from .cognitive_gate import register_cognitive_gate_tools
from .skillify import register_skillify_tools
from .bypass import register_bypass_tools
from .audit import register_audit_tools


def register_architect_tools(mcp: FastMCP, audit_fn=None, loop_check_fn=None):
    """Register all architect enforcement tools onto the MCP server instance."""

    def _audit(tool_name: str, status: str, details: str = ""):
        """Log tool call if audit function is provided."""
        if audit_fn:
            audit_fn(tool_name, status, details)

    def _loop_guard(tool_name: str, args_str: str = "") -> str | None:
        """Check for loop and return block/warning message, or None if OK."""
        if loop_check_fn:
            return loop_check_fn(tool_name, args_str)
        return None

    register_save_tools(mcp, _audit, _loop_guard)
    register_read_tools(mcp, _audit, _loop_guard)
    register_bootstrap_tools(mcp, _audit, _loop_guard)
    register_workflow_tools(mcp, _audit, _loop_guard)
    register_inventory_tools(mcp, _audit, _loop_guard)
    register_cleanup_tools(mcp, _audit, _loop_guard)
    register_cognitive_gate_tools(mcp, _audit, _loop_guard)
    register_skillify_tools(mcp, _audit, _loop_guard)
    register_bypass_tools(mcp, _audit, _loop_guard)
    register_audit_tools(mcp, _audit, _loop_guard)
