# 代码库摘要与目录结构 (Codebase Summary)

> **[用途说明]**
> 本文件记录项目的文件结构、核心模块的职责以及关键脚本的入口。
> 当 AI 需要修改某个功能或定位某个模块时，首先查阅此文件。
> 任何目录结构的变更或核心模块的添加，都必须同步更新到这里。

---

## 1. 核心目录结构 (Directory Structure)

[TODO: 描述项目顶层目录的作用。]

```text
/
├── .ai-operation/              # AI 框架（与项目代码完全隔离）
│   ├── docs/                   # 框架文档
│   │   ├── project_map/        # 核心记忆库（5 文件）
│   │   ├── codebaseSummary.md  # 代码库摘要
│   │   └── taskSpec_template.md # 任务规格模板
│   ├── mcp_server/             # MCP 强制执行工具
│   └── skills/                 # 框架技能模块
├── src/                        # 核心业务代码
├── tests/                      # 单元测试与集成测试
├── skills/                     # 项目业务技能（与框架 skills 分离）
├── .clinerules                 # AI 行为准则（Roo Code）
├── CLAUDE.md                   # AI 行为准则（Claude Code）
├── .cursorrules                # AI 行为准则（Cursor）
├── .windsurfrules              # AI 行为准则（Windsurf）
└── README.md                   # 项目入口说明
```

## 2. 核心模块与职责 (Core Modules & Responsibilities)

[TODO: 列出核心模块或脚本的具体作用。]

| 文件路径 | 职责描述 |
|---|---|
| `[path/to/module.py]` | [TODO: 描述该模块的核心职责] |

## 3. 数据流与契约文件 (Data Flow & Contract Files)

[TODO: 记录模块间传递数据的关键文件或 Schema。]

| 文件路径 | 描述 |
|---|---|
| `[path/to/contract.json]` | [TODO: 描述该契约文件的内容和用途] |

---

### 引导问题（新项目启动时请逐一回答）

1. 核心业务代码放在哪里？
2. 测试代码和测试数据放在哪里？
3. 项目中有哪些独立的可复用脚本（Skills）？
