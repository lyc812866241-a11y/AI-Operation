# Vibe-Agent-Framework: MCP Enforcement Layer

This directory contains the **Level 3 Enforcement Mechanism** of the Vibe-Agent-Framework.

## Architecture Overview

```
Level 1 (Skills)     : skills/           - Business logic scripts
Level 2 (Rules)      : .clinerules       - AI behavior rules
                       docs/project_map/ - Project memory
Level 3 (Enforcement): mcp_server/       - THIS DIRECTORY
                       .roo/mcp.json     - Roo Code MCP registration
```

## How It Works

When you issue a command like `[存档]` in Roo Code, the AI **must** call the corresponding MCP tool function instead of manually editing files. The tool function enforces:

1. All required parameters are provided
2. Files are updated surgically (no silent deletions)
3. Git commit is executed with evidence
4. The result is returned as a verifiable report

## Quick Setup

1. Install dependencies in your project's venv:
   ```bash
   source venv/bin/activate
   pip install "mcp[cli]" fastmcp
   ```

2. Configure `.roo/mcp.json` with your venv Python path:
   ```json
   {
     "mcpServers": {
       "project_architect": {
         "command": "/path/to/your/venv/bin/python3",
         "args": ["mcp_server/server.py"]
       }
     }
   }
   ```

3. In VS Code, press `Ctrl+Shift+P` → `Roo Code: Refresh MCP Servers`

## Adding New MCP Tools

Follow the 4-step protocol in `skills/mcp_protocols/MCP_CREATION_PROTOCOL.md`.

Or tell the AI in Roo Code:
> "I need a new MCP tool. Trigger: `[XXX]`. Constraint: [describe what AI keeps skipping]. Follow MCP_CREATION_PROTOCOL.md. Give me the plan first."

## Current Tools

| Tool | Trigger | Purpose |
|------|---------|---------|
| `force_architect_save` | `[存档]` | Enforce 5-file project map update + git commit |
| `force_architect_read` | `[读档]` | Force full project map context restore |
| `force_garbage_collection` | `[清理]` | Scan and delete temp/trash files with confirmation |
