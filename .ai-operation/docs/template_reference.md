# Project Map 填写参考 (Template Reference)

> 本文件包含每个 project_map 文件的详细填写规范和示例。
> AI 在执行 [初始化项目] 时参考此文件，日常开发不需要读。
> 不计入 12KB 提示词预算。

---

## projectbrief.md 填写规范

### 1. 核心愿景
一两句话，描述"这个项目做成了，世界有什么不同"。不要写技术实现，写业务结果。
示例：`全自动短视频生产系统，让一个人能以团队的效率完成从素材到成片的全流程，单条视频生产时间从 4 小时压缩到 20 分钟。`

### 2. 核心业务指标
必须可量化，必须有目标值。不能写"提升效率"，要写"从 X 降低到 Y"。

| 指标名称 | 目标值 | 当前值 | 备注 |
|---|---|---|---|
| 示例：单条视频生产耗时 | < 20 分钟 | ~4 小时 | 含素材处理到导出 |

### 3. 目标用户与使用场景
描述"谁在什么情况下用这个系统，输入是什么，输出是什么"。

### 4. 明确不做的事
明确写出"这个项目不负责什么"，防止 AI 自作主张扩展范围。

---

## systemPatterns.md 填写规范

### 1. 系统定性
格式：`[系统类型] — [核心用途] — 当前版本：[vX]`
类型：`纯流水线型` / `纯智能体型` / `混合型（状态机驱动）` / `工具集型`

### 2. 数据结构字典
列出所有跨模块传递的核心数据结构，标注定义位置（文件路径 + 行号）。

### 3. 可用单元清单
状态：✅ 已完成 🚧 开发中 ❌ 未开始。AI 必须优先复用 ✅ 状态的单元。

### 4. 数据流
用箭头描述数据在各单元之间的流转路径。

### 5. 架构约束
从代码 assert/raise/TODO/FIXME 中提取，每条标注代码依据。

---

## conventions.md 填写规范（二阶契约）

> **只存结构性规则** — 防止一类问题反复出现的契约。
> 具体踩坑教训（如"禁删 API 产出文件"）不放这里，放 `corrections/{key}.md`（一阶经验）。
> 判断口诀：防一类 → conventions；防同一个 → corrections。

### 1. 命名契约
明确每种命名场景的规则。格式：`[场景]: [规则]`
示例：
- API 路由: kebab-case (`/user-profile`, `/order-history`)
- 数据库字段: snake_case (`created_at`, `user_id`)
- React 组件: PascalCase (`UserCard`, `OrderList`)
- Python 函数: snake_case (`get_user_profile`)
- 常量: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`)

### 2. API / 数据契约
统一的请求/响应格式，确保所有接口一致。
示例：`所有 API 统一返回 { code: int, message: str, data: any }，错误码 4xx 客户端错误 / 5xx 服务端错误`

### 3. UI 契约（无前端项目写 N/A）
把设计决策写成精确的 token，AI 生成 UI 时会自动对齐。
示例：
- 网格: 8px base
- 间距阶梯: 4 / 8 / 12 / 16 / 24 / 32 / 48
- 圆角: 4px (按钮) / 8px (卡片) / 16px (模态框)
- 主色: #2563EB, 成功: #16A34A, 错误: #DC2626

### 4. 错误处理契约
统一的错误处理模式，避免每个模块各写各的。
示例：`后端: 所有异常统一 try-catch 到 middleware，返回标准格式。前端: toast 提示 3 秒自动消失。`

### 5. 代码风格契约
从代码库已有风格提取，写明边界。
示例：`单文件不超过 300 行 / 函数不超过 40 行 / import 分三段：stdlib → third-party → local`

---

## techContext.md 填写规范

### 1. 核心技术栈
只列不可替换的技术选型，标注"为什么不能换"。

### 2. 外部依赖
列出所有外部服务的关键限制（速率、路径、内存等）。

### 3. 已知坑点
格式：`**[坑点名称]**：[表现] → [正确做法]`
每踩一次新坑通过 [存档] 追加。

### 4. 环境依赖
运行项目必须满足的条件（Python 版本、CUDA、API key 等）。

---

## save 工具写入语义（必读）

不同参数走不同写入策略，**搞混会直接丢数据**。

### 静态文件（projectbrief / systemPatterns / techContext / conventions）

三种模式，按优先级：

1. **精准增量**（首选）—— 用 `===SECTION===` 分隔符
   ```
   ===SECTION===
   系统定性
   新定性内容
   ===SECTION===
   架构约束
   新约束内容
   ```
   - title 忽略 `N.` 数字前缀，两边都会自动 strip
   - 零匹配 → REJECTED（带实际 section 清单），**不会偷偷改成 no-op**

2. **显式全替换**—— 用 `FULL_OVERWRITE_CONFIRMED:` 前缀
   ```
   FULL_OVERWRITE_CONFIRMED:
   # 全新文件内容
   ...
   ```
   - 仅在你真要重写整份文件时用

3. **空/新文件**—— 纯文本
   - 只在文件不存在或无任何 `##` section 时允许
   - 已有 section 结构的文件传纯文本 → **REJECTED**（上面规则 2 的保护）

### 动态文件（activeContext / progress）

始终 APPEND（追加到末尾）。

### inventory 清单

- **`save(inventory_update=...)`** = **FULL OVERWRITE**，替换整个 inventory.md
- **`aio__inventory_append(category, item)`** = **增量追加**，首选这个

新增 1-2 条资产时**千万不要**用 save 的 `inventory_update`——会清空整个清单。
