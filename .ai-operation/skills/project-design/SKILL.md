---
name: project-design
description: 项目立意协议（greenfield）。把脑子里的想法逼成功能树 + 每节点 input/processing/output 合约，再交给 MCP 工具硬校验写入。
when: ["立项", "立意", "开题", "design", "项目设计", "新项目", "设计稿", "PRD", "功能树"]
paths: []
tools: ["Read", "Write"]
---

# 项目立意规范 (Project Design)

> **触发条件**：用户说"我想做个 XX 但说不清"、"开始一个新项目"、"立项"、"设计稿"，或 [`.ai-operation/docs/conception/design.md`](../../docs/conception/design.md) 不存在。
>
> **本规范解决的问题**：脑子里有个想做的东西，但写不出"它具体是什么"。框架原本只能接管已有代码（[project-bootstrap](../project-bootstrap/SKILL.md)），无法处理"想法→设计"这一段。本协议把想法压成**功能树 + 每节点 IO 合约**，作为后续编码的硬合约。
>
> **铁律**：`NO CODE WITHOUT A FUNCTIONAL TREE WITH IO CONTRACTS.`
> 写不出 input/processing/output → 你没想清楚 → 不要动代码。

---

## 何时使用

**必须使用：**
- 全新项目，代码尚未存在
- 想法仍停在"我想做个 XX"的句式

**不要使用：**
- 已有代码库（用 [project-bootstrap](../project-bootstrap/SKILL.md)）
- 单纯加一个小功能（用 `aio__force_taskspec_submit`）

---

## 设计哲学（要先理解，再执行）

PRD 风格的输出是给人读的（用户故事、痛点叙事），AI 拿到难以直接落代码。本协议要求的是**给 AI 读的设计语言**：

| 维度 | PRD 路线 | 本协议（功能树 + IO） |
|---|---|---|
| 抽象层级 | 用户体验层 | 系统结构层 |
| 是否可作弊 | 容易（"用户满意"啥都能写） | 几乎不能（写不出 IO 类型 = 没想清楚） |
| AI 落地难度 | 高（需二次拆解） | 低（每节点 ≈ 一个函数/模块） |
| 与框架契合 | 要新建文件 | **直接产出 systemPatterns.md 设计稿** |

**关键产物链**：
```
设计稿 design.md  ──┐
                   ├──→ 自动 diff / audit ──→ 偏差告警
实现稿 systemPatterns.md (bootstrap 产出) ──┘
```

设计稿是合约，实现必须对齐。这是本框架原本缺的闭环。

---

## 七阶段流程（schema v2，全部硬性强制）

> **P0-P6 全部实装**：anchor + IO 树 + 深度拆解 + 数据字典 + 依赖 DAG + 优先级三类边界,共 16 道 gate。Phase 7 是两阶段写入(draft → 预览 → confirm),模仿 `[save]` 协议。
>
> 16 道 gate 完整清单见本文档末尾的 [Gate 总览](#gate-总览schema-v2-全部门控)。

### Phase 0：根锚（Root Anchor）

**目标**：用 1-3 句话锁死项目存在的理由。

**给用户的提问（按顺序问，得到答案前不进 P1）：**

```
Q1. 这是一个什么产品？(产品类型 + 形态：CLI / 网页 / 手机 App / Python 库 / 浏览器插件 / ...)
Q2. 解决什么需求？(具体到一个可验证的痛点，不能是"提高效率""更智能"这种抽象)
Q3. 不是给谁用的 / 不解决什么需求？(反向边界，至少 1 项)
```

**Q1 + Q2 合成 → root_anchor**（1-3 句）
**Q3 → negative_scope**（1 句）

**禁词**：高效 / 智能 / 一站式 / 全方位 / 一键 / any / 看情况 / TBD / 待定 / 等等。
出现这些 = 还没想清楚，重写。

**Phase 0 完成判据**：Q1+Q2 合成 1-3 句正向锚（无禁词）+ Q3 一句反向边界。

---

### Phase 1：一级功能广撒（Top-Level Capabilities）

**目标**：列 3-12 个一级功能，每个 1 句话职责。**先广后深**——这一步只要广度，不要深度。

**给用户的提问：**

```
基于刚才的根锚，列出 3-12 个一级功能。
- 少于 3 个：项目可能太小，不需要本协议
- 多于 12 个：要么合并相关功能，要么拆成子项目
每个功能用一句话写它干什么（最少 10 字）。
```

**Phase 1 完成判据**：3-12 个一级功能名称 + 每个 ≥ 10 字职责描述。

---

### Phase 2：每节点 IO 合约（Per-Node IO Spec）

**目标**：为每个一级功能写 input / processing / output 三段。**这是本协议最硬的一步。**

**对每个功能节点，向用户确认：**

```
功能 [name]：
- Input：什么类型的数据进来？从哪来？(具体到字段或示例)
- Processing：怎么变换？(1-3 行描述算法/逻辑)
- Output：什么类型的数据出去？给谁用？

写不出来 = 你不知道这个功能在干什么 = 要么删掉要么重新想。
```

**禁词**（在任一字段中出现都拒绝）：any / 看情况 / TBD / 待定 / 等等 / 高效 / 智能。

**Phase 2 完成判据**：每个节点的 IO 三段都 ≥ 5 字，无禁词，AI 能口述每个节点的代码骨架。

---

### Phase 3：深度拆解 (Decomposition)

**目标**：IO 太大或 processing 太复杂的一级节点，拆成 ≤ 4 层子树，直到每个叶子节点 ≈ 一个函数/模块（约 50-200 行代码）。

**给用户的提问（对每个一级节点逐个评估）：**

```
节点 [name]：
- 它的 processing 是否能用一段 ≤ 5 行的代码描述实现？
  是 → 不拆，留作叶子
  否 → 拆成子节点
- 拆出来的子节点要满足同样的 5 字段（name/purpose/input/processing/output）
- 子节点可继续拆，但**总深度不能超过 4 层**（一级 = 第 1 层）
```

**子节点字段差异**：
- `priority` 在子节点是 **可选**（不写则视为继承父节点）
- `consumes` 仍可标，引用任意节点（包括兄弟节点、父节点的兄弟）

**Phase 3 完成判据**：
- 任何"我光看 input/output 不知道里面在干什么"的节点都已被拆开
- 树深 ≤ 4 层（工具 Gate 6 强制）
- 节点名**全树唯一**（含子节点；工具 Gate 6 强制）

---

### Phase 4：数据字典 (Data Dictionary)

**目标**：所有 IO 字段中出现的**非原始类型**（如 `User`、`Message`、`Session`），必须在数据字典里给出字段定义。

**给用户的提问：**

```
扫一遍所有节点的 input/output 字段：
- 出现的类型是 int / str / float / bool / list / dict 等原始类型 → 不用定义
- 出现的是 User / Message / Order 这种自定义类型 → 必须在 data_dict 里给字段定义
```

**data_dict_json 格式：**

```json
{
  "User":    { "id": "int", "email": "str", "role": "str" },
  "Message": { "from": "User", "body": "str", "ts": "datetime" }
}
```

**要点**：
- 字段值是字符串描述类型，可以引用其他自定义类型（`"from": "User"`）
- 当前**不强制要求** IO 中提到的所有类型都已定义（容易误判，因为 IO 是自由文本），但工具 Gate 校验 `data_dict` 本身的结构合法性
- 字段不能是空对象（要么定义至少 1 个字段，要么删除该类型）

**Phase 4 完成判据**：所有 IO 中出现的非原始类型都已被定义；data_dict_json 是合法 JSON 对象。

---

### Phase 5：依赖 DAG (Dependency Edges)

**目标**：在每个节点上标 `consumes` 字段，列出它**消费**了哪些节点的 output。形成依赖 DAG（有向无环图），自动检测循环依赖。

**给用户的提问：**

```
对每个节点，问自己：
- 它的 input 是从哪几个节点的 output 来的？
- 把这些节点名写进 consumes（list of strings）
- 没有外部依赖（如纯工具函数）→ consumes 留空
```

**DAG 校验（工具自动跑）：**
- 所有 `consumes` 引用的名字必须是**已定义的节点名**（找不到 → 拒绝）
- 整个依赖图必须**无环**（出现 a → b → a 这种 → 拒绝并打印环路径）

**Phase 5 完成判据**：consumes 字段全部正确引用；工具未报告 cycle。

---

### Phase 6：三类边界 (Priority Marking)

**目标**：在**每个一级节点**上打优先级标签，强制说出"要做的"和"不做的"。

**取值**：
- `must-have` — MVP 必须有，缺它项目不成立
- `nice-to-have` — 可以加但不是核心
- `out-of-scope` — 明确不做的（重要！强制反向边界）

**给用户的提问：**

```
对每个一级功能：
- 删掉它，根锚还成立吗？成立 → nice-to-have 或 out-of-scope
- 不成立 → must-have
- 列了一堆"应该有但其实不做"的功能 → 标 out-of-scope，留作显式反向边界
```

**强制约束（工具 Gate 自动）：**
- 至少 1 个 must-have（否则项目无核心承诺）
- 一级 out-of-scope 数量 ≥ 一级 must-have 数量（**强制砍**——每承诺一项就要明确不承诺一项）

**Phase 6 完成判据**：一级所有节点都打了 priority；must-have ≥ 1；out-of-scope ≥ must-have。

---

### Phase 7：两阶段写入（Two-Phase MCP-Enforced Write）

模仿 `[save]` 协议的两阶段范式：先生成完整 staging 预览给用户看，确认后才落盘。**用户在 Phase 7a 看到的是最终 `design.md` 的全文,不是 AI 在 chat 里口述的草稿——文件级预览,改一个字都能看出来。**

```
P7a: aio__force_project_design_draft
   ├── 6 道 gate 全跑(anchor / neg-scope / JSON / tree-size / node-shape / 禁词)
   ├── 写 staging:.ai-operation/.design_staging.json
   ├── 渲染完整 markdown 预览(就是最终 design.md 的样子)
   └── 返回 PENDING_REVIEW + 完整预览
              ↓
   AI 把预览原样摊给用户看,用户说"行 / 改 X / 重来"
              ↓
   "改 X" → 重新调 draft，旧 staging 被覆盖,重新 6 道 gate
   "重来" → 不调 confirm，staging 24h 后过期作废
   "行"  → 进入 P7b
              ↓
P7b: aio__force_project_design_confirm(user_confirmed=True)
   ├── 读 staging
   ├── 24h 新鲜度检查(过期则拒,清理 staging,要求重新 draft)
   ├── 防御性重校验(staging 万一被手动改过)
   ├── 写 design.md(议题 #010: projectbrief 已删除)
   ├── git commit (非阻塞)
   └── 清理 staging → SUCCESS
```

**为什么必须两阶段**：
单阶段把"组装 + 写盘"合并,用户只能"口头确认 AI 在 chat 里描述的草稿",见不到最终文件。两阶段保证用户**看到完整 markdown 文件级预览**才决定是否落盘——这是 `[save]` 协议早就在用的范式,设计稿同等重要,不该例外。

---

#### Phase 7a 调用规范

```
调用 MCP 工具: aio__force_project_design_draft
参数:
  root_anchor          = [P0 Q1+Q2 合成的 1-3 句]
  negative_scope       = [P0 Q3 的 1 句反向边界]
  function_tree_json   = [JSON 数组,完整 schema v2,见下]
  data_dict_json       = [P4 数据字典 JSON,可选,默认空对象]
  (无 user_confirmed,因为 draft 阶段不写正式文件)
```

**function_tree_json schema v2(P1-P6 全字段）**：

```json
[
  {
    "name": "auth",
    "purpose": "用户登录注册并签发会话凭证",
    "input": "username (str), password (str)",
    "processing": "验证凭据,生成 JWT 并返回",
    "output": "JWT token (str) 或错误码 (int)",
    "priority": "must-have",
    "consumes": ["db", "audit_logger"],
    "children": [
      {
        "name": "verify_credentials",
        "purpose": "比对密码哈希子函数",
        "input": "username (str), password (str)",
        "processing": "查 db 取 hash, bcrypt 比对",
        "output": "User 对象或 None"
      }
    ]
  }
]
```

**字段必填矩阵：**

| 字段 | 一级节点 | 子节点 | 备注 |
|---|---|---|---|
| `name`, `purpose`, `input`, `processing`, `output` | 必填 | 必填 | P1+P2 |
| `priority` | **必填** | 可选(继承) | P6 |
| `consumes` | 可选 | 可选 | P5,默认 `[]` |
| `children` | 可选 | 可选(深度 ≤ 4) | P3 |

**data_dict_json 格式**(P4,可选)：

```json
{
  "User":    { "id": "int", "email": "str", "role": "str" },
  "Session": { "token": "str", "expires_at": "datetime" }
}
```

**Phase 7a 完成判据**：工具返回 `PENDING_REVIEW` + 完整预览(含树形展开 / 数据字典表 / 优先级统计 / 依赖图)。AI 把预览原文摊给用户。

---

#### Phase 7b 调用规范

```
调用 MCP 工具: aio__force_project_design_confirm
参数:
  user_confirmed = True   ← 仅在用户看完 7a 的预览并明确同意后置 True
```

**Phase 7b 完成判据**：工具返回 `SUCCESS`,design.md 已写入,staging 已清理,git commit 已创建。

---

#### Gate 总览（schema v2 全部门控）

| Gate | 在哪阶段查 | 类别 | 检查 | 拒绝条件 |
|---|---|---|---|---|
| 1 | 7b | 用户授权 | user_confirmed | False 直接拒 |
| 2 | 7a + 7b | P0 | root_anchor | 空 / 句数 > 3 / 含禁词 |
| 3 | 7a + 7b | P0 | negative_scope | 空 / < 5 字 |
| 4 | 7a + 7b | 结构 | function_tree JSON | 解析失败 / 不是 array |
| 5 | 7a + 7b | P1 | 一级节点数 | < 3 或 > 12 |
| 6 | 7a + 7b | P1+P2+P3 | 每节点字段（递归到子节点） | 缺字段 / 字段空 / purpose < 10 字 / IO 字段 < 5 字 / 含禁词 / 名字重复（全树） / 子树深 > 4 |
| 7 | 7a + 7b | 环境 | project_map 目录 | 不存在 → 提示先跑 setup |
| 8 | 7a + 7b | **P5** | consumes 引用解析 | 引用了未定义的节点名 → 拒 + 列出所有合法名 |
| 9 | 7a + 7b | **P5** | 依赖图无环 | 检测到 cycle → 拒 + 打印环路径 |
| 10 | 7a + 7b | **P6** | 一级 priority 完整性 | 任何一级节点缺 priority 或 priority 不在 {must-have, nice-to-have, out-of-scope} → 拒 |
| 11 | 7a + 7b | **P6** | 优先级平衡 | 0 个 must-have,或 out-of-scope < must-have → 拒 |
| 12 | 7a + 7b | **P4** | data_dict 结构 | 解析失败 / 非对象 / 类型字段是空对象 / 字段类型非字符串 → 拒 |
| 13 | 7b only | staging | staging 存在 | 不存在 → 必须先调 draft |
| 14 | 7b only | staging | schema 版本 | ≠ v2 → 拒 + 清理 staging |
| 15 | 7b only | staging | 新鲜度 | > 24h → 拒 + 清理 staging |
| 16 | 7b only | staging | 防御性重校验 | staging 被手动改过且不合法 → 拒 + 清理 staging |

7a 与 7b 重叠跑 Gate 2-12 是**故意的**——staging 文件可能在两次调用之间被人为编辑,纵深防御。

---

## 与其他技能的协作

```
project-design (本技能：想法 → 设计稿)
        ↓
[手工编码或 taskSpec 驱动开发，按 design.md 实现]
        ↓
project-bootstrap (代码完成后接管：扫描 → 实现稿 systemPatterns.md)
        ↓
[未来] aio__audit_design_vs_implementation (设计 vs 实现 diff)
        ↓
DUAL-LAYER AGENT WORKFLOW (taskSpec → 执行 → 存档)
```

`project-design` 一个项目只跑一次（除非彻底重做）。后续维护通过 [存档] 和 taskSpec。

---

## 常见陷阱与对策

| 陷阱 | 正确做法 |
|---|---|
| 把"用户体验"当 IO 写 | IO 是数据/类型契约，不是体验描述。"返回好看的页面" → "返回 HTML(str) + 状态码(int)" |
| 一上来就拆 4 层深 | 先广后深。Phase 1 只要一级 3-12 个，深度交给 P3 |
| 列了一堆"应该有"的功能 | 反问每个功能：删掉它根锚还成立吗？成立 → nice-to-have 或 out-of-scope，砍 |
| 抽象描述 input/output | 用具体类型和字段："User 对象" → 在 P4 数据字典里把 User 字段写清楚 |
| 跳过用户确认就调 MCP | Gate 1 会把你打回来 |
| **P3 拆错方向**：按"功能模块"拆而非按"调用层级"拆 | 子节点应该是父节点的**实现细分**（一段处理逻辑里的子步骤），不是平级的"另一个功能" |
| **P5 把"调用"和"消费"搞混** | consumes 是数据消费——A 的 input 来自 B 的 output。仅"A 调用 B 但不依赖 B 的返回值"不算 consumes |
| **P5 拒绝了说"我又不会写循环"就跳过** | cycle 检测 catch 的不只是显式循环，是**架构上不该耦合的两个节点不小心互相依赖**。被拒说明设计本身有问题 |
| **P6 全部标 must-have** | 强制 out-of-scope ≥ must-have 是**纪律**，不是 bug。每个承诺背后必须有一个明确放弃 |
| **P6 用 nice-to-have 逃 must-have 比例** | 工具会拒 0 must-have（项目无核心承诺）。"全部是 nice-to-have" 等于"我自己也不知道在做啥" |
| **P4 把 IO 写成自然语言绕过类型** | "返回用户信息" → 在 data_dict 定义 User，IO 写 "User 对象"。文字描述能逃 P4，但你自己将来落代码时会发现没合约可对照 |
| **修改设计稿直接改 design.md** | 改了不会触发任何 gate / 也不会影响 staging。要改必须重跑 7a draft，工具会重新 6 + P3-P6 全部校验 |
