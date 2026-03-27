# Vibe Coding Agent Framework

> An advanced Context Engineering boilerplate for AI Agents (Level 4 "Robotaxi" standard).

## What is this?

This is an abstraction of the "Project Map" / "Memory Bank" paradigm designed to elevate any code repository into a fully AI-native **Vibe Coding** workspace. By providing a structured, progressively disclosed information architecture, it prevents AI context-window pollution and "hallucination loops".

The framework enforces a **Dual-Layer Agent Architecture**:
- **Lead Agent (Architect mode)**: Analyzes intent, writes `taskSpec.md`, waits for human approval.
- **Worker Agent (Code mode)**: Executes only what the approved spec says, then saves state.

---

## How to Deploy

### One command — that's it

```bash
# Run this from your project root directory
bash <(curl -fsSL https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.sh)
```

The script will automatically:
- Download all scaffold files into your current directory
- Detect your Python version (3.8+ required)
- Create a `venv/` and install MCP dependencies
- Auto-detect the Python path and write it into `.roo/mcp.json`
- Verify the MCP server starts correctly
- Print your exact next steps

Then reload MCP servers in your IDE:
- **Roo Code**: `Ctrl+Shift+P` → `Roo Code: Refresh MCP Servers`
- **Cursor / Windsurf**: Restart the IDE

> **Rename `.clinerules` if needed:** Cursor → `.cursorrules` | Windsurf → `.windsurfrules`

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
setup.sh                 ← One-command installer (auto-configures .roo/mcp.json)
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
