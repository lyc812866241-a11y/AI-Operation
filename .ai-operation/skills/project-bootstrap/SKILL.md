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

## 五阶段接管流程

**每个阶段必须完成后才能进入下一阶段。在每个阶段结束时向用户汇报发现，等待确认后再继续。**

### Phase 1：代码库地形侵察（Reconnaissance）

**目标：在不做任何判断的情况下，先摸清代码库的物理结构。**

> **⚠️ 模式前置条件（必读）**：以下所有 shell 命令必须在 **Code 模式**（具备 `execute_command` 工具）下执行。
> - 如果当前处于 **Architect 模式**，必须先切换到 Code 模式，再执行以下命令。
> - 切换方式：Roo Code 左下角模式选择器 → 选择 **Code**，或在对话框输入 `/mode code`。
> - Phase 1 完成后，可以切回 Architect 模式进行 Phase 3 校准对话。

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

# 7. 已有的业务 Skill 模块（关键：必须扫描，防止遗漏已完成的功能）
# 项目可能已有自己的 skills/ 目录（与框架的 skills/ 不同，是业务逻辑模块）
ls skills/ 2>/dev/null && echo "--- skills 目录存在 ---"
find . -path '*/skills/*.py' -not -path '*/__pycache__/*' | sort
find . -name 'OPERATOR_GUIDE.md' -o -name 'PIPELINE_GUIDE.md' -o -name 'ARCHITECTURE.md' 2>/dev/null

# 8. 尝试生成全局代码压缩地图（强烈推荐：如果目标环境支持 npx）
# 这将提取整个代码库的类与函数签名，防止遗漏任何隐藏模块
npx repomix --compress --output repomix-map.xml 2>/dev/null && echo "--- 全局代码地图 repomix-map.xml 已生成 ---" || echo "--- 未安装 npx，跳过全局地图生成 ---"
```

> **⚠️ 特别注意**：项目中的 `skills/` 目录可能包含已完成的业务功能模块（如 `audio_cloning.py`、`extract_product.py` 等），这些是**已实现的能力清单**，必须在 Phase 2 中读取并在 `systemPatterns.md` 中体现。不能只看 `src/` 目录。

**Phase 1 完成标准**：能回答"这是一个什么类型的项目，用什么语言写的，有多少文件，以及 skills/ 目录下有哪些已完成的业务模块"。

---

### Phase 2：并行深度扫描（Parallel Deep Scan）

**目标：用 5 个并行子任务同时扫描代码库的不同维度，获得完整的系统认知。初始化是一次性操作，允许消耗更多 token，不得偷懒跳过任何子任务。**

> **⚠️ 执行方式**：以下 5 个子任务必须**全部完成**，不得跳过。每个子任务完成后在工作记忆中记录结论，最后统一汇总。

---

**⚠️ 前置步骤（必须最先执行，不可跳过）**

读取 `.ai-operation/docs/project_map/corrections.md`。
- 如果文件**不存在或无活跃记录**：继续执行 T1
- 如果文件**有活跃纠正记录**：将每条 `LESSON` 加入本次扫描的重点检查清单，在对应子任务中优先执行
  - 例如：上次记录了「遗漏 `skills/audio_cloning.py`」→ T3 单元深读时必须优先检查该路径
  - 例如：上次记录了「误判系统为流水线，实为智能体」→ 综合定性时必须重新核查调用关系
- 如果文件中有 **COUNT >= 3 且未标注 `已升级`** 的记录：
  1. 将该 LESSON 追加到本文件（SKILL.md）Phase 2 对应子任务的检查清单末尾
  2. 在 corrections.md 中将该记录 COUNT 标注为 `已升级`
  3. 向用户报告升级内容，等待确认后继续

**自进化检查清单（由 corrections.md 升级机制自动追加）：**
<!-- 当 corrections.md 中某条 LESSON 的 COUNT >= 3 时，AI 会在此处追加一行检查项 -->

---

**T1 — 结构扫描（Structure Map）**

优先读取 `repomix-map.xml`（如果 Phase 1 已生成）。如果没有，则读取 README.md 和顶层目录结构。
目标：建立完整的文件清单，识别所有模块的物理位置。

---

**T2 — 入口追踪（Entry Trace）**

从入口文件（`main.py`、`app.py`、`cli.py` 等）出发，**逐层追踪调用链**，直到找到所有核心业务逻辑的调用点。
目标：弄清楚数据从哪里进来、经过哪些单元、从哪里出去。不能只看入口文件本身。

---

**T3 — 单元深读（Unit Deep Read）**

逐一读取每个核心单元（`skills/`、`src/`、`agents/`、`lib/` 下的模块）的入口文件。对每个单元记录：
- 函数/类签名
- 输入参数的类型和结构
- 返回值的类型和结构
- 调用了哪些外部 API 或服务
- 完成状态（函数体是否有实质实现，还是 `pass` / `raise NotImplementedError`）

**这是最容易遗漏已完成模块的环节，必须逐一检查，不能跳过任何文件。**

---

**T4 — 数据结构提取（Schema Extraction）**

在整个代码库中搜索核心数据结构定义：
```bash
# 搜索 dataclass、TypedDict、Pydantic BaseModel、Schema 定义
grep -r "@dataclass\|TypedDict\|BaseModel\|class.*Schema" --include="*.py" -l 2>/dev/null
# 搜索核心 JSON 结构（timeline、blueprint 等关键词）
grep -r "timeline\|blueprint\|manifest\|schema" --include="*.py" -l 2>/dev/null | head -10
```
逐一读取找到的文件，提取所有跨模块传递的数据结构的字段定义。

---

**T5 — 约束挖掘（Constraint Mining）**

搜索代码中的硬性约束和已知坑点：
```bash
# 搜索所有约束性代码
grep -r "TODO\|FIXME\|HACK\|assert\|raise.*Error\|StateMachine" --include="*.py" -n 2>/dev/null | head -40
```
对每个发现的约束，记录：约束内容 + 所在文件路径。

---

**综合定性（强制步骤，不可跳过）**

5 个子任务完成后，**必须先输出以下定性声明，再进入 Phase 3**：

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

**如果以上任何一项需要填写 [待确认]，说明对应子任务阅读不充分，必须回去补读再输出。**

**Phase 2 完成标准**：能输出完整的【系统定性】声明，且【已完成单元清单】中无遗漏（与 T3 扫描结果一致）。

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

**Phase 3 完成标准**：用户对 projectbrief、systemPatterns、techContext 的草稿内容表示认可（即使只是“大致对，先这样”）。

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

> **升级规则**：如果某条纠正记录的 COUNT 达到3，必须将对应的 LESSON 升级为 SKILL.md Phase 2 的强制扫描步骤，并将 COUNT 标注为 `已升级`。这是框架自我改进的核心机制。

---

### Phase 4：调用 MCP 工具写入文件（MCP-Enforced Write）

**目标：调用 `aio__force_project_bootstrap_write` MCP 工具，将用户确认后的内容一次性写入全部 5 个文件。**

**为什么用 MCP 而不是直接编辑文件？**

MCP 工具是框架的强制执行层。直接编辑文件意味着 AI 可以在任何时候、跳过任何步骤地修改 project_map——这破坏了校准对话的意义。MCP 工具通过 `user_confirmed` 参数作为硬性门控：AI 必须声明"用户已经确认了草稿"才能触发写入，否则工具直接拒绝。

**调用规范：**

```
调用 MCP 工具: aio__force_project_bootstrap_write
参数:
  projectbrief_content  = [Phase 3.1 用户确认后的完整内容，不含任何 [TODO]]
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
