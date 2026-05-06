# Project Map 填写参考 (Template Reference)

> 本文件包含每个 project_map 文件的详细填写规范和示例。
> AI 在执行 [初始化项目] 时参考此文件，日常开发不需要读。
> 不计入 12KB 提示词预算。

---

## design.md 填写规范（议题 #010 后接管 vision/scope 角色）

> **物质职责**：项目愿景 + 反向边界 + IO 合约 + 功能树 + 优先级 — 单一来源。
> **由谁写**：由 `skills/project-design/` 立项时通过 `aio__force_project_design_*` 工具写入。
> **物理位置**：`.ai-operation/docs/conception/design.md`（不在 project_map/ 内）。
>
> 议题 #010：projectbrief.md 已删除。原本属于它的"愿景 + 反向边界"由 design.md §1 (根锚) + §2 (反向边界) 承担;业务指标 + 目标用户不在 project_map 范围内（属于 product spec / 商业文档）。

### 1. 根锚 (Root Anchor)
1-3 句话写清"这个项目是什么类型的产品 + 解决什么需求"。不写技术实现,只写业务/价值。
示例：`全自动短视频生产系统,让一人以团队效率完成素材到成片全流程,单条视频生产从 4 小时压缩到 20 分钟。`

### 2. 反向边界 (Negative Scope)
1 句话写清"这个项目不为谁/不做什么",防止 AI 自作主张扩展 scope。
示例：`不为高端定制广告服务（每条都需要导演级人工把控的不在范围内）;不做实时直播流处理。`

### 3. 数据字典 (Data Dictionary)
跨节点传递的核心数据结构,JSON 类型定义。

### 4. 功能树 (Functional Tree)
每个节点必填:name / purpose / input / processing / output。
顶层节点必须有 priority(must-have / nice-to-have / out-of-scope)。
最大深度 4 层。可选 `consumes`(声明依赖)。

### 5. 优先级与统计 / 元信息
project-design 工具自动渲染。

---

## systemPatterns.md 填写规范（5 段，与 template 严格对齐）

> **维护 skill**：`skills/omm-scan/`(全量扫描)+ [存档] 流程(增量更新)
> **物质职责**：AI / 新人接手项目时**架构入门必读**。详细可视化在 `.omm/`,本文件是**轻量索引**(< 50 行)。

### 1. 系统定性
格式：`[系统类型] — [核心用途] — 当前版本：[vX]`
类型枚举：`纯流水线型` / `纯智能体型` / `混合型（状态机驱动）` / `工具集型`

### 2. 核心模块清单
表格格式：模块 / 路径 / 一句话职责 / 状态(✅ 已完成 / 🚧 开发中 / ❌ 未开始)。
AI **必须优先复用** ✅ 模块,不重复造轮子。

### 3. 数据结构字典
跨模块传递的核心数据结构,标注**定义位置**(file:line)。
存在理由:改字段时知道哪些调用方会受影响——防止破坏数据契约。

### 4. 数据流
用箭头描述数据在模块间的流转路径。
例:`HTTP → API handler (src/api.py:42) → Validator → DB writer (src/db.py:88) → Postgres`

### 5. 架构约束
不可违反的约束,**每条标注代码依据**(从 assert / raise / TODO / FIXME 提取)。
例:`所有外部 API 调用必须经过 retry 装饰器 — 依据:src/agent.py:88 (raise NotImplementedError)`

---

## systemPatterns 更新策略（三层 hybrid 模型）

> 这是议题 #006/#007 迭代节奏在架构文档层的具体应用。

| 层 | 频率 | 触发方式 | 干什么 |
|---|---|---|---|
| **Layer 1 增量** | 每个 taskSpec | **半自动** — [存档] 时被问"本次改架构了吗?" | 改 systemPatterns 受影响段(§2/§3/§4/§5),不动 .omm/ |
| **Layer 2 全量** | 每 5-10 taskSpec / 大重构 | **手动** — 跑 `[架构扫描]` | 跑 omm-scan 全量重扫,重建 .omm/ + 重写 systemPatterns.md |
| **Layer 3 兜底** | 不定期(被动) | **全自动** — `aio__audit_project_map` 检测漂移 | 输出警告 + 建议跑 Layer 2 |

**为什么三层都要**:
- 纯 Layer 1 → 二阶传播看不见,3 个月后跟代码脱节
- 纯 Layer 2 → 全量太贵(npm + 递归 + 多 perspective),跑不动
- Layer 3 → 你忘记 Layer 2 时的安全网

**判断式**:**99% 时间 Layer 1 cover;5-10 个 taskSpec 触发一次 Layer 2;Layer 3 默默跑**。

---

## corrections.md 填写规范（项目级一阶 - 内部三段）

> **scope = 单项目** — 当前项目内所有经验/规则/习惯。
> 跨项目通用智慧不放这里(放 `.ai-operation/wisdom.md`)。
> 由 `skills/lesson-distill/` 维护。
> 末尾必须保留 `SESSION_KEY: xxx`(cognitive_gate 用,**不可删**)。

### §1 项目契约（声明式规则 — 防一类问题）

**写入模式**：section-merge / overwrite。稳定。
**来源**：立项主动设计 OR 从 §2 人工提炼。

示例：
- **命名**：API 路由 kebab-case；数据库字段 snake_case；React 组件 PascalCase；Python 函数 snake_case
- **API 数据契约**：所有 API 统一返回 `{ code, message, data }`,4xx 客户端错误 / 5xx 服务端错误
- **UI tokens**：网格 8px base；间距 4/8/12/16/24/32/48；圆角 4(按钮)/8(卡片)/16(模态框);主色 #2563EB
- **错误处理**：后端 middleware 统一 catch;前端 toast 3 秒自动消失
- **代码风格**：单文件 ≤ 300 行;函数 ≤ 40 行;import 分三段(stdlib → third-party → local)

### §2 具体踩坑（经验式日志 — 防同一个坑）

**写入模式**：append。
**结构**：本段只放**一行索引**(踩过几次 + key);**详细情况存** `corrections/{key}.md` 子文件。

示例索引：
- `dingtalk-userid-must-int` — 踩过 2 次
- `delete-api-output-protected` — 踩过 1 次

### §3 习惯指令（项目级 AI 操作约束）

**写入模式**：append。
**内容**：AI 在本项目的操作习惯 / 约束。

示例：
- 提交前必须跑 lint
- PR 必须关联 issue
- 部署前必须跑回归测试

---

## wisdom.md 填写规范（跨项目二阶 - 通用智慧）

> **物理位置**：`.ai-operation/wisdom.md`(框架级,**不在 `project_map/` 内**)
> **scope = 所有项目** — 跨项目通用方法论 / 普适原则 / 智慧
> **读取**：每次新对话 ★ 必读(跟 corrections 同级别)

### 三条铁律（议题 #009）

1. **type 边界 = scope 边界** — 单项目 corrections **永远不会**自动升级到这里
2. **只能由人主动写入** — 必须先拷问"对所有项目都成立吗?"
3. **每条经得起跨项目反例检验** — 不成立的反例项目出现 → 修订或撤回

### 内容形态

每条 wisdom 条目应包含:
- **核心命题**:一句话总结
- **推理**:为什么普适? 对所有项目都成立的论证
- **应用范围**:在什么情境下生效
- **反例边界**:什么情境下不适用(如有)

示例:议题 #005 求导思维(已写入 wisdom.md 第 1 条)。

### 写入触发器

| 何时 | 谁 |
|---|---|
| 单个项目反思后,发现疑似普适的洞察 | **人主动**判断 + 拷问 |
| 多项目对比后,发现共性原理 | **人主动**判断 |
| AI 自动从一阶升级 | **❌ 严格禁止**(议题 #009 铁律 1) |

### 反模式

- ❌ 把项目级规则误升级到这里(scope 不同就不是同一 type)
- ❌ 写"通用经验"但其实只在某类项目成立(必须明确反例边界)
- ❌ 用 corrections × N 次累积"证明"普适(累积只证明该项目重复出现,不证明跨项目普适)

---

## techContext.md 填写规范

### 1. 核心技术栈
只列不可替换的技术选型，标注"为什么不能换"。

### 2. 外部依赖
列出所有外部服务的关键限制（速率、路径、内存等）。

### 3. 已知坑点
格式：`**[坑点名称]**：[表现] → [正确做法]`
每踩一次新坑通过 [存档] 追加。

### 4. 环境依赖
运行项目必须满足的条件（Python 版本、CUDA、API key 等）。

---

## activeContext.md 填写规范（动态文件 - 快照型）

> **物质职责**：议题 #002 The Engine 的载体。让被中断的会话在 2 分钟内恢复到工作状态。
> **写入模式**：**OVERWRITE**（不是 APPEND）—— 快照,非日志。**≤ 80 行硬上限**。
> **维护 skill**：`skills/state-checkpoint/`(由它强制更新,不手写)

### 必需字段

| 字段 | 必填 | 约束 |
|---|---|---|
| 最后更新 | ✓ | ISO 时间戳 `YYYY-MM-DD HH:MM` |
| 当前 taskSpec | ✓ | 必须链回真实 taskSpec 文件 |
| § 1 taskSpec 边界 | ✓ | 上一个 / 当前 / 下一个(预期) |
| § 2 子步骤 | ✓ | 必须含 `X / N` 数字进度 |
| § 3 关键决策 | 可空 | 每条:`决策 — 理由` 二元结构 |
| § 4 卡点 | 可空 | "无" 或具体问题描述 |
| § 5 下一动作 | ✓ | **必须含动词 + 具体对象**,拒"继续/修复"泛话 |

### 更新触发器（6 个语义事件）

| 事件 | 强制级别 | 更新哪部分 |
|---|---|---|
| 完成 taskSpec 子步骤 | **必须** | § 2 + § 5 |
| 完成 taskSpec | **必须**（MCP 兜底强制） | § 1 切换 + 重置 § 2/3/4/5 |
| 做出关键决策 | **必须** | § 3 add |
| 发现卡点 | 强烈建议 | § 4 add |
| 解决卡点 | 强烈建议 | § 4 remove |
| 决策升级到 corrections §1 / design / wisdom | **必须**（防膨胀） | § 3 remove |

**判断式**（挂工作台）："现在中断,1 小时后回来,看 activeContext 能 2 分钟接续吗?"
- 能 → 不更新
- 不能 → **立即更新**

### 反模式（被拒内容）

| ❌ 不该写 | 正确归宿 |
|---|---|
| 历史日志、里程碑 | git log / git tags(议题 #011: progress.md 已删除) |
| 详细推理过程 | 对话 / skill log |
| 已沉淀到 corrections §1 / design / wisdom 的内容 | 那些文件 |
| 代码片段 | `file:line` 引用即可 |
| "继续开发" / "修 bug" 这种无意义动作 | 改写为具体动词+对象 |

---

## save 工具写入语义（必读）

不同参数走不同写入策略，**搞混会直接丢数据**。

### 静态文件（systemPatterns / techContext）

> ⚠️ **注意**:`corrections.md` 在重构后**不再是纯静态**——它有三段内部结构,§1 用 section-merge,§2/§3 用 append。详见 corrections 填写规范段。
> `conventions.md` **已删除**(并入 corrections §1)。
> `wisdom.md` 是跨项目级,在框架级位置 `.ai-operation/wisdom.md`,不在 project_map 内。

三种模式，按优先级：

1. **精准增量**（首选）—— 用 `===SECTION===` 分隔符
   ```
   ===SECTION===
   系统定性
   新定性内容
   ===SECTION===
   架构约束
   新约束内容
   ```
   - title 忽略 `N.` 数字前缀，两边都会自动 strip
   - 零匹配 → REJECTED（带实际 section 清单），**不会偷偷改成 no-op**

2. **显式全替换**—— 用 `FULL_OVERWRITE_CONFIRMED:` 前缀
   ```
   FULL_OVERWRITE_CONFIRMED:
   # 全新文件内容
   ...
   ```
   - 仅在你真要重写整份文件时用

3. **空/新文件**—— 纯文本
   - 只在文件不存在或无任何 `##` section 时允许
   - 已有 section 结构的文件传纯文本 → **REJECTED**（上面规则 2 的保护）

### 动态文件（议题 #011 后只剩 activeContext 一种类型）

⚠️ **历史背景**：早期版本统一规定为 APPEND,这对 activeContext 是错的——会让快照文件膨胀,违反"2 分钟恢复"目标(议题 #002 The Engine)。

- **快照型 → OVERWRITE**：`activeContext`
  - 只保留**当前**状态,不累积历史
  - ≤ 80 行硬上限
  - 由 `skills/state-checkpoint/` 维护
  - 议题 #009 修正:从 APPEND 改为 OVERWRITE

> 议题 #011: 原"日志型 progress" 已删除。历史归 git log,前瞻 todo 归下一 taskSpec,session_compaction feature 一并删除(走 [整理] / consolidate skill)。

### inventory 清单

- **`save(inventory_update=...)`** = **FULL OVERWRITE**，替换整个 inventory.md
- **`aio__inventory_append(category, item)`** = **增量追加**，首选这个

新增 1-2 条资产时**千万不要**用 save 的 `inventory_update`——会清空整个清单。
