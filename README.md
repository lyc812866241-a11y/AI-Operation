# AI-Operation

**AI agent behavior governance framework. Not another prompt template — a physical enforcement layer.**

Most AI coding frameworks tell the AI what to do. AI-Operation makes it **physically impossible** to skip the process.

---

## The Problem

You give an AI agent a set of rules. It follows them 85% of the time. The other 15%:
- It writes code without a plan, then you spend hours debugging the wrong implementation
- It "forgets" what you were working on after the conversation resets
- It makes the same mistake three times because it has no memory of being corrected
- It claims it's done without actually verifying anything

Text rules are suggestions. AI-Operation turns them into gates.

## How It Works

**Three enforcement layers, each harder to bypass than the last:**

```
Layer 1: Rules (.clinerules / CLAUDE.md)
  AI reads rules on startup. Each rule has a WHY explanation
  so the AI understands the reasoning, not just the command.
  Compliance: ~90%

Layer 2: MCP Tools (9 tools with hard-coded validation)
  AI must call these tools to save state, submit plans, run tests.
  Tools reject invalid inputs — empty fields, missing approvals,
  skipped steps. AI cannot talk its way past code.
  Compliance: 100% (once the tool is called)

Layer 3: Git Hooks (physical blocking)
  Three pre-commit gates:
  Gate 1: Auto-sync rule files across 4 IDEs
  Gate 2: Block direct edits to project memory files
  Gate 3: Block code commits without an approved plan
  Compliance: 95% (only --no-verify bypasses, which rules forbid)
```

## What Makes This Different

| Feature | Most frameworks | AI-Operation |
|---|---|---|
| "Write a plan first" | Text rule (ignorable) | **Git hook blocks commit without approved plan** |
| "Save your progress" | Text rule (ignorable) | **MCP tool rejects if you don't reflect on lessons learned** |
| "Don't edit memory files directly" | Not enforced | **Git hook physically blocks the commit** |
| "Follow the same rules across IDEs" | Manual copy-paste | **Auto-synced on every commit** |
| "Learn from mistakes" | Doesn't exist | **Correction log → auto-upgrade to permanent checks after 3 repeats** |
| "Don't skip steps on small changes" | Fixed threshold | **Dynamic trust score adjusts threshold based on error history** |

## Quick Start

### Linux / macOS / WSL
```bash
cd your-project
bash <(curl -fsSL https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.sh)
```

### Windows PowerShell
```powershell
cd your-project
irm https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.ps1 | iex
```

Then open your IDE and type:
```
[初始化项目]
```

The AI scans your codebase, drafts a project profile, asks you to verify, and writes it. From that point on, every session starts with context and every save captures lessons.

### Updating an Existing Installation

```powershell
# Windows
.\setup.ps1 -Update
```
```bash
# Linux / macOS
bash setup.sh --update
```

Updates framework code (MCP tools, scripts, skills, hooks, rules) while **preserving** your project data (venv, project_map, audit.log, MCP configs).

## Supported IDEs

| IDE | Rule File | MCP Config | Auto-Synced |
|---|---|---|---|
| Roo Code | `.clinerules` | `.roo/mcp.json` | Yes |
| Cursor | `.cursorrules` | `.cursor/mcp.json` | Yes |
| Windsurf | `.windsurfrules` | `.windsurf/mcp.json` | Yes |
| Claude Code | `CLAUDE.md` | `.mcp.json` | Yes |

Edit `.clinerules` once. The pre-commit hook syncs the other three automatically.

## The 9 MCP Enforcement Tools

| Command | Tool | What It Enforces |
|---|---|---|
| `[初始化项目]` | `aio__force_project_bootstrap_write` | Merges into templates (not overwrite). 3 gates: user confirmed, no placeholders, directory exists |
| `[存档]` | `aio__force_architect_save` | Rejects empty active context, progress, **and lessons learned**. Clears approval flag after save |
| `[读档]` | `aio__force_architect_read` | 4KB/file, 12KB total budget. Auto-discovers sub-directory rules. Warns at 70% budget |
| `[汇报]` | `aio__force_architect_report` | All 4 report sections mandatory. No free-form reports |
| `[执行测试]` | `aio__force_test_runner` | Auto pre-cleanup. Rejects full-pipeline commands. 5-minute timeout |
| `[清理]` | `aio__force_garbage_collection` | Two-step: list first, delete only after user confirms |
| *Phase 1* | `aio__force_taskspec_submit` | Writes plan to file. Clears previous approval. 6 sections required |
| *Approval* | `aio__force_taskspec_approve` | Validates approval signal. Creates flag for git hook. Checks spec is PENDING |
| *Fast-track* | `aio__force_fast_track` | Dynamic threshold: 3/5/10 lines based on trust score from correction history |

## Self-Evolution: The Framework Gets Smarter

```
Session 1: AI makes a mistake → you correct it → saved to corrections.md (COUNT: 1)
Session 2: Same mistake → COUNT: 2, AI is reminded before scanning
Session 3: Same mistake → COUNT: 3 → LESSON auto-promoted to permanent check in SKILL.md
Session 4+: AI will never make this mistake again — it's hardcoded into the protocol
```

This works because `[存档]` **forces** the AI to fill `lessons_learned`. The MCP tool rejects empty values. No reflection, no save.

## Architecture

```
your-project/
├── .ai-operation/                    # Framework (isolated from your code)
│   ├── docs/project_map/             # 5-file memory bank (AI's long-term memory)
│   ├── mcp_server/                   # 9 enforcement tools + audit logger
│   ├── skills/                       # Bootstrap, debugging, TDD protocols
│   ├── hooks/                        # 3-gate pre-commit hook
│   ├── scripts/                      # Rule sync, hook installer
│   ├── cli/                          # Terminal tool + web dashboard
│   └── rules.d/                      # Sub-directory rules (for monorepos)
├── .clinerules                       # Rules (canonical source)
├── CLAUDE.md / .cursorrules / ...    # Auto-generated per IDE
└── tests/                            # 19 framework tests
```

**Framework files never touch your project directories.** No conflicts with your `src/`, `docs/`, `skills/`, or anything else.

## Dashboard & CLI

```bash
# Quick status
python .ai-operation/cli/ai_op.py status

# Read all project memory
python .ai-operation/cli/ai_op.py read

# Web dashboard (http://localhost:8420)
python .ai-operation/cli/dashboard.py
```

## Audit Trail

Every MCP tool call is logged to `.ai-operation/audit.log`:
```json
{"ts": "2026-04-01 14:30:22", "tool": "aio__force_architect_save", "status": "SUCCESS", "details": "files=activeContext.md,progress.md"}
{"ts": "2026-04-01 14:30:25", "tool": "aio__force_taskspec_approve", "status": "CALLED", "details": "批准"}
```

## Testing

```bash
python -m pytest tests/ -v
```

19 tests covering: parameter validation, taskSpec workflow lifecycle, trust scoring, bootstrap merge logic, audit logging.

CI runs on every push: Python 3.9/3.11/3.12 on Ubuntu + Windows.

## License

MIT

---

*The Plan IS the Product.*
