# Vibe Coding Agent Framework

> An advanced Context Engineering boilerplate for AI Agents (Level 4 "Robotaxi" standard).

## What is this?

This is an abstraction of the "Project Map" / "Memory Bank" paradigm designed to elevate any code repository into a fully AI-native **Vibe Coding** workspace. By providing a structured, progressively disclosed information architecture, it prevents AI context-window pollution and "hallucination loops".

The framework enforces a **Dual-Layer Agent Architecture**:
- **Lead Agent (Architect mode)**: Analyzes intent, writes `taskSpec.md`, waits for human approval.
- **Worker Agent (Code mode)**: Executes only what the approved spec says, then saves state.

**Key feature: Second-order templates (二阶模板)**
The 5 project map files are not empty forms — they are "meta-templates" that teach AI *how to* scan any codebase and auto-generate project-specific documentation through a 5-phase bootstrap protocol.

---

## Supported IDEs

| IDE | Rule File | MCP Config | Status |
|---|---|---|---|
| **Roo Code** | `.clinerules` | `.roo/mcp.json` | Full support |
| **Cursor** | `.cursorrules` | `.cursor/mcp.json` | Full support |
| **Windsurf** | `.windsurfrules` | `.windsurf/mcp.json` | Full support |
| **Claude Code** | `CLAUDE.md` | `.mcp.json` | Full support |

All rule files are auto-generated from `.clinerules` (the canonical source) during setup.

---

## How to Deploy

### Linux / macOS / WSL

```bash
# Run this from your project root directory
bash <(curl -fsSL https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.sh)
```

### Windows (PowerShell)

```powershell
# Run this from your project root directory
irm https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.ps1 | iex
```

The script will automatically:
- Download all scaffold files into `.ai-operation/` (isolated from your project)
- Detect your Python version (3.8+ required)
- Create a virtual environment and install MCP dependencies
- Auto-configure MCP for all 4 supported IDEs
- Generate IDE-specific rule files
- Verify the MCP server starts correctly

Then reload MCP servers in your IDE:
- **Roo Code**: `Ctrl+Shift+P` → `Roo Code: Refresh MCP Servers`
- **Cursor / Windsurf**: Restart the IDE
- **Claude Code**: Auto-detects `.mcp.json`

### Initialize your project

In your first chat with the AI Agent, type:

```
[初始化项目]
```

The AI will scan your codebase, understand its structure, present a draft for your review, and populate all 5 project map files after your approval. **This only needs to be done once.**

---

## Trigger Commands

| Command | MCP Tool | What it does |
|---|---|---|
| `[初始化项目]` | `aio__force_project_bootstrap_write` | **First-time setup.** Scans codebase, calibrates with you, writes all 5 project map files. |
| `[读档]` | `aio__force_architect_read` | Forces a full read of all 5 project map files and outputs a macro state report. |
| `[汇报]` | `aio__force_architect_report` | Stops AI from coding. Forces a structured 4-section Architect report. |
| `[执行测试]` | `aio__force_test_runner` | Runs isolated module tests with auto pre-cleanup. Rejects full pipeline runs. |
| `[存档]` | `aio__force_architect_save` | Full system save: updates project map files, runs garbage collection, creates git commit. |
| `[清理]` | `aio__force_garbage_collection` | Scans for temporary/trash files, lists them, waits for your confirmation to delete. |

All 6 commands are backed by MCP enforcement tools — AI cannot bypass them.

---

## Architecture

```
Project Root (your project)
├── .ai-operation/                   ← Framework (isolated from project files)
│   ├── docs/
│   │   ├── project_map/             ← The 5 core memory files (AI's long-term memory)
│   │   │   ├── projectbrief.md      ← [STATIC]  Core vision and business goals
│   │   │   ├── systemPatterns.md    ← [STATIC]  Architecture rules and module definitions
│   │   │   ├── techContext.md       ← [STATIC]  Tech stack constraints and known gotchas
│   │   │   ├── activeContext.md     ← [DYNAMIC] Current focus and immediate next steps
│   │   │   ├── progress.md          ← [DYNAMIC] Master TODO list and completed milestones
│   │   │   └── corrections.md       ← Self-correction log (auto-evolving)
│   │   └── taskSpec_template.md     ← Template for Lead Agent's task specification
│   ├── mcp_server/                  ← MCP enforcement layer (6 tools, cannot be bypassed)
│   │   └── tools/architect.py
│   ├── skills/                      ← Framework capability modules (not your project skills)
│   │   ├── project-bootstrap/       ← 5-phase project onboarding protocol
│   │   ├── systematic-debugging/    ← Root-cause investigation protocol
│   │   ├── test-driven-development/ ← TDD enforcement protocol
│   │   └── mcp_protocols/           ← MCP tool usage protocols
│   └── venv/                        ← Python virtual environment for MCP
│
├── .clinerules                      ← AI rules (Roo Code) — canonical source
├── CLAUDE.md                        ← AI rules (Claude Code) — auto-generated
├── .cursorrules                     ← AI rules (Cursor) — auto-generated
├── .windsurfrules                   ← AI rules (Windsurf) — auto-generated
├── .roo/mcp.json                    ← MCP config (Roo Code)
├── .cursor/mcp.json                 ← MCP config (Cursor)
├── .windsurf/mcp.json               ← MCP config (Windsurf)
├── .mcp.json                        ← MCP config (Claude Code)
│
├── setup.sh                         ← Installer (Linux/macOS/WSL)
├── setup.ps1                        ← Installer (Windows PowerShell)
└── ... your project files ...
```

### Design Principles

1. **Framework isolation** — All framework files live in `.ai-operation/`, never conflicting with your project's `docs/`, `skills/`, or `src/` directories.
2. **Second-order templates** — The 5 project map files contain fill instructions + examples, not empty forms. AI auto-generates project-specific content via the bootstrap protocol.
3. **MCP enforcement** — Critical operations are enforced through MCP tools that AI cannot bypass with direct file editing or shell commands.
4. **Self-evolution** — When AI makes the same mistake 3 times during bootstrap, the lesson is automatically promoted to a mandatory scan step (with user confirmation).
5. **IDE-agnostic** — The dual-layer workflow is enforced through reply structure, not IDE-specific modes.

---

*The Plan IS the Product.*
