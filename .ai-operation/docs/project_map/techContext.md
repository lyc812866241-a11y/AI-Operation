# 技术栈与上下文约束 (Tech Context)

> 技术选型、已知坑点。[STATIC] 技术变更时更新。

## 1. 核心技术栈

| 类别 | 技术 | 不可替换原因 |
|---|---|---|
| 语言 | Python 3.9+ | MCP server 和所有工具都是 Python |
| MCP 框架 | mcp[cli] + fastmcp | MCP 协议实现 |
| 版本控制 | Git + pre-commit hooks | 物理强制层 |
| 测试 | pytest | CI 矩阵 |
| 安装 | bash / PowerShell | 跨平台 |

## 2. 已知坑点

- **字符 vs 字节**：中文 1 字符 = 3 字节 UTF-8。所有文件大小检查必须用 `len(content.encode("utf-8"))`，不是 `len(content)`。已踩坑修复。
- **Windows git 慢**：大项目（8000+ 文件）上 `git add 目录` 会扫描全部工作树。必须 `git add 具体文件`。
- **MCP 冷启动**：每次工具调用启动新 Python 进程 ~2 秒。两阶段存档 = 2 次冷启动 ≈ 4 秒。
- **pre-commit hook 扫描**：hook 里的 `git diff --cached` 在大 repo 上很慢。MCP commit 用 `--no-verify` 跳过。
- **corrections.md 头部膨胀**：使用规则说明文字占 14KB，实际条目只有 3 条。需要先瘦身头部再计算。
- **`[存档]` 缩水警告假阳性**：动态文件 append 后比上次整体内容"短"是正常的（因为压缩了旧条目），但工具会报 size warning。

## 3. 环境依赖

- Python 3.9+（3.11/3.12 推荐）
- Git 2.x
- pip install mcp[cli] fastmcp（装在 .ai-operation/venv/ 里）
