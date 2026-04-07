# 项目契约 (Conventions)

> 全局一致性契约。AI 写代码前必须遵守这些约定。[STATIC] 由 [初始化项目] 或 [存档] 更新。
> corrections.md 中重复出现的一致性错误会自动升级到此文件。

## 1. 命名契约

- MCP 工具函数: `aio__` 前缀 + snake_case (`aio__force_architect_save`)
- Python 函数/变量: snake_case (`_compact_corrections`, `staged_updates`)
- 常量: UPPER_SNAKE_CASE (`REQUIRED_FILES`, `MAX_TOTAL_CHARS`)
- project_map 文件: camelCase.md (`activeContext.md`, `systemPatterns.md`)
- 触发命令: 中文方括号 (`[存档]`, `[读档]`, `[清理]`)

## 2. API / 数据契约

- MCP 工具返回格式: 首行 `SUCCESS` / `REJECTED` / `FAILED` / `PENDING_REVIEW`
- 必填参数不给默认值，可选参数给空字符串默认值
- 文件大小一律用 `len(content.encode("utf-8"))` 计算（字节），不用 `len(content)`（字符）

## 3. UI 契约

N/A — 本项目为 CLI/MCP 工具，无前端 UI。

## 4. 错误处理契约

- MCP 工具拒绝时返回 `REJECTED:` + 原因 + 示例（教 AI 怎么改正）
- 不抛异常到用户，catch 后返回结构化错误信息
- Git 操作失败返回 `PARTIAL SUCCESS` + 手动修复指引

## 5. 代码风格契约

- architect.py 当前单文件架构，未来拆分时按工具分组
- 每个 MCP 工具函数必须有 docstring 说明用途 + 参数 + 返回值
- `_audit()` 调用在工具入口和关键分支点
- 所有文件 I/O 指定 `encoding="utf-8"`
