# [执行测试] MCP 执行协议

## 触发条件

当用户输入 `[执行测试]` 时，AI 必须调用 MCP 工具 `aio__force_test_runner`。

**禁止行为：**
- 禁止直接运行测试命令（必须通过 MCP 工具）
- 禁止跳过预清理步骤（工具自动执行）
- 禁止全管线盲跑（工具会拒绝含 `--all`、`full_pipeline` 等关键词的命令）

---

## 必填参数说明

| 参数 | 类型 | 说明 |
| :--- | :--- | :--- |
| `test_target` | string | 要测试的模块或节点名称（如 `IngestNode`、`tests/test_ingest.py`） |
| `test_command` | string | 要执行的完整测试命令（如 `python -m pytest tests/test_ingest.py -v`） |

---

## 工具内置行为

1. **预清理**：自动扫描并删除 `*.temp`、`temp_*.py`、`debug_*.py`、`tests/output/*.tmp` 等临时文件
2. **隔离检查**：检测命令中是否包含全管线关键词，如有则拒绝执行
3. **超时保护**：测试命令超过 300 秒自动终止
4. **输出截断**：stdout 最多保留末尾 3000 字符，stderr 最多保留末尾 2000 字符

---

## 验证标准

- 返回值以 `PASSED` 或 `FAILED` 开头
- 报告包含：预清理结果、测试命令、退出码、stdout/stderr
- 如果返回 `REJECTED`，说明参数不合规（空参数或全管线命令）
