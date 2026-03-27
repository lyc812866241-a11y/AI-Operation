# Vibe-Agent-Framework: MCP Enforcement Layer

This directory contains the **Level 3 Enforcement Mechanism** of the Vibe-Agent-Framework.

## Architecture Overview

```
Level 1 (Skills)     : skills/           - AI capability modules and protocols
Level 2 (Rules)      : .clinerules       - AI behavior rules
                       docs/project_map/ - Project memory (5 core files)
Level 3 (Enforcement): mcp_server/       - THIS DIRECTORY
                       .roo/mcp.json     - Roo Code MCP registration
```

## How It Works

When you issue a trigger command like `[存档]` in Roo Code, the AI **must** call the corresponding MCP tool function instead of manually editing files. The tool function enforces:

1. All required parameters are provided and validated
2. Files are updated with verified content (no silent deletions or skipped steps)
3. Git commit is executed with evidence
4. The result is returned as a verifiable `SUCCESS` / `FAILED` / `REJECTED` report

The AI cannot bypass these tools. This is the "AI creates its own shackles" mechanism.

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

## Current Tools

| Tool | Trigger | Purpose | Protocol |
|---|---|---|---|
| `force_architect_save` | `[存档]` | Enforce 5-file project map update + git commit | `SAVE_PROTOCOL.md` |
| `force_architect_read` | `[读档]` | Force full project map context restore | `SAVE_PROTOCOL.md` |
| `force_garbage_collection` | `[清理]` | Scan and delete temp/trash files with confirmation | `SAVE_PROTOCOL.md` |
| `force_project_bootstrap_write` | `[初始化项目]` | Write all 5 project map files after user calibration (one-time setup) | `BOOTSTRAP_PROTOCOL.md` |

## Adding New MCP Tools

Follow the 4-step protocol in `skills/mcp_protocols/MCP_CREATION_PROTOCOL.md`.

Or tell the AI in Roo Code:
> "I need a new MCP tool. Trigger: `[XXX]`. Constraint: [describe what AI keeps skipping]. Follow MCP_CREATION_PROTOCOL.md. Give me the plan first."
