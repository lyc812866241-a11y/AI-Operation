# AI-Operation

**AI Agent 行为治理框架 — 不是提示词模板，是物理强制层。**

Most AI coding frameworks tell the AI what to do. AI-Operation makes it **physically impossible** to skip the process.

---

## 摘要

AI-Operation 是一个开源的 AI Agent 行为治理框架（脚手架），通过"物理强制层"确保 AI Agent 严格遵循预设的开发流程和规范。核心在于构建了从软约束到物理阻断的**三层强制机制**，并通过 MCP 工具、8 文件分层记忆、Git 钩子和 corrections → conventions 自进化闭环，形成了一个越用越聪明的治理系统。

**v1.1 (2026-04-09)** — 14 个 MCP 工具 / 18 个强制机制 / 8 文件记忆系统 / 21 tests / 4 IDE 支持

---

## 1. 核心哲学：为何文本规则是不够的

传统 AI 框架依赖文本规则指导 Agent 行为——"先写计划"、"保存进度"。但 AI Agent 只有约 85% 的时间遵循，其余 15%：

- **跳过规划**：没有计划就写代码，后续调试花几倍时间
- **上下文丢失**：对话重置后"忘记"之前的工作
- **重复犯错**：同一个坑踩三次，因为没有被纠正的记忆
- **虚假完成**：声称任务完成但未验证

AI-Operation 的哲学：**文本规则是建议，物理门控是法律**。将"AI 请遵守规则"升级为"AI 不遵守也过不了关"。

---

## 2. 三层强制架构：从软约束到物理阻断

### 第一层：规则层（Rules）— 约 90% 合规

`.clinerules` 是唯一规范源，通过 Git pre-commit 钩子自动同步到 4 个 IDE 的规则文件。每条规则附带 `WHY` 解释，让 AI 理解原因而非盲从命令。

```
.clinerules (canonical) → CLAUDE.md / .cursorrules / .windsurfrules
                          每次 commit 自动同步
```

包含：Iron Laws（开发铁律）、双层代理架构、8 个触发指令、CONVENTIONS FIRST（契约优先）、CORRECTIONS AUTO-UPGRADE（经验自动升级）。

### 第二层：MCP 工具层（14 个工具）— 100% 合规

AI 必须调用 MCP 工具完成关键操作。工具内置硬编码校验，拒绝无效输入——空字段、缺少审批、信息密度不足。AI 无法通过"对话"绕过代码层面的验证。

| 指令 | 工具 | 强制内容 |
|---|---|---|
| `[存档]` | `aio__force_architect_save` + `_confirm` | 两阶段存档：6 文件参数 + lessons 必填 + 自审清单 6 问 + 数据质量检查 |
| `[读档]` | `aio__force_architect_read` | 优先级读取 + 50KB 预算控制 + TOC 模式 + 数据质量警告 |
| `[初始化项目]` | `aio__force_project_bootstrap_write` | 模板 merge + 3 门控（用户确认 / 无 TODO / 目录存在）|
| `[汇报]` | `aio__force_architect_report` | 4 段结构化报告，不允许自由格式 |
| `[执行测试]` | `aio__force_test_runner` | 自动预清理 + 隔离 + 5 分钟超时 |
| `[清理]` | `aio__force_garbage_collection` | 先列清单，用户确认后才删除 + git 健康扫描 |
| `[整理清单]` | `aio__inventory_consolidate` | 去重排序 inventory.md |
| `[架构扫描]` | omm-scan SKILL.md | 递归生成 .omm/ Mermaid 架构图（人类验证 AI 理解的抓手）|
| *TaskSpec 流程* | `submit` + `approve` | 6 段计划必填 → 用户审批 → 创建 flag → Git Hook 检查 |
| *快速通道* | `aio__force_fast_track` | 动态阈值：基于信任评分调整允许修改行数 |
| *实时追加* | `aio__inventory_append` | 发现资产立即持久化，防止上下文窗口丢失 |
| *详情读取* | `aio__detail_read` / `_list` | 按需加载分拆的子文件 |

**辅助机制：**
- **审计日志**：每次 MCP 调用记录到 `audit.log`，不可篡改
- **循环检测**：同工具+同参数 5 分钟内 3 次警告、5 次拒绝，强制 AI 换思路

### 第三层：Git 钩子层（物理阻断）— 约 95% 合规

pre-commit 钩子实现 3 层门控：

| 门控 | 作用 | 触发条件 |
|---|---|---|
| Gate 1 | 规则文件自动同步 | `.clinerules` 被修改时 |
| Gate 2 | 保护 project_map | 直接编辑 project_map/ 被拦截（必须通过 MCP 工具）|
| Gate 3 | 代码提交需审批 | 无 `.taskspec_approved` 或 `.fast_track` flag 时拦截 |

仅 `--no-verify` 可绕过，框架规则禁止此操作。

---

## 3. 8 文件分层记忆系统（Project Map）

AI 每次开机读取这 8 个文件恢复上下文，相当于 AI 的"长期记忆"：

| 文件 | 内容 | 类型 | 特殊机制 |
|---|---|---|---|
| `projectbrief.md` | 核心愿景与业务目标 | 静态 | — |
| `systemPatterns.md` | 系统架构与模块契约 | 静态 | 超限 section 自动拆到 details/ |
| `techContext.md` | 技术栈与已知坑点 | 静态 | — |
| `conventions.md` | 命名/API/UI/代码风格契约 | 静态 | corrections COUNT >= 3 自动升级到此 |
| `activeContext.md` | 当前焦点与下一步 | 动态 | > 8KB 自动压缩 |
| `progress.md` | 进度与里程碑 | 动态 | > 8KB 自动压缩 |
| `inventory.md` | 资产清单（模块/API/数据模型）| 静态 | 实时追加，全量覆写 |
| `corrections.md` | 经验库（犯过的错）| 动态 | COUNT 自增 + 自动升级 + 归档 |

**分层存储**：文件超限自动拆分到 `details/` 子目录，主文件留指针，`aio__detail_read` 按需加载。读档时 50KB 总预算控制，预算紧张时静态文件只显示 TOC。

**数据质量检查**：读档时自动检测 inventory 空白、systemPatterns 与 techContext 关键词矛盾（如写着 LangGraph 但 techContext 说自研 ReAct）、conventions 缺失。存档时自审清单强制 AI 关注数据完整性。

---

## 4. 自进化闭环：corrections → conventions

```
AI 犯错 → corrections.md 记录 (COUNT: 1)
同样的错再犯 → COUNT +1（代码自动自增，不是文本指令）
COUNT 到 3 → 自动升级到 conventions.md 成为项目契约
→ 以后 AI 写代码前就能看到这条约定
→ 同类错误从源头消失
```

这个闭环之所以有效，是因为：
1. `lessons_learned` 是 `[存档]` 的**强制参数**，MCP 工具拒绝空值
2. COUNT 自增是 **Python 代码**执行的，不是靠 AI 自觉
3. 升级到 conventions.md 后，**每次读档都会加载**（always full 优先级）
4. conventions.md 是**预防型**（写代码前看到），不是 corrections 的**纠错型**（犯错后记录）

---

## 5. 架构验证：[架构扫描]

框架集成了 [oh-my-mermaid](https://github.com/oh-my-mermaid/oh-my-mermaid)，用户说 `[架构扫描]` 即可生成交互式 Mermaid 架构图。

解决的问题：**AI 写代码几秒，人类理解代码几小时。** 架构图让项目负责人随时验证 AI 对项目的理解是否正确，而不是盲目信任 AI 的文本摘要。

```
[架构扫描]
  → AI 读取 SKILL.md，自动安装 omm（如未安装）
  → 选择视角（整体架构/数据流/依赖图...共 12 种）
  → 递归生成 .omm/ 目录（Mermaid 图 + 7 维文档）
  → omm view 打开浏览器查看
```

---

## 6. 快速开始

### 安装

**Linux / macOS / WSL：**
```bash
cd your-project
bash <(curl -fsSL https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.sh)
```

**Windows PowerShell：**
```powershell
cd your-project
irm https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.ps1 | iex
```

setup 自动完成：Python 检测 → 下载脚手架 → 创建 venv → 安装 MCP + omm 依赖 → 配置 4 个 IDE → 验证 MCP server → 安装 Git hooks。

然后打开 IDE，输入：
```
[初始化项目]
```

AI 扫描代码库，生成项目档案，请你确认后写入。从此每次会话自动恢复上下文，每次存档捕获经验。

### 更新已有安装

```powershell
# Windows
.\setup.ps1 -Update

# Linux / macOS
bash setup.sh --update
```

只覆盖框架代码（MCP 工具、脚本、Skills、规则），**保留** venv、project_map、audit.log 等本地产物。

---

## 7. 支持的 IDE

| IDE | 规则文件 | MCP 配置 | 自动同步 |
|---|---|---|---|
| Roo Code | `.clinerules` | `.roo/mcp.json` | Yes |
| Cursor | `.cursorrules` | `.cursor/mcp.json` | Yes |
| Windsurf | `.windsurfrules` | `.windsurf/mcp.json` | Yes |
| Claude Code | `CLAUDE.md` | `.mcp.json` | Yes |

编辑 `.clinerules` 一次，pre-commit 钩子自动同步其余三个。

---

## 8. 目录结构

```
your-project/
├── .ai-operation/                    # 框架（与你的代码隔离）
│   ├── docs/project_map/             # 8 文件记忆系统
│   ├── mcp_server/                   # 14 个强制工具 + 审计 + 循环检测
│   ├── skills/                       # 5 个技能协议（bootstrap/debug/TDD/omm-scan/mcp_protocols）
│   ├── hooks/                        # 3 层 pre-commit 门控
│   ├── scripts/                      # 规则同步、钩子安装
│   ├── cli/                          # 终端工具 + Web Dashboard
│   └── rules.d/                      # 子目录规则（monorepo 用）
├── .clinerules                       # 规则（唯一规范源）
├── CLAUDE.md / .cursorrules / ...    # 按 IDE 自动生成
└── tests/                            # 21 个框架测试
```

**框架文件不侵入你的项目目录。** 不与 `src/`、`docs/`、`skills/` 或任何其他目录冲突。

---

## 9. 18 个强制机制一览

| # | 机制 | 层级 | 作用 |
|---|---|---|---|
| 1 | Git Hook Gate 1 | 物理 | 规则文件自动同步 |
| 2 | Git Hook Gate 2 | 物理 | project_map 直接编辑拦截 |
| 3 | Git Hook Gate 3 | 物理 | 无审批的代码提交拦截 |
| 4 | MCP Flag 文件 | 工具 | 控制 Hook 放行（mcp_commit / taskspec / fast_track）|
| 5 | 信息密度校验 | 工具 | activeContext 200 字 + 文件路径 / progress 150 字 |
| 6 | NO_CHANGE_BECAUSE | 工具 | 跳过文件必须写理由 |
| 7 | 动态文件压缩 | 工具 | > 8KB 自动压缩旧内容 |
| 8 | Section 拆分 | 工具 | > 8KB 的 section 拆到 details/ 子文件 |
| 9 | Corrections → Conventions | 工具 | COUNT >= 3 自动升级为项目契约 |
| 10 | Conventions 契约层 | 规则 | 读档时 always full 优先加载 |
| 11 | Corrections 归档 | 工具 | > 10KB 瘦身头部 + 旧条目归档 |
| 12 | 通用 overflow 兜底 | 工具 | 任何文件 > 16KB 强制拆分 |
| 13 | TOC 模式读档 | 工具 | 预算紧张时静态文件只显示标题 |
| 14 | 信任评分 | 工具 | corrections 频率动态调整 fast-track 阈值 |
| 15 | 审计日志 | 工具 | 每次 MCP 调用记录到 audit.log |
| 16 | 循环检测 | 工具 | 同工具+同参数 3 次警告 / 5 次拒绝 |
| 17 | 数据质量检查 | 工具 | 读档检测 inventory 空白 / systemPatterns 过时 / conventions 缺失 |
| 18 | WHY 心理学 | 规则 | 每条规则附带理由提升 AI 遵守率 |

---

## 10. 测试与 CI

```bash
python -m pytest tests/ -v
```

21 个测试覆盖：存档参数校验、taskSpec 工作流生命周期、信任评分、bootstrap merge、审计日志。

CI 矩阵：Python 3.9 / 3.11 / 3.12 × Ubuntu / Windows（6 组合），每次 push 自动运行。

---

## 11. 与其他框架的定位区分

| | AI-Operation | DeerFlow / OpenHarness | LangGraph / CrewAI |
|---|---|---|---|
| 定位 | 治理层（AI 守不守规矩）| 执行层（AI 怎么跑起来）| 编排层（多 Agent 如何协作）|
| 核心能力 | 物理门控 + 自进化 | 沙箱 + 中间件 + 多 Provider | 图状态机 + 工具链 |
| 记忆 | 8 文件分层 + 自动分拆 | 单文件 MEMORY.md | 无内置 |
| 自进化 | corrections → conventions 闭环 | 无 | 无 |
| 可叠加 | 是 | 是 | 是 |

**AI-Operation 不替代执行层框架，而是叠加在它们之上。** 用 DeerFlow 跑 Agent，用 AI-Operation 管代码质量。

---

## License

MIT

---

*The Plan IS the Product.*
