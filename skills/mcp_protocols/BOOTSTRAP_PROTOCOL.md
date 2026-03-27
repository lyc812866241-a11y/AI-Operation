# Bootstrap 写入协议 (Bootstrap Write Protocol)

## 触发条件

当 `skills/project-bootstrap/SKILL.md` 的 **Phase 4** 执行时，AI 必须调用此工具。

**以下行为被明确禁止：**
- 直接用文件编辑工具覆写 `docs/project_map/` 下的任何文件
- 在 `user_confirmed=False` 的情况下调用此工具
- 在任意参数中保留 `[TODO]` 占位符

---

## 必填参数说明

| 参数 | 类型 | 说明 |
| :--- | :--- | :--- |
| `projectbrief_content` | string | `projectbrief.md` 的完整新内容，不含 `[TODO]` |
| `systemPatterns_content` | string | `systemPatterns.md` 的完整新内容，不含 `[TODO]` |
| `techContext_content` | string | `techContext.md` 的完整新内容，不含 `[TODO]` |
| `activeContext_focus` | string | 用户在 Phase 3.4 回答的当前最紧迫任务（一句话） |
| `progress_initial` | string | 当前待办事项列表（Markdown 格式） |
| `user_confirmed` | bool | **必须为 `True`**。只有在用户明确表示"可以写入"后才能设置为 True |

**不确定的内容使用 `[待确认]` 标注，而非 `[TODO]`。**

---

## 三道内置门控

工具在执行写入前会自动校验以下条件，任一不满足则返回 `REJECTED`：

| 门控 | 检查内容 | 拒绝时的返回信息 |
| :--- | :--- | :--- |
| Gate 1 | `user_confirmed == True` | `REJECTED: user_confirmed must be True.` |
| Gate 2 | 所有参数均不含 `[TODO]` | `REJECTED: {field_name} still contains [TODO] placeholders.` |
| Gate 3 | `docs/project_map/` 目录存在 | `FAILED: Directory docs/project_map does not exist.` |

---

## 验证标准

工具执行成功的标志：

- 返回值以 `SUCCESS` 开头
- `docs/project_map/` 下 5 个文件均已被覆写（无 `[TODO]` 残留）
- Git commit 已自动创建（commit message 格式：`chore: bootstrap project map [YYYY-MM-DD HH:MM]`）

工具返回 `PARTIAL SUCCESS` 时：文件已写入但 git commit 失败，需手动执行：
```bash
git add docs/project_map/
git commit -m "chore: bootstrap project map"
```

---

## 与其他协议的关系

本协议仅在项目生命周期内执行**一次**。初始化完成后，project_map 的后续更新由 `[存档]` 指令和 `SAVE_PROTOCOL.md` 负责。
