# MCP 工具创建规范 (MCP Tool Creation Protocol)

## 核心原则

> 凡是你在 `.clinerules` 里写了"AI 必须做"但发现 AI 经常偷懒的步骤，就把它升级成 MCP 工具。

MCP 工具是将"AI 的承诺"变成"代码的契约"的机制。AI 无法绕过 MCP 工具，因为工具调用是强制的程序执行，不是文字描述。

---

## 何时创建新的 MCP 工具

当你发现以下任一情况时，立刻创建对应的 MCP 工具：

1. AI 经常跳过某个 `.clinerules` 里定义的必要步骤
2. 某个操作需要强制的参数校验（不能让 AI 自由发挥）
3. 某个操作需要真实的代码执行证据（不能只靠 AI 的文字汇报）
4. 某个操作涉及文件写入或 Git 操作（必须有可验证的结果）

---

## 创建新 MCP 工具的四步协议

每次创建新 MCP 工具，AI 必须同时完成以下四件事，缺一不可：

### Step 1: 在 `mcp_server/tools/` 下创建或更新工具文件

按类别选择或创建文件：

| 类别 | 文件 | 用途 |
| :--- | :--- | :--- |
| 架构维护 | `tools/architect.py` | 存档、读档、清理等框架级操作 |
| 管线执行 | `tools/pipeline.py` | 节点测试、验证、管线控制 |
| Git 操作 | `tools/git.py` | 提交、回滚、分支管理 |
| 自定义类别 | `tools/{category}.py` | 新业务类别时创建新文件 |

工具函数必须遵守以下规范：
- 函数名以动词开头，清晰描述动作（如 `force_architect_save`，不是 `save`）
- 所有参数必须有类型注解和 docstring 说明
- 返回值必须是字符串，包含 `SUCCESS` / `FAILED` / `PENDING` 状态标识
- 必须包含参数校验逻辑，拒绝不合规的输入

### Step 2: 在 `mcp_server/server.py` 里注册新工具

在 `server.py` 的注册区添加对应的 import 和 register 调用：

```python
from tools.your_category import register_your_tools
register_your_tools(mcp)
```

### Step 3: 在 `skills/mcp_protocols/` 下创建协议文档

文件命名规范：`{TRIGGER_COMMAND}_PROTOCOL.md`（如 `SAVE_PROTOCOL.md`、`TEST_PROTOCOL.md`）

协议文档必须包含：
- 触发条件（哪个 `.clinerules` 指令触发此工具）
- 必填参数说明（每个参数的含义和填写规范）
- 禁止行为（明确列出 AI 不允许做的事）
- 验证标准（如何判断工具执行成功）

### Step 4: 在 `.clinerules` Section 2 里添加路由索引

格式固定为一行：
```
- **`[触发词]`**: Call MCP tool `tool_function_name`. Protocol: `skills/mcp_protocols/PROTOCOL_FILE.md`
```

---

## 口令式创建新 MCP 工具

当你需要创建新的 MCP 工具时，在 Roo Code 里对 AI 说：

> "我需要一个新的 MCP 工具，触发词是 `[XXX]`，要约束的行为是：[描述 AI 经常偷懒的步骤]。按照 `skills/mcp_protocols/MCP_CREATION_PROTOCOL.md` 的四步协议完整创建。先给方案，等我同意再执行。"

AI 必须按照四步协议完整执行，不允许只完成部分步骤。

---

## 现有 MCP 工具索引

| 触发词 | MCP 工具函数 | 工具文件 | 协议文档 |
| :--- | :--- | :--- | :--- |
| `[存档]` | `force_architect_save` | `tools/architect.py` | `SAVE_PROTOCOL.md` |
| `[读档]` | `force_architect_read` | `tools/architect.py` | `SAVE_PROTOCOL.md` |
| `[清理]` | `force_garbage_collection` | `tools/architect.py` | `SAVE_PROTOCOL.md` |
