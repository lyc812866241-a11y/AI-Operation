# Vibe Coding Agent Framework

> An advanced Context Engineering boilerplate for AI Agents (Level 4 "Robotaxi" standard).

## What is this?

This is an abstraction of the "Project Map" / "Memory Bank" paradigm designed to elevate any code repository into a fully AI-native **Vibe Coding** workspace. By providing a structured, progressively disclosed information architecture, it prevents AI context-window pollution and "hallucination loops".

The framework enforces a **Dual-Layer Agent Architecture**:
- **Lead Agent (Architect mode)**: Analyzes intent, writes `taskSpec.md`, waits for human approval.
- **Worker Agent (Code mode)**: Executes only what the approved spec says, then saves state.

---

## How to Deploy

### Step 1 — Copy scaffold into your project

```bash
cp -r .clinerules .roo docs/project_map docs/taskSpec_template.md mcp_server skills /your/project/root/
```

Rename `.clinerules` based on your IDE:
- Roo Code → `.clinerules`
- Cursor → `.cursorrules`
- Windsurf → `.windsurfrules`

### Step 2 — Set up the MCP enforcement layer

```bash
cd /your/project
python -m venv venv
source venv/bin/activate
pip install "mcp[cli]" fastmcp
```

Edit `.roo/mcp.json` and replace the placeholder with your actual Python path:
```json
{
  "mcpServers": {
    "project_architect": {
      "command": "/your/project/venv/bin/python3",
      "args": ["mcp_server/server.py"]
    }
  }
}
```

In VS Code: `Ctrl+Shift+P` → `Roo Code: Refresh MCP Servers`

### Step 3 — Initialize your project

In your first chat with the AI Agent, type:

```
[初始化项目]
```

The AI will scan your codebase, understand its structure, present a draft for your review, and populate all 5 project map files after your approval. **This only needs to be done once.**

---

## Trigger Commands

| Command | What it does |
|---|---|
| `[初始化项目]` | **First-time setup.** Scans codebase, calibrates with you, writes all 5 project map files via MCP enforcement. |
| `[读档]` | Forces a full read of all 5 project map files and outputs a macro state report. |
| `[汇报]` | Stops AI from coding. Forces a high-level Architect report: files modified, why, architecture impact, next steps. |
| `[执行测试]` | Runs isolated module tests. Pre-cleans dirty data and leftover artifacts from previous failed runs. |
| `[存档]` | Full system save: updates project map files, runs garbage collection, creates git commit. |
| `[清理]` | Scans for temporary/trash scripts and files, lists them, waits for your confirmation to delete. |

---

## Architecture

```
.clinerules              ← AI behavior rules (Dual-Layer Workflow, Iron Laws, trigger routing)
docs/
  project_map/           ← The 5 core memory files (AI's long-term memory)
    projectbrief.md      ← [STATIC]  Core vision and business goals
    systemPatterns.md    ← [STATIC]  Architecture rules and module definitions
    techContext.md       ← [STATIC]  Tech stack constraints and known gotchas
    activeContext.md     ← [DYNAMIC] Current focus and immediate next steps
    progress.md          ← [DYNAMIC] Master TODO list and completed milestones
  taskSpec_template.md   ← Template for Lead Agent's task specification
mcp_server/              ← MCP enforcement layer (cannot be bypassed by AI)
  tools/architect.py     ← 4 enforcement tools
skills/                  ← AI capability modules
  project-bootstrap/     ← First-time project onboarding (5-phase protocol)
  systematic-debugging/  ← Root-cause investigation protocol
  test-driven-development/ ← TDD enforcement protocol
  mcp_protocols/         ← MCP tool usage protocols and index
```

---

*The Plan IS the Product.*
