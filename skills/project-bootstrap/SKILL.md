# 项目接管与初始化规范 (Project Bootstrap)

> **触发条件**：当用户说"初始化项目"、"接管这个项目"、"帮我填写 project_map"，或者 AI 在开机自检时发现 `docs/project_map/` 下的文件仍然包含 `[TODO]` 占位符时，必须执行本规范。
>
> **本规范解决的问题**：框架被植入一个已有代码库后，AI 需要自主扫描、理解、提炼，然后将结论写入 project_map 的 5 个文件，而不是让用户手动填写每一个字段。
>
> **铁律**：`NEVER fill project_map files based on assumptions. Every claim must be traced to actual files.`
> 所有写入 project_map 的内容，必须能指向代码库中的具体文件或代码作为依据。

---

## 何时使用

**以下情况必须触发本规范：**
- 框架被 `git clone` 或复制进一个已有项目后的首次会话
- 用户明确说"帮我初始化"或"接管这个项目"
- 开机自检（AUTO-INITIALIZATION）时发现 5 个文件中有 3 个以上仍含 `[TODO]` 占位符

**以下情况不需要触发：**
- project_map 已经由用户手动填写完毕（无 `[TODO]` 残留）
- 仅需要更新某一个文件（使用 `[存档]` 指令即可）

---

## 五阶段接管流程

**每个阶段必须完成后才能进入下一阶段。在每个阶段结束时向用户汇报发现，等待确认后再继续。**

### Phase 1：代码库地形侦察（Reconnaissance）

**目标：在不做任何判断的情况下，先摸清代码库的物理结构。**

按顺序执行以下扫描命令，并将结果保存在工作记忆中：

```bash
# 1. 顶层目录结构（不超过 3 层）
find . -maxdepth 3 -not -path '*/.git/*' -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*' -not -path '*/.venv/*' | sort

# 2. 依赖文件（判断技术栈）
ls requirements.txt pyproject.toml package.json Cargo.toml go.mod pom.xml 2>/dev/null

# 3. 配置文件（判断部署环境）
ls .env .env.example docker-compose.yml Dockerfile k8s/ 2>/dev/null

# 4. 入口文件（判断系统类型）
ls main.py app.py index.js server.js manage.py 2>/dev/null

# 5. 最近的 Git 提交记录（判断项目活跃度和方向）
git log --oneline -20 2>/dev/null || echo "非 Git 仓库"

# 6. 现有文档
find . -name "*.md" -not -path '*/.git/*' | head -20
```

**Phase 1 完成标准**：能回答"这是一个什么类型的项目，用什么语言写的，有多少文件"。

---

### Phase 2：核心逻辑深度阅读（Deep Read）

**目标：理解系统的真实运作方式，而不是猜测。**

根据 Phase 1 的侦察结果，选择性深度阅读以下内容（按优先级排序）：

| 优先级 | 读取目标 | 目的 |
|---|---|---|
| P0 | 入口文件（`main.py`、`app.py`、`index.js` 等） | 理解系统从哪里启动，主流程是什么 |
| P0 | 现有 README.md | 了解作者自己的描述 |
| P1 | 核心业务逻辑目录（`src/`、`lib/`、`core/`、`agents/` 等） | 理解模块划分 |
| P1 | 依赖文件（`requirements.txt`、`package.json`） | 确认技术栈和第三方依赖 |
| P2 | 配置文件（`.env.example`、`config.py`、`settings.py`） | 了解环境变量和外部服务依赖 |
| P2 | 测试目录（`tests/`、`__tests__/`） | 了解已有的功能边界 |
| P3 | 最近修改的文件（`git log --name-only -5`） | 了解当前开发重心 |

**阅读时记录以下问题的答案：**
- 数据从哪里进来，经过什么处理，从哪里出去？
- 有哪些明显的模块边界？
- 有哪些外部 API 或服务被调用？
- 代码里有没有明显的"坑"（TODO、FIXME、HACK 注释）？

**Phase 2 完成标准**：能用 3 句话描述这个系统的核心数据流。

---

### Phase 3：草稿生成与用户校准（Draft & Calibrate）

**目标：基于 Phase 1-2 的证据，生成 5 个文件的草稿，并与用户对齐。**

**重要：不要直接写文件。先以对话形式向用户展示草稿，等待确认。**

按以下顺序，逐一向用户展示草稿内容并提问：

**Step 3.1 — 校准 `projectbrief.md`**

向用户展示：
```
我对这个项目的理解是：
- 核心愿景：[基于代码和 README 推断的一句话描述]
- 目标用户：[推断]
- 明确不做的事：[从代码边界推断]

这个理解准确吗？有什么需要修正的？
```

**Step 3.2 — 校准 `systemPatterns.md`**

向用户展示推断出的模块结构表格：
```
| 模块名称 | 职责 | 输入 | 输出 |
|---|---|---|---|
| [推断的模块 A] | [推断的职责] | [推断的输入] | [推断的输出] |
```
提问："这个模块划分准确吗？有没有我遗漏的核心模块？"

**Step 3.3 — 校准 `techContext.md`**

向用户展示推断出的技术栈表格和已发现的坑点（来自 TODO/FIXME 注释）。
提问："有没有我没发现的外部 API 约束或已知坑点？"

**Step 3.4 — 确认 `activeContext.md` 和 `progress.md`**

这两个动态文件不需要用户校准，直接询问：
"当前最紧迫的任务是什么？这将作为 activeContext.md 的初始焦点。"

**Phase 3 完成标准**：用户对 projectbrief、systemPatterns、techContext 的草稿内容表示认可（即使只是"大致对，先这样"）。

---

### Phase 4：调用 MCP 工具写入文件（MCP-Enforced Write）

**目标：调用 `force_project_bootstrap_write` MCP 工具，将用户确认后的内容一次性写入全部 5 个文件。**

**为什么用 MCP 而不是直接编辑文件？**

MCP 工具是框架的强制执行层。直接编辑文件意味着 AI 可以在任何时候、跳过任何步骤地修改 project_map——这破坏了校准对话的意义。MCP 工具通过 `user_confirmed` 参数作为硬性门控：AI 必须声明"用户已经确认了草稿"才能触发写入，否则工具直接拒绝。

**调用规范：**

```
调用 MCP 工具: force_project_bootstrap_write
参数:
  projectbrief_content  = [Phase 3.1 用户确认后的完整内容，不含任何 [TODO]]
  systemPatterns_content = [Phase 3.2 用户确认后的完整内容，不含任何 [TODO]]
  techContext_content   = [Phase 3.3 用户确认后的完整内容，不含任何 [TODO]]
  activeContext_focus   = [Phase 3.4 用户回答的当前最紧迫任务]
  progress_initial      = [当前待办事项列表]
  user_confirmed        = True  ← 只有在用户明确表示"可以写入"后才能设为 True
```

**三道内置门控（MCP 工具自动执行）：**

| 门控 | 检查内容 | 拒绝条件 |
|---|---|---|
| Gate 1 | `user_confirmed` 参数 | `False` 时直接拒绝，要求先完成校准对话 |
| Gate 2 | 所有内容字段 | 任意字段含 `[TODO]` 时拒绝，要求替换为真实内容或 `[待确认]` |
| Gate 3 | `docs/project_map/` 目录 | 目录不存在时拒绝，提示框架未正确植入 |

**Phase 4 完成标准**：MCP 工具返回 `SUCCESS`，5 个文件已写入，git commit 已创建。

---

### Phase 5：验证（Verify）

**目标：确认 MCP 工具的写入结果，让用户验收初始化内容。**

> **注意**：git commit 已由 Phase 4 的 MCP 工具自动完成，此阶段无需再次提交。

1. 执行 `[读档]` 指令，输出宏观状态报告，让用户验证 5 个文件的内容是否准确
2. 向用户汇报：
   ```
   项目接管完成。project_map 已初始化（git commit 已由 MCP 工具自动创建）：
   - projectbrief.md：[一句话摘要]
   - systemPatterns.md：[模块数量] 个模块已定义
   - techContext.md：[技术栈] + [坑点数量] 个已知坑点
   - activeContext.md：当前焦点已设置
   - progress.md：初始里程碑已记录

   建议下一步：检查 [待确认] 标注的字段，逐一确认或修正。
   ```

---

## 常见陷阱与对策

| 陷阱 | 正确做法 |
|---|---|
| 看了 README 就直接填写，没有读代码 | README 可能过时。必须用代码验证 README 的描述。 |
| 把所有模块都列进 systemPatterns | 只列核心模块（数据流上的关键节点）。辅助工具不需要列入。 |
| 对不确定的内容也填写具体值 | 用 `[待确认]` 标注，不要凭空填写。 |
| 一次性写完所有文件，不与用户校准 | Phase 3 的校准是强制的。先对话，再写文件。 |
| 把 `activeContext.md` 当静态文件填写 | 它是动态文件，只填写"当前最紧迫的任务"，不要填写长期规划。 |

---

## 与其他技能的协作

本技能是框架的**入口技能**，完成后才能正常使用其他技能：

```
project-bootstrap（接管旧项目）
        ↓
.clinerules AUTO-INITIALIZATION（每次会话读取 project_map）
        ↓
DUAL-LAYER AGENT WORKFLOW（taskSpec → 执行 → 存档）
        ↓
systematic-debugging / test-driven-development（按需调用）
```

project-bootstrap 只需执行一次。之后由 `[存档]` 指令维护 project_map 的动态更新。
