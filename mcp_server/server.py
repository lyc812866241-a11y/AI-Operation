"""
Vibe-Agent-Framework: MCP Server Root Entry Point
===================================================
This is the single entry point for all MCP tools in this project.

Architecture:
  - server.py         : Starts the MCP server and registers all tool categories.
  - tools/architect.py: Level 4 Architect enforcement tools (save, read, clean).
  - tools/pipeline.py : (Future) Pipeline execution enforcement tools.

To add a new MCP tool:
  Follow the protocol in `skills/mcp_protocols/MCP_CREATION_PROTOCOL.md`
"""

from mcp.server.fastmcp import FastMCP
from tools.architect import register_architect_tools

# Initialize the root MCP Server
mcp = FastMCP("Vibe-Agent-Architect")

# --- Register Tool Categories ---
# Each category is a separate file in tools/
# To add a new category: create tools/your_category.py and register it here.
register_architect_tools(mcp)

# Future categories (uncomment when ready):
# from tools.pipeline import register_pipeline_tools
# register_pipeline_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio")
