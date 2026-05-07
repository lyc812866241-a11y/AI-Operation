---
name: omm-scan
description: 架构扫描协议。扫描代码库生成/更新 .omm/ 架构文档和 Mermaid 图。
when: ["架构扫描", "omm scan", "scan architecture", "update architecture", "refresh diagrams"]
paths: ["src/**", "*.py", "*.ts", "*.js"]
tools: ["Bash", "Read", "Grep", "Write"]
primary_artifact: .ai-operation/docs/project_map/systemPatterns.md
---
> ⚠️ **议题 #013 物理强制(必读)**:本 skill 修改 systemPatterns.md + .omm/(方向 D)。议题 #013 强制:必须用 aio__skill_invoke / aio__skill_complete 包裹执行。
>
> 执行流程:`aio__skill_invoke("omm-scan")` → 走完本 skill 所有步骤 → `aio__skill_complete("omm-scan")`。
> 完成时若 primary_artifact 未被修改,锁不释放。


# omm-scan — Perspective-Based Architecture Scanner

## Purpose

Analyze the codebase and generate **two outputs** (方向 D, 单 skill 维护两份产物):

1. **`.omm/`** — perspective-driven recursive architecture documentation (mermaid diagrams + 7 fields per element). Human-readable visualization.
2. **`.ai-operation/docs/project_map/systemPatterns.md`** — lightweight 5-section text summary distilled from `.omm/`. AI-loadable architecture index (≤ 50 行).

Single skill maintains both → 永不漂移。

## Modes (这个 skill 是 Layer 2 全量模式)

架构更新策略分三层(详见 `template_reference.md` 的 systemPatterns 更新策略段):

| Layer | 谁触发 | 跑什么 |
|---|---|---|
| **Layer 1 增量** | 半自动(在 [存档] 流程里) | 用户/Claude 在 [存档] 时手改 systemPatterns 受影响段,**不跑本 skill** |
| **Layer 2 全量(本 skill)** | 手动 `[架构扫描]` / 周期建议 | 全量重扫 + 重建 `.omm/` + 重写 `systemPatterns.md` |
| **Layer 3 漂移兜底** | `aio__audit_project_map` 自动 | 检测到漂移时建议跑 Layer 2 |

**何时调用本 skill**:
- 每 5-10 个 taskSpec 完成后(反漂移仪式)
- 大重构后(模块拆分/合并/换技术栈)
- audit 报告漂移
- 用户主动跑 `[架构扫描]`

---

## Recursive Analysis Concepts

- A **perspective** is a top-level element — a distinct way to look at the architecture.
- Each element in a diagram gets analyzed recursively. If it has internal structure, it becomes a **child element** (subdirectory with its own diagram). If not, it stays a leaf.
- The filesystem determines nesting. Element IDs in diagrams match child directory names. The viewer resolves groups from the filesystem.

## Prerequisites (MUST execute before anything else)

Run this command FIRST. Do NOT skip. Do NOT proceed without it.

```bash
npm list -g oh-my-mermaid 2>/dev/null || npm install -g oh-my-mermaid
```

Then verify:
```bash
omm --version
```

If omm is not found after install, STOP and tell the user: "omm 安装失败，请手动执行 `npm install -g oh-my-mermaid`"。

---

## Step 0: Check Language

```bash
omm config language
```

Write field content (description, context, constraint, concern, todo, note) in the configured language. Default is English. Element IDs, directory names, and diagram node IDs are always English kebab-case.

## Step 1: Explore the Codebase

Use Glob and Read to understand the project:

- Read `package.json`, `pyproject.toml`, or equivalent manifests
- List top-level directories to identify module boundaries
- Read key entry points (main, index, app files)
- Look for route definitions, service layers, database connections, external integrations

## Step 2: Select Perspectives

From the catalog below, choose which perspectives are meaningful for this codebase.

### Perspective Catalog

| Perspective | When to create | What it answers |
| --- | --- | --- |
| `overall-architecture` | **Always** | What exists and how pieces relate |
| `request-lifecycle` | Any server/API | How a request enters and gets handled end-to-end |
| `data-flow` | Any data processing, DB usage | Where data comes from, transforms, and lands |
| `dependency-map` | Complex module graph | What depends on what, what's shared |
| `external-integrations` | External APIs/services | What the system connects to and why |
| `state-transitions` | Stateful features (frontend or backend) | How state changes and what triggers it |
| `route-page-map` | Frontend with routing | Page structure and navigation flow |
| `command-surface` | CLI tools | Command hierarchy and dispatch |
| `extension-points` | Plugin/extension systems | Extension architecture and registry |
| `pipeline` | ML/data pipelines | Stage topology and data flow |
| `orchestration` | Event-driven/queue systems | Publisher, subscriber, broker topology |
| `storage` | 2+ storage systems | Storage topology (DB, cache, queue, object store) |

Don't force perspectives that don't exist in the code.

## Step 3: Generate Perspectives with Recursive Drill-Down

For each selected perspective, follow this recursive process:

### 3a. Write the perspective diagram

Element IDs match child directory names. The viewer resolves nesting from the filesystem.

```bash
omm write <perspective> diagram - <<'MERMAID'
graph LR
    renderer["Renderer\nsrc/renderer/"]
    renderer -->|"IPC invoke/on"| main-process["Main Process\nsrc/main/"]
    main-process -->|"spawn PTY"| engine-system["Engine System\nsrc/main/engine/"]
    main-process -->|"read/write JSON"| data-store["Data Store\nsrc/main/store.ts"]
    main-process -->|"xterm.js"| terminal-dock["Terminal Dock\nsrc/renderer/src/panel/"]
MERMAID
```

### 3b. Write the other 6 fields

Each as a separate `omm write` command: description, context, constraint, concern, todo, note.

### 3c. Recursive drill-down: analyze every element

**For every element in the diagram:**

1. **Analyze** the code it represents (Glob + Read the relevant files/directories)

2. **Write description for every node — no exceptions.** This creates the element directory. Optionally write other fields (context, constraint, concern, todo, note) if relevant — Write in the configured language.

   ```bash
   omm write <perspective>/<element-name> description - <<'EOF'
   (what this element does, which files/dirs it covers)
   EOF
   ```

3. **Decide leaf or group:**
   - **Distinct internal components found** → write a diagram and recurse deeper (it becomes a group)
   - **No meaningful sub-components** (single file, trivial wrapper, external system) → write remaining fields only (it stays a leaf)

4. **If group** — write diagram and recurse:

   ```bash
   omm write <perspective>/<element-name> diagram - <<'MERMAID'
   graph LR
       (internal elements)
   MERMAID
   ```

   Then repeat step 3c for each element in this diagram.

### Example recursion

```text
overall-architecture (perspective)
  elements: renderer, main-process, engine-system, data-store, terminal-dock

  → analyze renderer (src/renderer/)
    → finds: App.tsx, components/, hooks/, stores/, world/
    → group → write diagram with: components, stores, world
      → analyze components → 15 .tsx files, no sub-structure → leaf
      → analyze stores → 4 zustand stores → leaf
      → analyze world → OfficeCanvas + PixiJS logic → leaf

  → analyze main-process (src/main/)
    → finds: ipc.ts, auth/, engine/, terminal-session-service.ts, store.ts
    → group → write diagram with: auth, engine, terminal-session
      → analyze auth → auth-service.ts, callback-server.ts → leaf
      → analyze engine → claude-code.ts, codex.ts → leaf

  → analyze data-store (src/main/store.ts)
    → single file → leaf

  → analyze terminal-dock (src/renderer/src/panel/)
    → TerminalDock.tsx, DockManager → leaf
```

## Step 4: Distill `systemPatterns.md` Summary (方向 D 关键步)

After all `.omm/` perspectives are generated, **also write `systemPatterns.md`** as the lightweight text index for AI loading. Single source of truth (`.omm/`), two derived outputs.

Read from `.omm/` what you just generated, then compile a **5-section summary**:

1. **§ 1 系统定性** — From `.omm/overall-architecture/description`, extract system type + core purpose + version. Format: `[类型] — [用途] — vX`.
2. **§ 2 核心模块清单** — From top-level perspective elements, list as table: `模块 | 路径 | 一句话职责 | 状态(✅/🚧/❌)`.
3. **§ 3 数据结构字典** — From data structures detected during scan (search `interface`/`type`/`class`/`@dataclass`/Pydantic models), list: `结构名 | 定义位置(file:line) | 用途`.
4. **§ 4 数据流** — From the main data-flow perspective (or `.omm/overall-architecture/diagram`), distill into one-line arrow chain. Example: `HTTP → API handler (src/api.py:42) → Validator → DB writer → Postgres`.
5. **§ 5 架构约束** — Extract from code: `assert` / `raise NotImplementedError` / `TODO` / `FIXME` lines, each with `file:line` reference.

**Write target**: `.ai-operation/docs/project_map/systemPatterns.md` — full overwrite.

**Format**: strictly follow `.ai-operation/docs/templates/project_map/systemPatterns.md`.

**Hard limit**: ≤ 50 lines. If exceeded, you're including too much detail — push it down to `.omm/` instead.

## Step 5: Summarize

Report what was created/updated (both `.omm/` and `systemPatterns.md`). Suggest `omm view` to view the visual architecture.

## Diagram Rules

- **Element IDs must match the child directory name.** Use kebab-case: `main-process`, `data-store`, `terminal-dock`.
- **Element labels use two-line format**: name + file path, separated by `\n`:

  ```text
  main-process["Main Process\nsrc/main/"]
  auth-service["Auth Service\nsrc/auth/service.ts"]
  ```

- Every edge must have a meaningful label: `A -->|"why this connection exists"| B`
- More elements in one diagram means you should recurse deeper.
- Use `graph LR` for most diagrams, `graph TD` for hierarchies.
- Use `classDef` for visual distinction when helpful:

  | Style | Color | When to use |
  | --- | --- | --- |
  | `external` | `#585b70` | Third-party services outside your codebase |
  | `concern` | `#f38ba8` | Known risk or bottleneck |
  | `entry` | `#89b4fa` | Entry points (HTTP handler, CLI, queue consumer) |
  | `store` | `#a6e3a1` | Persistent storage (DB, cache, file system) |

  ```text
  classDef external fill:#585b70,stroke:#585b70,color:#cdd6f4
  classDef concern fill:#f38ba8,stroke:#f38ba8,color:#1e1e2e
  classDef entry fill:#89b4fa,stroke:#89b4fa,color:#1e1e2e
  classDef store fill:#a6e3a1,stroke:#a6e3a1,color:#1e1e2e
  ```

## General Rules

- **Write each field as a separate `omm write` command.** Each `omm write` must be its own Bash tool call.
- Do not rewrite elements that haven't changed.
- Do not create circular references. A child element must never reference its parent.
