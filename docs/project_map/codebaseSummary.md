# 代码库摘要与目录结构 (Codebase Summary)

> **[用途说明]**
> 本文件记录项目的文件结构、核心模块的职责以及关键脚本的入口。
> 当 AI 想要修改某个功能或者寻找某个类时，首先查阅此文件以定位。
> 任何目录结构的变更或核心模块的添加，都必须同步更新到这里。

## 1. 核心目录结构 (Directory Structure)
[描述项目顶层目录的作用。]

*示例（视频智能体）：*
```text
/
├── data/               # 本地测试与运行时数据目录（必须被 gitignore）
├── docs/               # 项目文档与设计图
│   └── project_map/    # 核心记忆与上下文文件
├── mcp_server/         # MCP 强制执行工具
├── skills/             # 独立的可复用脚本或能力
├── src/                # 核心业务代码（管线节点实现）
│   ├── node_0_crawler/ # 爬虫节点
│   └── node_1_understanding/ # 理解节点
├── tests/              # 单元测试与集成测试
├── .clinerules         # AI 行为准则与双层架构约束
└── README.md           # 项目入口说明
```

## 2. 核心模块与职责 (Core Modules & Responsibilities)
[列出核心模块或脚本的具体作用。]

*示例（视频智能体）：*
*- `src/node_0_crawler/main.py`: Node 0 的入口脚本，负责接收 URL 并调用内部下载器，输出到 `data/raw/`。*
*- `skills/audio_separation.py`: 基于 Demucs 的音频分离工具脚本，被 Node 1 调用。*
*- `mcp_server/tools/architect.py`: 包含保存、加载和清理工作区的强制执行工具。*

## 3. 数据流与契约文件 (Data Flow & Contract Files)
[记录模块间传递数据的关键文件或 Schema。]

*示例：*
*- `data/features.json`: Node 1 输出的特征契约，包含视频切片信息和音频文本。*
*- `data/casting_plan.json`: Node 3 输出的角色分配契约，定义了每个镜头的表现形式。*

---
### 引导问题（新项目启动时请回答）：
1. 核心业务代码放在哪里？
2. 测试代码和测试数据放在哪里？
3. 项目中有哪些独立的可复用脚本（Skills）？
