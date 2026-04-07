# 系统架构与模块契约 (System Patterns)

> 新 Agent 接手时的必读文档。[STATIC] 架构变更时更新。

## 1. 系统定性

工具集型 — AI Agent 行为治理脚手架 — 当前版本：v1.0

## 2. 核心模块

| 模块 | 位置 | 职责 | 状态 |
|---|---|---|---|
| MCP 工具集 | .ai-operation/mcp_server/tools/architect.py | 14 个强制工具（存档/读档/清理/taskSpec/inventory/detail） | ✅ |
| MCP 服务器 | .ai-operation/mcp_server/server.py | 入口 + 审计日志 | ✅ |
| Pre-commit Hook | .ai-operation/hooks/pre-commit | 3 层门控（规则同步/map 保护/taskSpec 审批） | ✅ |
| 规则同步 | .ai-operation/scripts/sync-rules.sh/ps1 | .clinerules → CLAUDE.md/.cursorrules/.windsurfrules | ✅ |
| CLI 工具 | .ai-operation/cli/ai_op.py | 终端操作（read/save/clean/test/status/dashboard） | ✅ |
| Web Dashboard | .ai-operation/cli/dashboard.py | 零依赖本地可视化面板 | ✅ |
| Bootstrap Skill | .ai-operation/skills/project-bootstrap/SKILL.md | 5 阶段项目初始化协议 | ✅ |
| Debug Skill | .ai-operation/skills/systematic-debugging/SKILL.md | 根因调查协议 | ✅ |
| TDD Skill | .ai-operation/skills/test-driven-development/SKILL.md | TDD 强制协议 | ✅ |
| 安装脚本 | setup.sh / setup.ps1 | 跨平台一键安装 | ✅ |
| 单元测试 | tests/test_architect_tools.py | 21 个测试覆盖核心机制 | ✅ |
| CI | .github/workflows/ci.yml | 6 矩阵（Python 3.9/3.11/3.12 × Ubuntu/Windows） | ✅ |

## 3. 数据流

```
用户 → .clinerules（AI 读取规则）
  → MCP 工具（AI 调用，工具校验参数）
  → project_map/（工具写入 5+1 个文件）
  → Git Hook（拦截不合规的 commit）
  → git commit（合规后放行）
```

## 4. 架构约束

- architect.py 是单文件架构，所有 14 个工具在同一个文件。超过 2000 行，考虑拆分。
- MCP server 每次调用冷启动 Python 进程（~2 秒），两阶段存档 = 2 次冷启动。
- 所有文件大小阈值用字节数（encode utf-8），不是字符数。
- .clinerules 是 canonical source，其他 3 个 IDE 文件由 sync-rules 自动生成。

## 5. Conventions 契约体系

- conventions.md 是 project_map 第 7 个文件，存储全局一致性契约。
- 读档时优先级高于静态文件（always full），确保 AI 写代码前看到契约。
- corrections.md 中 COUNT >= 3 的条目自动升级到 conventions.md（闭环）。
- Bootstrap 时 conventions_content 为可选参数，可 SKIP。
