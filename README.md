# AI-Operation

**AI Agent Governance Framework — not prompt templates, physical enforcement.**

Most AI coding frameworks tell the AI what to do. AI-Operation makes it **physically impossible** to skip the process.

---

## The Problem

AI coding agents follow text rules ~85% of the time. The other 15%:

- **Skip planning** — write code without a plan, debug for 10x longer
- **Lose context** — forget everything when the session resets
- **Repeat mistakes** — hit the same bug three times because nothing was recorded
- **Claim completion** — say "done" without verification
- **Fabricate claims** — say "all 42 tools present" when the actual count is 38

Every existing framework addresses this with markdown instructions: "you MUST read all files", "you SHOULD write tests first". The AI reads these instructions... and sometimes ignores them.

**AI-Operation's approach: if the AI didn't read the context, the tools don't work. If the AI claims something about the codebase, code verifies it.**

---

## Architecture: Four Enforcement Layers

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Cognitive Gate (PreToolUse Hook)       │  ← AI must prove it read context
│  SESSION_KEY token + 30-op counter               │     before Edit/Write/Bash work
├─────────────────────────────────────────────────┤
│  Layer 2: MCP Tool Enforcement (21 tools)       │  ← Hard-coded validation in Python
│  save, read, scan, audit, taskSpec, bypass      │     rejects empty/vague/invalid input
├─────────────────────────────────────────────────┤
│  Layer 3: Programmatic Verification             │  ← Code verifies AI claims
│  scan_codebase + audit_project_map              │     AI cannot self-validate
├─────────────────────────────────────────────────┤
│  Layer 4: Git Pre-Commit Hook (3 gates)         │  ← Physical block at commit time
│  rule sync / map protection / taskSpec gate      │     cannot commit without approval
└─────────────────────────────────────────────────┘
```

### Layer 1: Cognitive Gate — "Read before you write"

A `PreToolUse` hook physically blocks `Edit`, `Write`, and `Bash` until the AI:

1. Reads `corrections.md` (project lessons/experience)
2. Extracts the `SESSION_KEY` from the file
3. Calls `aio__confirm_read(session_key=...)` to prove it

Without this, **every file operation is rejected**. Not by a prompt — by a shell script returning `exit 2`.

After 30 operations, the counter expires and the AI must re-read. This prevents context drift in long sessions.

**Bootstrap exception**: If `corrections.md` has no `SESSION_KEY` yet (fresh install or upgrade), the gate allows operations so initialization can proceed. Once the first save writes a SESSION_KEY, the gate is fully enforced.

### Layer 2: MCP Tools — "The AI creates its own shackles"

21 MCP tools with hard-coded Python validation. The AI **must** call these tools to complete operations — and the tools reject invalid input.

| Command | Tool | What It Enforces |
|---|---|---|
| `[save]` | `aio__force_architect_save` | Two-phase save: validate → diff preview → self-audit → confirm. |
| `[read]` | `aio__force_architect_read` | 50KB budget management, TOC fallback, orphan reference lint. |
| Feature dev | `aio__force_taskspec_submit` | 6-field plan required before coding. User must approve. |
| Trivial fix | `aio__force_fast_track` | Dynamic threshold based on trust score. |
| `[init]` | `aio__force_project_bootstrap_write` | 3 gates: confirmed / no TODOs / dir exists. |
| Scan | `aio__scan_codebase` | Walk file tree, extract all signatures, classify roles. |
| Audit | `aio__audit_project_map` | 5 programmatic checks against actual code. |
| Bypass | `aio__bypass_violation` | Single-use bypass with 24h rate limit + audit trail. |
| Monitor | `aio__rule_monitor` | Toggle rules between observe and enforce mode. |
| Skill extraction | `aio__extract_skill` | Auto-generate SKILL.md from audit.log workflow patterns. |

### Layer 3: Programmatic Verification — "Code says, not AI"

This layer solves the fundamental audit problem: **AI both produces and validates its own claims**.

**`aio__scan_codebase`** — Replaces manual code scanning with a single tool call:

```
Input:  project_root + scope (e.g. "src/", "agent_core/")
Process:
  - Walk entire file tree (skip .git/node_modules/venv/__pycache__)
  - Read every code file, extract class/def/import/decorator signatures
  - Classify each file: entry point / module / config / test
  - Group by directory, sort by importance
Output: Structured summary with 100% file coverage, 0 skipped
```

The output goes directly into `systemPatterns.md` as the module inventory. AI adds system qualification and data flow on top, but **cannot hand-write the file list** (hand-writing causes omissions).

Supports Python, JavaScript, TypeScript, Go, Rust, Java. No external dependencies (no repomix/npx needed).

**`aio__audit_project_map`** — 5 automated checks that verify AI claims against actual code:

| Check | What it verifies | FAIL threshold |
|---|---|---|
| File Existence | Paths in systemPatterns/inventory → `os.path.exists` | >10% missing |
| Decorator Count | Actual `@decorator` count in code vs inventory claim | Difference > 2 |
| Dependency Truth | Claimed libraries → `grep` actual imports | Claimed but no import |
| Naming Consistency | conventions.md rules → sample-check code | <70% compliance |
| Config Parsing | .env vars / docker-compose ports vs techContext | Conflicts found |

Integrated into bootstrap as **Phase 3.5**: must pass audit before writing to project_map.

### Layer 4: Git Pre-Commit Hook — "No commit without approval"

| Gate | Trigger | Effect |
|---|---|---|
| Rule Sync | `.clinerules` modified | Auto-syncs to `CLAUDE.md`, `.cursorrules`, `.windsurfrules` |
| Map Protection | `project_map/` files edited directly | **Blocked**. Must use MCP tools. |
| TaskSpec Gate | Code files modified without approval | **Blocked**. Must submit taskSpec first. |

### Bonus: Dangerous Command Guard

A separate `PreToolUse` hook blocks destructive Bash commands:

- `rm -rf` (except known build artifacts)
- `git push --force`, `git reset --hard`, `git clean -f`
- `DROP TABLE`, `TRUNCATE`, unfiltered `DELETE FROM`

---

## 8-File Project Memory

AI reads these at session start to restore full project context:

| File | Content | Type |
|---|---|---|
| `activeContext.md` | Current focus + what just happened + next step | Dynamic |
| `progress.md` | Completed tasks with files touched | Dynamic |
| `corrections.md` | Experience index (keys only) | Dynamic |
| `conventions.md` | Naming, API, code style contracts | Static |
| `systemPatterns.md` | Architecture, modules, data flow | Static |
| `techContext.md` | Tech stack, known pitfalls | Static |
| `inventory.md` | Asset registry (modules, APIs, skills) | Static |

**Key-value experience system**: `corrections.md` stores only category keys (e.g., `fileops`, `git`, `save`). Actual lessons live in `corrections/fileops.md`. AI calls `aio__load_experience("fileops")` on demand — minimizing context consumption.

**Budget management**: Total read budget is 50KB (~12K tokens). Static files fall back to TOC mode when budget is tight.

---

## Two-Phase Save Protocol

```
Phase 1: aio__force_architect_save
  ├── Validate all 6 file parameters
  ├── Cross-validate against git diff
  ├── Scan audit.log for session violations
  ├── Generate diff preview + 10-question self-audit
  └── Return PENDING_REVIEW (nothing written yet)

Phase 2: aio__force_architect_save_confirm
  ├── Section-aware merge (static) / append (dynamic)
  ├── Auto-split oversized sections to details/
  ├── Write lessons to key-value system
  ├── Regenerate SESSION_KEY
  └── Git commit
```

---

## Bootstrap: From Zero to Full Context

```
Phase 1:  aio__scan_codebase     → structured file inventory (one tool call)
Phase 2:  Entry trace + schema    → data flow + data structures
Phase 2+: System qualification    → type / purpose / version
Phase 3:  Draft + user calibrate  → confirm with user
Phase 3.5: aio__audit_project_map → 5 programmatic checks (PASS required)
Phase 4:  MCP write               → gates: confirmed / no TODOs / dir exists
Phase 5:  Verify                  → [read] output + user acceptance
```

**Calibrate-only mode**: If project_map already has data (<15 placeholders), skips Phase 1-2 entirely. Runs Phase 3 calibration + Phase 3.5 audit directly.

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

Then open your IDE and say: `[init]` or `[初始化项目]`

### Four Setup Modes

```bash
setup.sh              # Fresh install (download + venv + configure)
setup.sh --update     # Pull latest framework code, preserve project data
setup.sh --migrate    # Update + migrate old paths + extract custom rules
setup.sh --check      # Health check: 6-category verification, 0 modifications
```

`--check` output:
```
▶ 1. Framework structure    ✓ .ai-operation/ exists
▶ 2. Python & venv          ✓ MCP dependencies installed
▶ 3. MCP tools              ✓ MCP server OK — 21 tools registered
▶ 4. IDE configs            ✓ .mcp.json Python path configured
▶ 5. Claude Code hooks      ✓ Cognitive gate hook
▶ 6. Project map            ✓ 8/8 files have content

   All checks passed! (17 pass, 0 warn)
```

### Customization

| I want to... | Edit this |
|---|---|
| Add project rules (naming/API/style) | `conventions.md` |
| Add new `[commands]` | `rules.d/commands.md` |
| Add module-specific rules | `rules.d/{module}.md` |
| Record lessons learned | Automatic via `[save]`, or `corrections/` |
| Change framework behavior | `.clinerules` → run `sync-rules.sh` |
| Add automated skills | `skills/{name}/SKILL.md` |

`rules.d/` files are auto-loaded by `[read]`. No framework files need editing.

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
│   ├── mcp_server/                   # 21 MCP tools + audit + loop detection
│   │   ├── server.py                 # Entry (audit logger, loop detector)
│   │   └── tools/                    # 11 modules
│   │       ├── save.py               # Two-phase save protocol
│   │       ├── read.py               # Budget-managed context loading
│   │       ├── scan.py               # Codebase scanner (full signature extraction)
│   │       ├── audit.py              # 5-check programmatic verification
│   │       ├── workflow.py           # TaskSpec + fast-track + reporting
│   │       ├── bootstrap.py          # Project initialization (3 gates)
│   │       ├── cognitive_gate.py     # SESSION_KEY + experience loading
│   │       ├── bypass.py             # Rule override + monitoring
│   │       ├── inventory.py          # Asset registry operations
│   │       ├── cleanup.py            # Garbage collection
│   │       └── skillify.py           # Workflow → SKILL.md extraction
│   ├── skills/                       # 6 skill protocols
│   ├── hooks/                        # Git pre-commit (3 gates)
│   ├── rules.d/                      # User custom rules (auto-loaded)
│   ├── scripts/                      # Rule sync, hook install
│   ├── cli/                          # Terminal tools + Web Dashboard
│   └── audit.log                     # Operation log
├── .claude/hooks/                    # Claude Code hooks
│   ├── check-dangerous.sh            # Blocks rm -rf, git push --force
│   ├── require-context.sh            # Cognitive Gate
│   └── governance-capture.sh         # Audit all operations
├── .clinerules                       # Rules (canonical source)
├── CLAUDE.md / .cursorrules / ...    # Auto-generated per IDE
└── setup.sh / setup.ps1              # Install / Update / Migrate / Check
```

---

## Competitive Landscape

| Capability | AI-Operation | Cline Memory Bank | everything-claude-code | Windsurf Rules | Cursor Rules |
|---|---|---|---|---|---|
| Enforcement | Code (Hook + MCP + Git) | Text only | Hook-based audit | Text only | Text only |
| Memory system | 8 files + key-value experience | 6 files | CLAUDE.md | Rules file | Rules file |
| Cognitive gate | Yes (physical block) | No | No | No | No |
| Codebase scanning | Built-in (aio__scan_codebase) | No | No | No | No |
| Claim verification | 5-check audit tool | No | No | No | No |
| Two-phase save | Yes (forced self-review) | No | No | No | No |
| Bypass framework | 4 states + rate limit | No | No | No | No |
| Health check | `--check` (17 items) | No | No | No | No |
| Migration tooling | `--migrate` (path + rules) | No | No | No | No |
| Multi-IDE | 4 IDEs from single source | Roo Code only | Claude Code only | Windsurf only | Cursor only |

### What's unique to AI-Operation

1. **Cognitive Gate** — physical tool-level block until context is loaded. Not a text instruction.
2. **Programmatic verification** — `aio__audit_project_map` runs code-level checks on AI claims. AI cannot self-validate.
3. **Full codebase scan** — `aio__scan_codebase` extracts every file's signatures in one call. Zero external dependencies.
4. **Two-phase save** — forced self-review with diff preview and 10-question audit.
5. **30-operation counter** — forces context re-read during long sessions, preventing drift.
6. **4-mode setup** — install / update / migrate / check. Framework upgrades are a first-class operation.

### What others do better

- **Letta Code**: Git-versioned memory with merge conflict resolution
- **claude-mem**: Vector-based semantic search over past experience
- **Claude Code Auto Dream**: Automated memory consolidation (AI-Operation's `[consolidate]` is manual)
- **Microsoft AGT**: Declarative policy language (OPA/Rego) vs. hard-coded Python rules

---

## Testing & CI

```bash
python -m pytest tests/ -v
```

21 tests covering: save validation, taskSpec workflow, trust scoring, bootstrap merge, audit logging.

CI: Python 3.9 / 3.11 / 3.12 x Ubuntu / Windows (6 combinations).

---

## Philosophy

> "Text rules are suggestions. Physical gates are law."

AI-Operation doesn't make AI smarter. It makes the **process** smarter — so that even when AI makes mistakes, the framework catches them before they reach the codebase.

The AI creates its own shackles and wears them.

---

## License

MIT

---

*The Plan IS the Product.*
