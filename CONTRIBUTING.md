# Contributing to AI-Operation

> 这是**框架维护者**的文档。
> 日常使用 Claude / Cursor / Windsurf 编码**不需要读这个文件**——`CLAUDE.md` / `.clinerules` 才是 AI 的规则源。
> 这里只放"维护框架时才需要的信息":配置位置、修改流程、开发者参考。

---

## MCP 工具配置位置

- **Claude Code**:`.mcp.json`(项目根)
- **Cursor**:`.cursor/mcp.json`
- **Windsurf**:`.windsurf/mcp.json`

修改 MCP 配置后,重启 IDE 让其重新加载 MCP server。

---

## 框架规则修改流程

`.clinerules` 是唯一权威源。**不要直接编辑** `CLAUDE.md` / `.cursorrules` / `.windsurfrules`——它们由 `.clinerules` 自动生成。

```bash
# 修改 .clinerules 后必须同步:
bash .ai-operation/scripts/sync-rules.sh
```

`rules.d/` 文件会被 `[读档]` 自动加载,**无需修改任何框架文件**——加新规则只需往 `rules.d/` 丢 `.md` 文件即可。

---

## 自定义指南

| 我想… | 去哪改 | 说明 |
|---|---|---|
| 加代码契约(命名 / API / 风格) | `conventions.md` | 二阶:防一类问题 |
| 记录踩坑经验 | `corrections/{key}.md` | 一阶:防同一个坑 |
| 加项目操作规则 | `rules.d/{name}.md` | AI 行为约束 |
| 加新的 `[指令]` | `rules.d/commands.md` | 格式见 `rules.d/README.md` |
| 改框架行为 | `.clinerules` → `sync-rules.sh` | 改完需同步 |
| 加自动化 Skill | `skills/{name}/SKILL.md` | 参考已有 frontmatter |

---

## 开发者参考(框架内部位置)

| 内容 | 位置 |
|---|---|
| MCP 工具源代码 | `.ai-operation/mcp_server/tools/` |
| Git Hook(commit 拦截) | `.ai-operation/hooks/pre-commit` |
| 审计日志(MCP 调用记录) | `.ai-operation/audit.log` |
| 同步脚本(`.clinerules` → IDE 文件) | `.ai-operation/scripts/sync-rules.sh` |
| 安装 Hook | `.ai-operation/scripts/install-hooks.sh` |
