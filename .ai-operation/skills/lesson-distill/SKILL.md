---
name: lesson-distill
description: 议题 #005 求导思维的物质执行器。把"刚学到的教训"按 scope 分类存到正确位置(项目级 corrections / 跨项目级 wisdom)。
when: ["犯错", "被纠正", "学到教训", "记录经验", "lesson", "捕获教训", "踩坑"]
paths: [".ai-operation/docs/project_map/corrections.md", ".ai-operation/docs/project_map/corrections/", ".ai-operation/wisdom.md"]
tools: ["Read", "Write", "Edit"]
primary_artifact: .ai-operation/docs/project_map/corrections.md
---
> ⚠️ **议题 #013 物理强制(必读)**:本 skill 修改 corrections.md(项目级一阶经验载体)。议题 #013 强制:必须用 aio__skill_invoke / aio__skill_complete 包裹执行,完成时验证 corrections.md 真的被修改过。
>
> 执行流程:`aio__skill_invoke("lesson-distill")` → 走完本 skill 所有步骤 → `aio__skill_complete("lesson-distill")`。
> 完成时若 primary_artifact 未被修改,锁不释放。


# [教训沉淀] — Lesson Distill

> 议题 #005 求导思维 + 议题 #009 scope-based 知识分类的物质执行器。

---

## 触发时机

出现以下情况之一时,**立刻**走本 skill,**不要等到 [存档]**:

- 你犯了错 / 被用户纠正
- 发现一条值得记住的教训
- 发现某个隐性约定(过去几次都这么做但没记下来)

---

## 知识分级(scope-based,议题 #009)

> **type 边界 = scope 边界**。**scope 不同的 type 不可互升**。

存经验前,先问 **"这条的 scope 是什么?"**——决定它的 type,决定它的家:

| Type | Scope | 存哪里 | 内容 |
|---|---|---|---|
| **一阶 项目级** | 当前项目 | `corrections.md`(内部分 §1/§2/§3) | 项目特定的所有经验 / 规则 / 习惯 |
| **二阶 跨项目** | **所有项目** | `.ai-operation/wisdom.md` | 通用方法论、普适原则、跨项目智慧 |

### 一阶内部的三段(同 scope,不同形态)

| 段 | 形态 | 写入模式 | 例子 |
|---|---|---|---|
| **§1 项目契约** | 声明式规则(防一类问题) | section-merge / overwrite | "API 路由用 kebab-case"、"统一返回 `{code, data}`" |
| **§2 具体踩坑** | 经验式日志(防同一个坑) | append | "钉钉 userId 必须数字"、"删 .pyc 前先确认" |
| **§3 习惯指令** | 指令式约束 | append | "提交前跑 lint"、"PR 必须关联 issue" |

---

## 判断口诀(scope-based)

### Step 1:这条的 scope 是什么?

**Q1: 这条只对当前项目有效吗?**
- 是 → 一阶,进 `corrections.md`,继续 Step 2
- 否,所有项目都成立 → 二阶,进 `wisdom.md`,跳到 Step 3

### Step 2:一阶内部分到哪一段?

- 是结构性规则(防一类问题) → **§1 项目契约**
- 是具体踩坑(防同一个坑) → **§2 具体踩坑**(简短记一行,详细情况存 `corrections/{key}.md`)
- 是 AI 操作习惯 / 指令 → **§3 习惯指令**

### Step 3:二阶必须先经过"普适拷问"

写入 wisdom 前,问自己:
- 这条在反例项目里也成立吗?
- 不同语言 / 不同领域 / 不同规模 都适用吗?
- 经得起跨项目反例检验吗?

经得起 → 写入 wisdom.md
经不起 → 退回 corrections,标注"待观察是否普适"

---

## 求导提炼步骤(议题 #005)

| 阶 | 步骤 | 落地位置 |
|---|---|---|
| **一阶** | 这次发生了什么具体问题? | `corrections/{key}.md`(详细版本) |
| **二阶** | 为什么会发生? 根本原因? | 同一 corrections 条目里写明 |
| **三阶** | 以后避免这个根因的机制? | 如果是防一类问题 → 提炼到 corrections §1(项目内抽象升级,**人主动判断**) |
| **四阶** | 这个机制对其他项目也成立吗? | 经得起拷问 → wisdom.md(**scope 跃迁,只能人主动**) |

**三阶 → 四阶之间是 scope 跃迁,不是简单抽象升级**(议题 #005 v2)。

---

## 铁律(议题 #009)

1. **一阶 ≠ 二阶,无法互升** —— type 不可跨 scope
2. **wisdom 只能由人主动写入** —— "corrections × N 次自动升级到 wisdom" 已废除
3. **同 scope 内 abstraction 升级允许,但需人主动判断**:
   - §2 累积多次 → 人决定是否提炼到 §1(项目内规则)
   - 不再是"× 3 次自动升级"——是**人 + AI 协同判断**
4. **立即写入,不要拖到 [存档]** —— 记忆衰减比想象快
5. **二阶契约要写得能防"一类"问题** —— 只能防"这一个"就还是 §2 一阶具体
