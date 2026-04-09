---
name: consolidate
description: 整理 project_map 文件 — 与用户对齐后清理、压缩、分级。触发词："整理"、"清理文档"、"project_map 太大了"。
---

# [整理] — Project Map 整理与校准

## 目的

日常 [存档] 用 append 模式积累内容，随着时间推移 project_map 文件会膨胀、有重复段落、有过时内容。[整理] 是一次带**人在回路**的深度清洁：AI 读取所有文件，逐个向用户展示内容，用户确认后 overwrite 为干净版本。超限部分拆到 details/ 分级指针。

**与 [存档] 的区别**：
- [存档] = 高频、AI 自己做、append 只加不减
- [整理] = 低频、用户主动触发、overwrite + 分级

## 前置条件

- project_map 已初始化（非空白状态）
- 建议在以下时机触发：
  - 连续存档 5+ 次后
  - 任何 project_map 文件超过 8KB 时（[读档] 会警告）
  - 大版本完成后
  - 发现 project_map 内容有过时或重复时

---

## 执行流程

### Step 1：全量读取

读取 project_map 目录下所有文件，记录每个文件的大小：

```bash
wc -c .ai-operation/docs/project_map/*.md
ls -la .ai-operation/docs/project_map/details/ 2>/dev/null
```

### Step 2：逐文件校准

**按以下顺序逐个文件向用户展示当前内容，等待确认：**

#### 2.1 activeContext.md（动态文件）

向用户展示当前内容，提问：
- "这是当前焦点的描述，还准确吗？"
- "有没有过时的段落可以删掉？"

用户确认后 → **overwrite** 为干净版本。

#### 2.2 progress.md（动态文件）

向用户展示，提问：
- "已完成列表有没有可以归档的旧条目？"
- "待办列表还准确吗？"

用户确认后 → **overwrite**。已完成的旧条目可以移到 details/ 归档。

#### 2.3 corrections.md（动态文件）

向用户展示每条经验，逐条提问：

- "这条还有效吗？"
  - 无效 → 删掉
  - 有效 → 继续问：

- "要固化吗？"
  - **固化为一阶机制**（只对本项目生效）→ 写入 `conventions.md`，从 corrections 删掉
  - **固化为二阶机制**（对所有项目生效）→ 记录下来，提醒用户去更新框架的 SKILL.md 或 MCP 代码
  - **暂不固化** → 保留在 corrections 里

用户确认后 → **overwrite**。

#### 2.4 systemPatterns.md（静态文件）

向用户展示，提问：
- "模块列表和文件路径还对吗？（对比实际代码）"
- "有没有写了详细描述应该改成指针格式的？"

验证方式：对 systemPatterns 里提到的文件路径逐个 `ls` 确认存在。

用户确认后 → **overwrite**。

#### 2.5 techContext.md（静态文件）

向用户展示，提问：
- "技术栈有变化吗？"
- "坑点列表还适用吗？有新的要加吗？"

用户确认后 → **overwrite**。

#### 2.6 conventions.md（静态文件）

向用户展示，提问：
- "这些约定还在执行吗？"
- "有没有实际已经违反了的约定要删掉？"

用户确认后 → **overwrite**。

#### 2.7 inventory.md（静态文件）

向用户展示，提问：
- "资产清单和实际代码库一致吗？"

验证方式：对 inventory 里的模块路径抽样 `ls` 确认存在。

用户确认后 → **overwrite**。

#### 2.8 projectbrief.md（静态文件）

向用户展示，提问：
- "核心愿景有变化吗？"

通常不变，快速确认即可。

### Step 3：分级处理

对所有确认后的文件检查大小：
- **≤ 8KB** → 保持原样
- **> 8KB** → 与用户讨论哪些段落拆到 details/ 子文件，主文件留指针

```
> → [详见 details/systemPatterns__模块清单.md]
```

### Step 4：提交

所有文件确认后：

```bash
git add .ai-operation/docs/project_map/
git commit --no-verify -m "chore: [整理] project_map cleanup and consolidation"
```

### Step 5：汇报

向用户展示整理结果：
```
[整理] 完成：
- activeContext.md: 3826 → 694 字符（清理重复段落）
- progress.md: 5154 → 1645 字符（归档旧条目）
- systemPatterns.md: 无变化
- 2 个段落拆分到 details/
```

---

## 规则

- **每个文件必须经过用户确认才能 overwrite**。不能跳过确认直接清理。
- **不删除信息，只转移**。旧内容移到 details/ 或 git 历史，不凭空删除。
- **文件路径必须验证**。systemPatterns 和 inventory 里的路径要 `ls` 确认存在。
- **整理后必须跑 [读档]**。让用户验证整理结果。
