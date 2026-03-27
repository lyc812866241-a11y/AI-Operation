# 任务技术规格说明书 (Task Specification)

> **[用途说明]**
> 本文件由 **Lead Agent (Architect 模式)** 在理解用户需求后生成，是交由 **Worker Agent (Code 模式)** 执行的唯一凭证。
> 必须在用户审批通过后，Worker Agent 才能开始编码。禁止在没有此文件的情况下直接修改核心代码。

---

## 1. 任务目标 (Task Goal)

[TODO: 用一句话概括本次任务的核心目的。]

## 2. 影响范围 (Scope & Impact)

[TODO: 列出本次任务将影响的系统模块或管线节点。]

- **涉及模块**：
- **核心逻辑变更**：

## 3. 需修改 / 创建的文件清单 (Files to Modify / Create)

[TODO: 精确列出所有需要变动的文件及其具体变动内容。]

1. `[path/to/file.py]`：[描述变动，如"添加 xxx 函数以支持 yyy"]
2. `[path/to/file.json]`：[描述变动，如"新增 zzz 字段"]

## 4. 技术约束与边界 (Technical Constraints & Boundaries)

[TODO: 列出在实现过程中必须遵守的限制条件，防止 Worker Agent 自由发挥。]

- **依赖限制**：[如"仅使用内置库，不引入新依赖"]
- **性能要求**：[如"处理时间不超过 X 秒"]
- **隔离要求**：[如"测试文件必须输出到 tests/output/ 目录"]

## 5. 验收标准 (Acceptance Criteria)

[TODO: 定义如何验证任务已成功完成，必须是具体可执行的测试步骤。]

1. [验证步骤 1，如"运行 `python tests/test_xxx.py`，输出应包含 'success'"]
2. [验证步骤 2，如"检查 `data/output.json` 是否包含预期字段"]

---

**审批状态 (Approval Status)：** `[待审批 Pending]`

> 注：只有状态变更为 `已批准 Approved` 后，Worker Agent 才允许进入 Code 模式执行。
