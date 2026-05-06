---
name: project-bootstrap
description: 5 阶段项目初始化协议。框架植入新代码库后，AI 自主扫描并填写 project_map。
when: ["初始化", "接管", "bootstrap", "新项目", "init"]
paths: []
tools: ["Bash", "Read", "Grep", "Write"]
---

# 项目接管与初始化规范 (Project Bootstrap)

> **触发条件**：当用户说"初始化项目"、"接管这个项目"、"帮我填写 project_map"，或者 AI 在开机自检时发现 `.ai-operation/docs/project_map/` 下的文件仍然包含 `[TODO]` 占位符时，必须执行本规范。
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

## 校准模式（Calibrate-Only）

**前置检测**：在开始 Phase 1 之前，先检查 `.ai-operation/docs/project_map/` 的现有状态：

```
统计 project_map 中 [待填写] / [TODO] 占位符的总数：
  - 如果 ≥ 15 个占位符 → 全量模式（5 阶段完整执行）
  - 如果 < 15 个占位符 → 校准模式（跳过 Phase 1-2，直接进 Phase 3 校准 + Phase 3.5 审计）
```

**校准模式适用场景**：
- 项目通过 `setup.sh --migrate` 迁移，project_map 已有丰富数据
- project_map 已手动填写过，只需验证准确性
- 框架版本升级后需要校准但不需要重新扫描

**校准模式流程**：Phase 3（校准现有内容）→ Phase 3.5（审计验证）→ Phase 4（写入修正）→ Phase 5（验证）

---

## 五阶段接管流程（全量模式）

**每个阶段必须完成后才能进入下一阶段。在每个阶段结束时向用户汇报发现，等待确认后再继续。**

### Phase 1：代码库扫描（Scan）

**目标：用一次 MCP 工具调用获取完整代码库结构。**

**Step 1 — 定焦**：先看顶层目录，确定核心代码的子目录：

```bash
ls -d */ 2>/dev/null | head -20
```

问用户："核心代码在哪个子目录下？"（如 `src/`、`agent_core/`）。如果根目录就是代码，scope 留空。

**Step 2 — 调用扫描工具**：

```
调用 MCP 工具: aio__scan_codebase
参数:
  project_root = [项目根目录的绝对路径]
  scope = [用户指定的子目录，或留空扫描全部]
```

该工具自动完成：遍历文件树 → 读每个文件前 60 行 → 提取 class/def/import 签名 → 分类（entry/module/config/test）→ 返回结构化摘要（< 12KB）。**无需 repomix/npx 等外部依赖。**

**Step 3 — 补充上下文**（可选）：

```bash
git log --oneline -15 2>/dev/null                  # 近期提交
ls requirements.txt pyproject.toml package.json 2>/dev/null  # 依赖文件
ls .env docker-compose.yml Dockerfile 2>/dev/null   # 配置文件
```

**Phase 1 完成标准**：aio__scan_codebase 返回成功，得到文件清单 + 签名摘要。

---

### Phase 2：深度分析（Deep Analysis）

**目标：基于 Phase 1 的扫描摘要，针对性地深读关键文件，完成系统认知。**

> **注意**：Phase 1 的 aio__scan_codebase 已经完成了文件清单 + 签名提取（旧 T1 + T3）。Phase 2 只需要做 aio__scan_codebase 无法自动完成的分析：入口追踪、数据结构提取、约束挖掘。

---

**⚠️ 前置步骤（必须最先执行，不可跳过）**

读取 `.ai-operation/docs/project_map/corrections.md`。
- 如果文件**不存在或无活跃记录**：继续执行 T1
- 如果文件**有活跃纠正记录**：将每条 `LESSON` 加入本次扫描的重点检查清单，在对应子任务中优先执行
  - 例如：上次记录了「遗漏 `skills/audio_cloning.py`」→ T3 单元深读时必须优先检查该路径
  - 例如：上次记录了「误判系统为流水线，实为智能体」→ 综合定性时必须重新核查调用关系
- 如果文件中有 **COUNT >= 3** 的记录：这些已由 [存档] 自动升级到 conventions.md，无需手动处理。
  Bootstrap 时只需确认 conventions.md 中的契约仍然适用于当前代码库。

---

**T1 — 入口追踪（Entry Trace）**

从 Phase 1 扫描结果中的 **Entry Points** 出发，读入口文件全文（通常 1-3 个），追踪 `import` 链找到核心模块的调用关系。
目标：弄清数据从哪进、经过哪些单元、从哪出。

---

**T2 — 数据结构提取（Schema Extraction）**

搜索扫描范围内的核心数据结构：
```bash
grep -r "@dataclass\|TypedDict\|BaseModel\|class.*Schema" --include="*.py" -l 2>/dev/null | head -15
```
只读 grep 命中的文件，提取跨模块传递的数据结构字段定义。

---

**T3 — 约束挖掘（Constraint Mining）**

在 SCAN_ROOT 内搜索硬性约束和已知坑点：
```bash
grep -r "TODO\|FIXME\|HACK\|assert\|raise.*Error" $SCAN_ROOT --include="*.py" -n 2>/dev/null | head -30
```
对每个发现的约束，记录：约束内容 + 所在文件路径。

---

**综合定性（强制步骤，不可跳过）**

Phase 1 扫描 + Phase 2 分析完成后，**必须先输出以下定性声明，再进入 Phase 3**：

```
【系统定性】
这是一个 [系统类型：智能体 / 流水线 / 混合型] 系统，用于 [核心用途]，当前版本 [vX]。
判断依据：[引用具体文件或代码]

【已完成单元清单】
✅ [单元名] — [位置] — [一句话职责]
✅ [单元名] — [位置] — [一句话职责]
🚧 [单元名] — [位置] — [开发中，原因]
❌ [单元名] — [位置] — [未开始]

【核心数据流（3句话）】
[第1句：数据从哪里进来]
[第2句：经过哪些单元处理]
[第3句：最终输出是什么]
```

**如果以上任何一项需要填写 [待确认]，说明分析不充分，必须回去补读相关文件再输出。**

**Phase 2 完成标准**：能输出完整的【系统定性】声明，且【已完成单元清单】与 Phase 1 扫描结果一致。

> **⚠️ systemPatterns.md 的模块清单**：直接使用 aio__scan_codebase 的输出作为 systemPatterns.md 的"核心模块"部分。AI 只需在上面添加【系统定性】和【核心数据流】，禁止手写文件清单（手写会漏）。

---

### Phase 3：草稿生成与用户校准（Draft & Calibrate）

**目标：基于 Phase 1-2 的证据，生成 5 个文件的草稿，并与用户对齐。**

**重要：不要直接写文件。先以对话形式向用户展示草稿，等待确认。**

> **systemPatterns.md 草稿规则**：模块清单部分**必须**复制 aio__scan_codebase 的输出（完整文件列表），AI 只添加系统定性 + 数据流描述。不允许手工精简或遗漏任何文件。

按以下顺序，逐一向用户展示草稿内容并提问：

**Step 3.1 — 校准 `systemPatterns.md`**(议题 #010: projectbrief 已删,vision 在 design.md)

向用户展示：
```
我对这个项目的理解是：
- 核心愿景：[基于代码和 README 推断的一句话描述]
- 目标用户：[推断]
- 明确不做的事：[从代码边界推断]

这个理解准确吗？有什么需要修正的？
```

**Step 3.2 — 校准 `systemPatterns.md`**

展示 Phase 2 综合定性的完整结果，包含四个部分：

1. **系统定性**：展示【系统定性】声明，并说明判断依据。
2. **数据结构字典**：展示 T4 提取到的所有跨模块数据结构及其字段。
3. **可用单元清单**：展示【已完成单元清单】，包含每个单元的输入类型、输出类型、外部依赖、完成状态。
4. **数据流图**：展示【核心数据流】的完整路径。

提问：
- "这个系统定性准确吗？"
- "可用单元清单有没有遗漏？"
- "数据结构的字段定义有没有错误？"

**Step 3.3 — 校准 `techContext.md`**

向用户展示推断出的技术栈表格和已发现的坑点（来自 TODO/FIXME 注释）。
提问："有没有我没发现的外部 API 约束或已知坑点？"

**Step 3.4 — 确认 `activeContext.md` 和 `progress.md`**

这两个动态文件不需要用户校准，直接询问：
"当前最紧迫的任务是什么？这将作为 activeContext.md 的初始焦点。"

**Phase 3 完成标准**：用户对 systemPatterns、techContext 的草稿内容表示认可（即使只是“大致对，先这样”）。

**⚠️ Phase 3 结束时强制步骤（不可跳过）**

如果用户在校准过程中指出了任何草稿遗漏或错误，必须将其写入 `.ai-operation/docs/project_map/corrections.md`，格式严格按模板填写：

```
---
DATE: [YYYY-MM-DD]
CONTEXT: [Phase 几，做什么时出现的错误]
MISTAKE: [AI 犯了什么错，越具体越好]
CORRECTION: [用户怎么纠正的，原话或摘要]
LESSON: [下次扫描时的具体检查动作，必须是可执行的指令]
COUNT: [同类错误出现次数，首次填 1]
---
```

> **升级规则**：corrections.md 中 COUNT >= 3 的记录已由 [存档] 自动升级到 conventions.md，无需手动处理。Bootstrap 时确认 conventions.md 中的契约仍适用即可。

---

### Phase 3.5：可编程审计（Evidence Audit）

**目标：用代码验证 Phase 3 草稿中的可检查声明，堵住 AI 自我验证的漏洞。**

> **为什么需要这一步**：Phase 3 的"校准"依赖 AI 自我声明（"现有内容准确"），但 AI 既是 claim 的生产者又是验证者——这违反审计原则。本步骤用可编程检查替代自我声明。

**调用方式：**

```
调用 MCP 工具: aio__audit_project_map
参数:
  project_root = [目标项目根目录的绝对路径]
```

**5 项自动检查：**

| 检查 | 验证内容 | 判定 |
|---|---|---|
| 1. 文件存在性 | systemPatterns/inventory 中的路径 → `os.path.exists` | 缺失 >10% = FAIL |
| 2. 装饰器计数 | 代码中实际 `@enterprise_tool` 数量 vs inventory 声称数量 | 差 >2 = FAIL |
| 3. 依赖真实性 | 声称使用的库 → `grep import` 验证 | 声称但无 import = FAIL |
| 4. 命名一致性 | conventions.md 规则 → 抽样检查实际代码 | <70% 合规 = FAIL |
| 5. 配置解析 | .env 变量 / docker-compose 端口 vs techContext | 有冲突 = WARN |

**处理审计结果：**

- **全 PASS**：进入 Phase 4
- **有 WARN**：向用户汇报，确认是否需要修正草稿
- **有 FAIL**：必须修正草稿中对应的错误声明，重新审计通过后才能进入 Phase 4

**Phase 3.5 完成标准**：审计结果无 FAIL 项。

---

### Phase 4：调用 MCP 工具写入文件（MCP-Enforced Write）

**目标：调用 `aio__force_project_bootstrap_write` MCP 工具，将用户确认后的内容一次性写入全部 5 个文件。**

**为什么用 MCP 而不是直接编辑文件？**

MCP 工具是框架的强制执行层。直接编辑文件意味着 AI 可以在任何时候、跳过任何步骤地修改 project_map——这破坏了校准对话的意义。MCP 工具通过 `user_confirmed` 参数作为硬性门控：AI 必须声明"用户已经确认了草稿"才能触发写入，否则工具直接拒绝。

**调用规范：**

```
调用 MCP 工具: aio__force_project_bootstrap_write
参数:
    systemPatterns_content = [Phase 3.2 用户确认后的完整内容，不含任何 [TODO]]
  techContext_content   = [Phase 3.3 用户确认后的完整内容，不含任何 [TODO]]
  activeContext_focus   = [Phase 3.4 用户回答的当前最紧迫任务]
  progress_initial      = [当前待办事项列表]
  conventions_content   = [从代码库提取的命名/API/UI/错误处理契约，或 "SKIP" 稍后填写]
  user_confirmed        = True  ← 只有在用户明确表示"可以写入"后才能设为 True
```

**三道内置门控（MCP 工具自动执行）：**

| 门控 | 检查内容 | 拒绝条件 |
|---|---|---|
| Gate 1 | `user_confirmed` 参数 | `False` 时直接拒绝，要求先完成校准对话 |
| Gate 2 | 所有内容字段 | 任意字段含 `[TODO]` 时拒绝，要求替换为真实内容或 `[待确认]` |
| Gate 3 | `.ai-operation/docs/project_map/` 目录 | 目录不存在时拒绝，提示框架未正确植入 |

**Phase 4 完成标准**：MCP 工具返回 `SUCCESS`，6 个文件（含 conventions.md）已写入，git commit 已创建。

---

### Phase 5：验证（Verify）

**目标：确认 MCP 工具的写入结果，让用户验收初始化内容。**

> **注意**：git commit 已由 Phase 4 的 MCP 工具自动完成，此阶段无需再次提交。

1. 执行 `[读档]` 指令，输出宏观状态报告，让用户验证 5 个文件的内容是否准确
2. 向用户汇报：
   ```
   项目接管完成。project_map 已初始化（git commit 已由 MCP 工具自动创建）：
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
| **遗漏 `skills/` 目录的业务模块** | **Phase 1 第 7 条扫描命令必须执行。`skills/` 下的 `.py` 文件是已完成的能力，必须在 `systemPatterns.md` 中体现。** |
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
