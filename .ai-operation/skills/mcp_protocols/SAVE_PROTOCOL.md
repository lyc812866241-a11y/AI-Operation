# [存档] / [读档] / [清理] MCP 执行协议

## 触发条件

| 用户指令 | 必须调用的 MCP 工具 |
| :--- | :--- |
| `[存档]` | `aio__force_architect_save` |
| `[读档]` | `aio__force_architect_read` |
| `[清理]` | `aio__force_garbage_collection` |

---

## [存档] 协议：`aio__force_architect_save`

### 禁止行为（铁律）
- **禁止**手动编辑 `.ai-operation/docs/project_map/` 下的任何文件
- **禁止**手动运行 `git commit` 或 `git add`
- **禁止**跳过任何参数
- **禁止**用模糊的摘要替代具体细节（必须包含精确的文件路径、函数名、变量名）
- **禁止**写裸 `NO_CHANGE` —— 必须写 `NO_CHANGE_BECAUSE: [具体理由]`

> **WHY:** 裸 NO_CHANGE 让 AI 可以无脑跳过文件。加了 BECAUSE 后，AI 必须对每个文件做一次"这个文件是否需要更新"的思考。如果理由写不出来，说明你可能遗漏了更新。

### 五个必填参数规范

> 议题 #010 重组：projectbrief_update 已删除。项目愿景在 design.md (§1 根锚 / §2 反向边界),由 project-design 工具维护。

**`systemPatterns_update`**
- 填写条件：发现了新的架构规则、新增了管线节点、定义了新的 Tool Contract、修改了目录协议
- 有变更时：必须包含具体的文件路径、函数名或规则描述
- 无变更时：`NO_CHANGE_BECAUSE: 本次会话只修改了 [具体模块] 的内部实现，未改变模块边界或接口`

**`techContext_update`**
- 填写条件：引入了新的依赖库、发现了技术约束、修改了 API 接口、更换了技术方案
- 有变更时：`新增依赖：[库名 版本]；约束：[具体描述]`
- 无变更时：`NO_CHANGE_BECAUSE: 未引入新依赖，未发现新的技术坑点`

**`activeContext_update`**（必填，不允许 `NO_CHANGE`）
- 必须包含：当前正在做什么、刚刚完成了什么、下一步立刻要做什么
- 填写格式：
  ```
  当前焦点：[具体任务描述]
  刚完成：[具体完成内容，含文件路径]
  下一步：[具体的下一个动作]
  ```


**`lessons_learned`**（必填，MCP 工具拒绝空值）
- 这是框架自进化机制的核心入口。每次存档时 AI 必须回顾本次会话，提取经验教训。
- 写入目标：`.ai-operation/docs/project_map/corrections.md`（项目经验库）
- 填写格式：每行一条，以 `- ` 开头
  ```
  - FFmpeg 输出路径含空格会静默失败 → 所有路径必须用引号包裹
  - 用户偏好：PR 合并时用 squash，不要 merge commit
  - AI 遗漏了 plugins/ 目录的已完成模块
  ```
- 经验类型包括：
  - **技术坑点**：代码层面的 bug、兼容性问题、API 限制
  - **用户偏好**：用户纠正的行为习惯、代码风格、流程偏好
  - **AI 纠错**：AI 判断失误后被用户纠正的记录
  - **架构决策**：为什么选 A 不选 B 的理由
- 仅当本次会话确实没有任何新发现时，填写 `NONE`
- **进化链路**：corrections.md 中同类经验 COUNT >= 3 → 自动升级到 conventions.md 成为项目契约（由 architect.py 代码执行，非文本指令）

---

## [读档] 协议：`aio__force_architect_read`

无需参数。调用后 AI 必须：
1. 将工具返回的全部内容完整阅读（受 4KB/文件、12KB 总量预算控制）
2. 输出一份宏观状态报告，包含：当前项目阶段、当前焦点、待办优先级

---

## [清理] 协议：`aio__force_garbage_collection`

执行分两步：
1. 先以 `confirm=False` 调用，获取待删除文件列表，展示给用户
2. 用户确认后，以 `confirm=True` 调用，执行实际删除
3. 禁止跳过用户确认步骤直接删除
