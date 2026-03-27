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
├── docs/               # 项目文档与设计图
│   └── project_map/    # 核心记忆与上下文文件（本目录）
├── mcp_server/         # MCP 强制执行工具
├── skills/             # 独立的可复用脚本或能力
├── src/                # 核心业务代码
├── tests/              # 单元测试与集成测试
├── .clinerules         # AI 行为准则与双层架构约束
└── README.md           # 项目入口说明
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
