---
name: state-checkpoint
description: 议题 #002 The Engine 的物质执行器。在 6 个语义事件发生时 OVERWRITE 更新 activeContext.md 快照,使被中断会话在 2 分钟内可恢复。
when: ["完成子步骤", "完成 taskSpec", "做出关键决策", "发现卡点", "解决卡点", "决策升级到 conventions"]
paths: [".ai-operation/docs/project_map/activeContext.md"]
tools: ["Read", "Write", "Edit"]
---

# [状态快照] — State Checkpoint

> 议题 #002 **The Engine**(思维链连续性)的物质执行器。
> activeContext = 当前可执行状态的**完整快照**。**OVERWRITE**,不 APPEND。

---

## 触发时机(6 个语义事件)

| 事件 | 强制级别 | 更新哪部分 |
|---|---|---|
| 完成 taskSpec 子步骤 | **必须** | § 2 子步骤 + § 5 下一动作 |
| 完成 taskSpec | **必须**(MCP 兜底) | § 1 边界切换 + 重置 § 2/3/4/5 |
| 做出关键决策 | **必须** | § 3 add 一条 |
| 发现卡点 | 强烈建议 | § 4 add |
| 解决卡点 | 强烈建议 | § 4 remove |
| 决策升级到 conventions/design | **必须** | § 3 remove(防膨胀) |

**判断式**(挂工作台):
> "现在中断,1 小时后回来,看 activeContext 能 2 分钟接续吗?"
> - 能 → 不更新
> - **不能 → 立即更新**

---

## 写入语义

- **OVERWRITE 整个文件**,不 APPEND
- activeContext 是当前快照,不是历史日志(历史归 `progress.md`)
- **≤ 80 行硬上限**——超过 = 没及时清理过期决策/已解卡点 → 触发审视

---

## 更新流程

1. **Read** 当前 `activeContext.md`
2. 根据触发事件,合并 / 修改 / 删除字段:
   - 完成子步骤 → 更新 § 2(子步骤进度) + § 5(下一动作)
   - 完成 taskSpec → § 1 切换上一个/当前/下一个,清空 § 2/3/4/5
   - 关键决策 → § 3 add 一条(格式:`决策 — 理由`)
   - 卡点 → § 4 add / remove
   - 决策升级 → § 3 remove(防膨胀)
3. 更新 `**最后更新**` 时间戳为当前 ISO 时间
4. **OVERWRITE** 写回文件

---

## 反模式(绝不该触发)

- ❌ 每次文件读 / grep / 搜索
- ❌ 工具调用本身
- ❌ 思考推理过程(归对话,不归快照)
- ❌ 短暂方向讨论(没有真正决策时)
- ❌ 失败尝试(除非升级为卡点)

→ 这些事件触发更新会让 activeContext 膨胀成对话日志,失去快照语义。

---

## 字段写入约束

| 字段 | 约束 | 例子 |
|---|---|---|
| § 5 下一动作 | 必须含**动词 + 具体对象** | ✅ `打开 src/cache.py:25,实现 _make_cache_key(user_id, endpoint)` |
| § 5 拒绝接受 | 泛话 | ❌ `继续开发` `修 bug` `继续优化` |
| § 3 决策 | 每条必须有"决策 + 理由"二元结构 | ✅ `用 LRU,maxsize=1024 — 理由:内存压力可控` |
| 时间戳 | ISO `YYYY-MM-DD HH:MM` | `2026-05-06 14:23` |

---

## 与 MCP 工具的兜底强制(后续工程)

- `aio__force_taskspec_complete`:taskSpec 完成时**强制**触发本 skill,不更新 → 拒绝完成
- `aio__force_architect_save`:[存档] 时验证 activeContext 时间戳在 1 小时内,过期 → 拒绝存档

(这两个是后续代码层增强,文档规范先行。)
