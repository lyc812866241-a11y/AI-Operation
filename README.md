# AI-Operation

**AI Agent 行为治理框架 — 不是提示词模板，是物理强制层。**

Most AI coding frameworks tell the AI what to do. AI-Operation makes it **physically impossible** to skip the process.

---

## The Problem

AI coding agents follow text rules ~85% of the time. The other 15%:

- **Skip planning** — write code without a plan, debug for 10x longer
- **Lose context** — forget everything when the session resets
- **Repeat mistakes** — hit the same bug three times because nothing was recorded
- **Claim completion** — say "done" without verification

Every existing framework addresses this with markdown instructions: "you MUST read all files", "you SHOULD write tests first". The AI reads these instructions... and sometimes ignores them.

**AI-Operation's approach: if the AI didn't read the context, the tools don't work.**

---

## How It Works: Three Enforcement Layers

```
┌─────────────────────────────────────────────┐
│  Layer 1: Cognitive Gate (PreToolUse Hook)   │  ← AI must prove it read context
│  SESSION_KEY token + 30-op counter           │     before Edit/Write/Bash work
├─────────────────────────────────────────────┤
│  Layer 2: MCP Tool Enforcement (19 tools)   │  ← Hard-coded validation in Python
│  save, read, taskSpec, bypass, skillify     │     rejects empty/vague/invalid input
├─────────────────────────────────────────────┤
│  Layer 3: Git Pre-Commit Hook (3 gates)     │  ← Physical block at commit time
│  rule sync / map protection / taskSpec gate  │     cannot commit without approval
└─────────────────────────────────────────────┘
```

### Layer 1: Cognitive Gate — "Read before you write"

A `PreToolUse` hook physically blocks `Edit`, `Write`, and `Bash` until the AI:

1. Reads `corrections.md` (project lessons/experience)
2. Extracts the `SESSION_KEY` from the file
3. Calls `aio__confirm_read(session_key=...)` to prove it

Without this, **every file operation is rejected**. Not by a prompt — by a shell script returning `exit 2`.

After 30 operations, the counter expires and the AI must re-read. This prevents context drift in long sessions.

> No other open-source framework enforces context loading at the tool level. Cline Memory Bank says "MUST read ALL files" — but it's a text instruction the AI can skip. AI-Operation makes skipping impossible.

### Layer 2: MCP Tools — "The AI creates its own shackles"

19 MCP tools with hard-coded Python validation. The AI **must** call these tools to complete operations — and the tools reject invalid input.

| Command | Tool | What It Enforces |
|---|---|---|
| `[存档]` | `aio__force_architect_save` → `_confirm` | **Two-phase save**: validate all 6 file params + lessons → generate diff preview + self-audit checklist → AI reviews → then commits. Empty lessons rejected. Vague updates rejected. |
| `[读档]` | `aio__force_architect_read` | 50KB budget management, TOC fallback, orphan reference lint, skill registry, cleanup reminders |
| Feature dev | `aio__force_taskspec_submit` → `_approve` | 6-field plan required before coding. `dry_run` mode shows PASS/FAIL/BYPASSABLE per rule. User must approve. |
| Trivial fix | `aio__force_fast_track` | Dynamic threshold based on trust score (LOW: <3 lines, NORMAL: <5, HIGH: <10) |
| `[初始化项目]` | `aio__force_project_bootstrap_write` | 5-phase codebase scan → draft → user confirm → write. 3 gates (confirmed / no TODOs / dir exists) |
| Bypass | `aio__bypass_violation` | Single-use bypass with audit trail. 24h rate limit per rule. User must say "bypass/绕过". |
| Monitor | `aio__rule_monitor` | Toggle rules between observe (log-only) and enforce mode. Safe rule rollout. |
| Skill extraction | `aio__extract_skill` | Analyze audit.log → auto-generate SKILL.md from workflow patterns |

**Supporting mechanisms:**
- **Audit log**: Every MCP call recorded as JSON to `audit.log`
- **Loop detection**: Same tool + same args 3x in 5 min → warning. 5x → blocked. Args normalized before hashing.
- **Auto-reflection**: If AI was blocked/rejected during the session, it cannot write "NONE" for lessons — must reflect on what happened
- **Re-entrancy guard**: Only one save at a time. 30-min TTL auto-clears if process crashes.

### Layer 3: Git Pre-Commit Hook — "No commit without approval"

Three gates, checked on every `git commit`:

| Gate | Trigger | Effect |
|---|---|---|
| Rule Sync | `.clinerules` modified | Auto-syncs to `CLAUDE.md`, `.cursorrules`, `.windsurfrules` |
| Map Protection | `project_map/` files edited directly | **Blocked**. Must use MCP tools (`aio__force_architect_save`) |
| TaskSpec Gate | Code files modified without approval | **Blocked**. Must submit taskSpec → get user approval → then commit |

Exempt: `.ai-operation/`, `.claude/`, tests, docs, config files. Emergency bypass: `git commit --no-verify`.

### Bonus Layer: Dangerous Command Guard

A separate `PreToolUse` hook blocks destructive Bash commands before execution:

- `rm -rf` (except known build artifacts: `node_modules`, `dist`, `__pycache__`, etc.)
- `git push --force`, `git reset --hard`, `git clean -f`
- `DROP TABLE`, `TRUNCATE`, unfiltered `DELETE FROM`
- `kill -9 -1`, `killall`, `mkfs`, `fdisk`

All blocks logged to `audit.log`. AI cannot bypass — it's a shell-level gate.

---

## 8-File Project Memory (Project Map)

AI reads these files at session start to restore full project context:

| File | Content | Type | Special Behavior |
|---|---|---|---|
| `activeContext.md` | Current focus, what just happened, next step | Dynamic | Must include file paths. Min 200 chars. |
| `progress.md` | Completed tasks with files touched | Dynamic | Min 150 chars per save. |
| `corrections.md` | Experience index (keys only) | Dynamic | Keys → lazy-load values via `aio__load_experience` |
| `conventions.md` | Naming, API, code style contracts | Static | Always loaded in full. Proactive prevention. |
| `systemPatterns.md` | Architecture, modules, data flow | Static | Orphan reference lint on read. Section-aware merge on save. |
| `techContext.md` | Tech stack, known pitfalls | Static | — |
| `projectbrief.md` | Core vision, business objectives | Static | — |
| `inventory.md` | Asset registry (modules, APIs, skills) | Static | Full overwrite on save. Real-time append via `aio__inventory_append`. |

**Key-value experience system**: `corrections.md` stores only category keys (e.g., `fileops`, `git`, `save`). Actual lessons live in `corrections/fileops.md`, `corrections/git.md`, etc. AI calls `aio__load_experience("fileops")` to load relevant experience on demand — minimizing context consumption while ensuring lessons are available when needed.

**Freshness tracking**: Experience files older than 30 days are marked `⚠ STALE`. Cleanup reminders trigger when `activeContext.md` hasn't been updated in 7+ days.

**Budget management**: Total read budget is 50KB (~12K tokens). Dynamic files always loaded in full. Static files fall back to TOC mode when budget is tight. `aio__detail_read` loads full content on demand.

---

## Two-Phase Save Protocol

The save is the most important operation in the framework. It's deliberately split into two phases to force AI self-review:

```
Phase 1: aio__force_architect_save
  ├── Validate all 6 file parameters (reject if vague/empty)
  ├── Check NO_CHANGE_BECAUSE justification for skipped files
  ├── Cross-validate against git diff (warn if claimed changes ≠ actual changes)
  ├── Scan audit.log for session violations (force reflection if blocked)
  ├── Generate diff preview
  ├── Generate self-audit checklist (10 questions)
  └── Return PENDING_REVIEW (nothing written yet)

Phase 2: aio__force_architect_save_confirm
  ├── Read staging file
  ├── Apply updates (section-aware merge for static files, append for dynamic)
  ├── Write lessons to corrections key-value system
  ├── Auto-split oversized sections to details/
  ├── Regenerate SESSION_KEY (forces next session to re-read)
  ├── Git commit (non-blocking, Windows-safe)
  └── Return SUCCESS
```

The AI must answer the self-audit checklist between Phase 1 and Phase 2. If any answer is "no", it must call Phase 1 again with corrections.

---

## Bypass Framework

Not all rules should be hard blocks. The framework supports four enforcement states:

| State | Behavior | Example |
|---|---|---|
| `REJECTED` | Hard block. Must fix. | Empty `activeContext_update` |
| `BYPASSABLE` | Block with escape hatch. User can authorize bypass. | Vague file paths in taskSpec |
| `MONITOR` | Log violation but don't block. Observation mode for new rules. | New rule being tested |
| `SUCCESS` | Passed all checks. | — |

Bypass flow: tool returns `BYPASSABLE` → user says "bypass" → AI calls `aio__bypass_violation(rule_code, user_said)` → single-use flag created → next submit skips that rule → flag consumed.

**Safeguards**: 24-hour rate limit per rule. Bypass signals validated ("bypass", "绕过", "skip", etc.). All bypasses logged with reason and timestamp.

---

## 5 Skills (Structured Protocols)

| Skill | Trigger | What It Does |
|---|---|---|
| `project-bootstrap` | `[初始化项目]` | 5-phase codebase scan → fill project_map. No assumptions — every claim traced to actual files. |
| `systematic-debugging` | Bug / error / test failure | Root cause investigation BEFORE any fix. 4 phases: investigate → analyze → hypothesize → implement. |
| `test-driven-development` | New feature / fix | RED-GREEN-REFACTOR. No production code without a failing test first. |
| `omm-scan` | `[架构扫描]` | Generate Mermaid architecture diagrams. 12 perspective catalog. Recursive drill-down. |
| `consolidate` | `[整理]` | Human-in-the-loop project_map cleanup. Review each file with user. Stratify to details/. |

All skills have YAML frontmatter for auto-discovery by `_discover_skills()`. Skills are shown in `[读档]` output with their trigger conditions.

---

## Quick Start

### Install

**Linux / macOS / WSL:**
```bash
cd your-project
bash <(curl -fsSL https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.sh)
```

**Windows PowerShell:**
```powershell
cd your-project
irm https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.ps1 | iex
```

Setup auto-detects Python, downloads the framework, creates venv, installs MCP dependencies, configures 4 IDEs, installs Git hooks, and verifies the MCP server starts.

Then open your IDE and say:
```
[初始化项目]
```

The AI scans your codebase, drafts project documentation, asks you to confirm, and writes the project map. From then on, every session starts with full context and every save captures lessons.

### Update

```bash
# Linux / macOS
bash setup.sh --update

# Windows
.\setup.ps1 -Update
```

Updates framework code only. Preserves venv, project_map, audit.log, and all local state.

---

## Supported IDEs

| IDE | Rules File | MCP Config | Auto-Sync |
|---|---|---|---|
| Claude Code | `CLAUDE.md` | `.mcp.json` | Yes |
| Cursor | `.cursorrules` | `.cursor/mcp.json` | Yes |
| Windsurf | `.windsurfrules` | `.windsurf/mcp.json` | Yes |
| Roo Code | `.clinerules` | `.roo/mcp.json` | Yes |

Edit `.clinerules` once, pre-commit hook syncs the rest.

---

## Directory Structure

```
your-project/
├── .ai-operation/                    # Framework (isolated from your code)
│   ├── docs/project_map/             # 8-file memory system
│   ├── docs/corrections/             # Key-value experience files
│   ├── mcp_server/                   # 19 MCP tools + audit + loop detection
│   │   ├── server.py                 # Entry point (audit logger, loop detector)
│   │   └── tools/                    # 9 modules (save, read, workflow, bypass, ...)
│   ├── skills/                       # 5 skill protocols
│   ├── hooks/                        # Git pre-commit (3 gates)
│   ├── scripts/                      # Rule sync, hook install
│   ├── cli/                          # Terminal tools + Web Dashboard
│   └── audit.log                     # Tamper-evident operation log
├── .claude/hooks/                    # Claude Code hooks
│   ├── check-dangerous.sh            # Blocks rm -rf, git push --force, etc.
│   ├── require-context.sh            # Cognitive Gate (blocks until context read)
│   └── governance-capture.sh         # Audit all Edit/Write/Bash operations
├── .clinerules                       # Rules (canonical source)
├── CLAUDE.md / .cursorrules / ...    # Auto-generated per IDE
└── tests/                            # 21 framework tests
```

Framework files don't invade your project directory. No conflicts with `src/`, `docs/`, or anything else.

---

## Competitive Landscape

| Layer | AI-Operation | Cline Memory Bank | everything-claude-code | Microsoft Agent Governance |
|---|---|---|---|---|
| **What it is** | Cognitive governance | Project memory | Harness optimizer | Enterprise policy engine |
| **Enforcement** | Code-enforced (Hook + MCP + Git) | Text instruction only | Hook-based audit | OPA/Rego policies |
| **Memory** | 8 files + key-value experience | 6 files | CLAUDE.md | N/A |
| **Cognitive gate** | Yes (SESSION_KEY + counter) | No | No | No |
| **Two-phase save** | Yes | No | No | No |
| **Bypass framework** | Yes (4 states + rate limit) | No | No | Yes (different scope) |
| **Target** | Developer workflow | Developer workflow | Performance tuning | Enterprise compliance |

### What's unique to AI-Operation

1. **Cognitive Gate** — PreToolUse hook that physically blocks tools until AI proves it read project context via SESSION_KEY token. No other open-source framework does this.
2. **Two-phase save** — forced self-review with diff preview and 10-question audit checklist before any write.
3. **Key-value experience with lazy loading** — corrections index + on-demand detail loading. Minimizes context consumption.
4. **Bypass framework** — structured rule override with 4 states (REJECTED/BYPASSABLE/MONITOR/SUCCESS), single-use flags, 24h rate limit, full audit trail.
5. **30-operation counter** — forces AI to re-read context during long sessions, preventing drift.

### What others do better

- **Letta Code**: Git-versioned memory with merge conflict resolution
- **claude-mem** (46K stars): Vector-based semantic search over past experience
- **Claude Code Auto Dream**: Automated memory consolidation (AI-Operation's `[整理]` is manual)
- **Microsoft AGT**: Declarative policy language (OPA/Rego) vs. hard-coded Python rules

---

## Testing & CI

```bash
python -m pytest tests/ -v
```

21 tests covering: save parameter validation, taskSpec workflow lifecycle, trust scoring, bootstrap merge, audit logging.

CI matrix: Python 3.9 / 3.11 / 3.12 × Ubuntu / Windows (6 combinations), runs on every push.

---

## Philosophy

> "Text rules are suggestions. Physical gates are law."

AI-Operation doesn't try to make AI smarter. It makes the **process** smarter — so that even when AI makes mistakes, the framework catches them before they reach the codebase.

The AI creates its own shackles and wears them.

---

## License

MIT

---

*The Plan IS the Product.*
