---
name: test-driven-development
description: TDD 强制协议。实现新功能或修复 Bug 前，必须先写失败测试。
when: ["新功能", "feature", "实现", "implement", "修复", "fix"]
paths: ["tests/**", "src/**", "*.py", "*.ts"]
tools: ["Bash", "Read", "Write", "Edit"]
---

# 测试驱动开发规范 (Test-Driven Development)

> **触发条件**：实现任何新功能或修复任何 Bug 时，在编写实现代码之前，必须先执行本规范。
>
> **铁律**：`NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST`
> 先写了代码再写测试？删掉代码，重新开始。没有例外。

---

## 何时使用

**以下情况必须使用 TDD：**
- 新功能开发
- Bug 修复
- 重构
- 行为变更

**以下情况可例外（需与用户确认）：**
- 一次性原型验证
- 自动生成的代码
- 配置文件

"这次跳过 TDD"的念头出现时，停下来。那是在给自己找借口。

---

## RED-GREEN-REFACTOR 循环

```
RED（红）→ 写一个失败的测试
    ↓
验证它确实失败（且失败原因正确）
    ↓
GREEN（绿）→ 写最少的代码让测试通过
    ↓
验证它确实通过（且其他测试未被破坏）
    ↓
REFACTOR（重构）→ 清理代码，保持绿色
    ↓
回到 RED，进入下一个测试
```

---

## Phase 1：RED — 写失败的测试

写一个最小化的测试，描述期望的行为。

**好的测试：**
```python
def test_retries_failed_operation_three_times():
    attempts = 0
    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("fail")
        return "success"

    result = retry_operation(operation)

    assert result == "success"
    assert attempts == 3
```
名称清晰，测试真实行为，只测一件事。

**不好的测试：**
```python
def test_retry_works():
    mock = Mock(side_effect=[Exception(), Exception(), "success"])
    retry_operation(mock)
    assert mock.call_count == 3
```
名称模糊，测试的是 Mock 行为而不是真实代码。

**测试必须满足：**
- 只测一个行为
- 名称清晰描述期望行为
- 使用真实代码（非必要不用 Mock）

## Phase 2：验证 RED — 亲眼看到它失败

**这一步是强制的，永远不能跳过。**

运行测试，确认：
- 测试失败（不是报错）
- 失败信息符合预期
- 失败原因是"功能缺失"，而不是拼写错误

**测试直接通过？** 说明你在测试已有行为，修改测试。
**测试报错？** 修复错误，重新运行，直到它正确地失败。

如果你没有亲眼看到测试失败，你不知道这个测试是否真的在测正确的东西。

## Phase 3：GREEN — 写最少的代码

写最简单的、能让测试通过的代码。

**好的实现：**
```python
def retry_operation(fn, max_retries=3):
    for i in range(max_retries):
        try:
            return fn()
        except Exception:
            if i == max_retries - 1:
                raise
```
刚好够用。

**不好的实现：**
```python
def retry_operation(
    fn,
    max_retries=3,
    backoff_strategy="linear",
    on_retry=None,
    timeout=None,
    # YAGNI
):
    ...
```
过度设计，你并不需要这些。

不要添加功能，不要重构其他代码，不要"顺手改进"超出测试范围的东西。

## Phase 4：验证 GREEN — 亲眼看到它通过

**这一步是强制的。**

运行测试，确认：
- 新测试通过
- 其他测试仍然通过
- 输出干净（无错误、无警告）

**测试失败？** 修复代码，不要修改测试。
**其他测试失败？** 立刻修复。

## Phase 5：REFACTOR — 清理代码

只在绿色状态下重构：
- 消除重复
- 改善命名
- 提取辅助函数

保持测试绿色。不要添加新行为。

---

## 测试质量标准

| 质量维度 | 好的测试 | 不好的测试 |
|---|---|---|
| **最小化** | 只测一件事；名称里有"and"？拆分它 | `test_validates_email_and_domain_and_whitespace` |
| **清晰** | 名称描述期望行为 | `test_1`、`test_works` |
| **表达意图** | 展示代码应该如何被使用 | 掩盖代码的设计意图 |

---

## 与框架的集成点

**Bug 修复时**：先写一个能复现 Bug 的失败测试，再走 TDD 循环。测试既证明了修复有效，又防止了回归。

**与 `systematic-debugging` 的协作**：`systematic-debugging` 的 Phase 4 第 1 步要求"先创建失败测试"，此时调用本规范的 RED 阶段。两个技能在 Bug 修复场景下形成完整闭环：
```
发现 Bug → systematic-debugging（找根因）→ test-driven-development（写测试 → 修复 → 验证）
```

**与 `taskSpec.md` 的协作**：Worker Agent 执行 taskSpec 中的每一个文件变更时，必须先为该变更写失败测试，再实施变更。

---

## 常见借口对照表

| 借口 | 现实 |
|---|---|
| "太简单了，不需要测试" | 简单代码同样会出错。写测试只需 30 秒。 |
| "我之后再写测试" | 事后写的测试会立刻通过，什么都证明不了。 |
| "事后写测试效果一样" | 事后测试回答"这段代码做什么"；先写测试回答"这段代码应该做什么"。 |
| "我已经手动测试过了" | 手动测试是临时的，没有记录，无法重复运行。 |
| "删掉 X 小时的工作太浪费了" | 沉没成本谬误。保留无法信任的代码才是真正的浪费。 |
| "留着做参考，然后先写测试" | 你会去"调整"它。那就是事后写测试。删掉就是删掉。 |
| "需要先探索一下" | 可以。但探索完之后扔掉，从 TDD 重新开始。 |
| "TDD 会让我变慢" | TDD 比调试更快。务实 = 先写测试。 |

---

## 完成前验证清单

在标记工作完成之前：

- [ ] 每个新函数/方法都有对应的测试
- [ ] 亲眼看到每个测试在实现前失败
- [ ] 每个测试的失败原因符合预期（功能缺失，而非拼写错误）
- [ ] 写了最少的代码让每个测试通过
- [ ] 所有测试通过
- [ ] 输出干净（无错误、无警告）
- [ ] 测试使用真实代码（非必要不用 Mock）
- [ ] 边界情况和错误路径已覆盖

无法全部勾选？说明你跳过了 TDD。重新开始。

---

## 卡住时的对策

| 问题 | 解决方案 |
|---|---|
| 不知道怎么测试 | 先写你希望的 API 调用方式，再写断言，再请求帮助 |
| 测试太复杂 | 设计太复杂。简化接口。 |
| 必须 Mock 所有东西 | 代码耦合度太高。使用依赖注入。 |
| 测试 setup 代码量巨大 | 提取辅助函数。仍然复杂？简化设计。 |
