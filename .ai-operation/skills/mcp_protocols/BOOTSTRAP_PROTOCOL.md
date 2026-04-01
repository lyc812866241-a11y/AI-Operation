# Bootstrap 写入协议 (Bootstrap Write Protocol)

## 触发条件

当 `.ai-operation/skills/project-bootstrap/SKILL.md` 的 **Phase 4** 执行时，AI 必须调用此工具。

**以下行为被明确禁止：**
- 直接用文件编辑工具覆写 `.ai-operation/docs/project_map/` 下的任何文件
- 在 `user_confirmed=False` 的情况下调用此工具
- 在任意参数中保留 `[TODO]` 占位符

---

## 核心行为：合并（Merge），不是覆写（Overwrite）

**重要变更**：此工具采用**模板合并**策略，而非全覆写。

对于 3 个静态文件（projectbrief、systemPatterns、techContext）：
1. 读取现有模板文件（包含填写规范、示例、`[待填写]` 占位符）
2. 找到所有 `[待填写...]` 占位符
3. 用 AI 生成的内容**逐一替换**占位符
4. **保留**模板结构（标题、填写规范、示例）
5. 未填的 section 保留 `[待填写]` 占位符

**这意味着：**
- 大项目可以**分批初始化**（第一次填 3 个 section，下次补剩下的）
- AI 遗漏的 section 不会丢失模板指导语
- 可以多次运行 `[初始化项目]` 逐步完善

---

## 参数说明

| 参数 | 类型 | 说明 |
| :--- | :--- | :--- |
| `projectbrief_content` | string | 按 `===SECTION===` 分隔的各 section 填充内容。每段内容对应一个 `[待填写]` 占位符，按顺序替换。使用 `SKIP` 跳过某个 section 或整个文件。 |
| `systemPatterns_content` | string | 同上格式 |
| `techContext_content` | string | 同上格式 |
| `activeContext_focus` | string | 当前最紧迫任务（一句话）。使用 `SKIP` 跳过。 |
| `progress_initial` | string | 当前待办事项列表。使用 `SKIP` 跳过。 |
| `user_confirmed` | bool | **必须为 `True`** |

### 参数格式示例

```
# 填写 projectbrief.md 的 4 个 section：
projectbrief_content = """
全自动短视频生产系统，让一个人能以团队的效率完成全流程
===SECTION===
| 指标名称 | 目标值 | 当前值 | 备注 |
|---|---|---|---|
| 单条视频耗时 | < 20分钟 | ~4小时 | 含全流程 |
===SECTION===
- **用户群体**：独立创作者
- **核心场景**：提供素材，系统自动剪辑
===SECTION===
- 不做内容创意生成
- 不做多平台分发
"""

# 跳过整个文件：
systemPatterns_content = "SKIP"

# 跳过某些 section（第 2 个不填）：
techContext_content = """
| 类别 | 技术选型 | 版本 |
|---|---|---|
| 语言 | Python | 3.11+ |
===SECTION===
SKIP
===SECTION===
SKIP
===SECTION===
- Python 3.11+
- FFmpeg 6.x
"""
```

---

## 三道内置门控

| 门控 | 检查内容 | 拒绝时的返回信息 |
| :--- | :--- | :--- |
| Gate 1 | `user_confirmed == True` | `REJECTED: user_confirmed must be True.` |
| Gate 2 | 所有参数均不含 `[TODO]` | `REJECTED: {field_name} still contains [TODO] placeholders.` |
| Gate 3 | `.ai-operation/docs/project_map/` 目录存在 | `FAILED: Directory does not exist.` |

---

## 验证标准

工具返回的 merge report 格式：
```
SUCCESS: Project bootstrap merge complete.

Merge report:
  projectbrief.md: MERGED (4 filled, 0 kept as template)
  systemPatterns.md: SKIPPED
  techContext.md: MERGED (2 filled, 2 kept as template)
  activeContext.md: GENERATED
  progress.md: GENERATED

Remaining [待填写] placeholders: 5
Re-run [初始化项目] to fill remaining sections.
```

- `MERGED (X filled, Y kept)` — X 个占位符被替换，Y 个保留
- `SKIPPED` — 整个文件未修改
- `GENERATED` — 动态文件全量生成
- `Remaining [待填写]: N` — 全局还有 N 个未填的占位符

---

## 与其他协议的关系

本协议可在项目生命周期内**多次执行**，逐步填充大项目的所有 section。
当所有 `[待填写]` 占位符都被替换后（Remaining = 0），初始化视为完成。
后续更新由 `[存档]` 指令和 `SAVE_PROTOCOL.md` 负责。
