物理拦截层 — pre-commit hook 实现 3 层门控：Gate 1 自动同步规则文件到 4 个 IDE；Gate 2 拦截对 project_map 的直接编辑（必须通过 MCP 工具）；Gate 3 拦截没有 taskSpec 审批的代码提交。合规率 95%（仅 --no-verify 可绕过）。
