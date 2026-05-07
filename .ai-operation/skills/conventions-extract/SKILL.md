---
name: conventions-extract
description: 从已有代码反推项目级契约(命名/API/风格/错误处理),产出 corrections.md §1 项目契约段的草稿。接管已有项目时关键。
when: ["提取项目契约", "反推契约", "extract conventions", "convention extract", "扫码反推"]
paths: ["src/**", "*.py", "*.ts", "*.js", "*.go", "*.rs"]
tools: ["Glob", "Grep", "Read", "Bash"]
---

# [契约提取] — Conventions Extract

> 接管已有项目时,代码里**已经存在事实约定**(命名风格、API 格式、代码风格),但 corrections.md §1 项目契约段是空的。
> 这个 skill 扫描代码自动提炼这些事实约定,产出**草稿** → 用户审核 → 写入 corrections §1。

---

## 触发场景

- 接管已有代码库,corrections §1 还没填
- 重大重构后,验证当前代码事实契约跟 §1 声明是否漂移
- 周期性审计(类似 omm-scan 的"反漂移"用途)

## 跟其他 skill 的边界

| Skill | 干啥 | 跟本 skill 区别 |
|---|---|---|
| `omm-scan` | 提取**架构**(模块 / 数据流) | 这个提**契约**(命名 / 风格 / API 格式) |
| `lesson-distill` | 把单条新教训分类入档 | 这个**批量**反推已有约定 |
| `project-bootstrap` | 立项时主动设计契约 | 这个用于**接管阶段**反推已有契约 |

---

## 协议步骤

### Step 1:扫描技术栈

读项目根:
- `package.json` / `pyproject.toml` / `requirements.txt` / `Cargo.toml` / `go.mod`
- 识别主要语言、主要框架(Django / FastAPI / React / Next.js / Express...)、包管理器

输出:`tech_summary` 一句话(用于报告)

### Step 2:提取命名约定

按语言 grep 不同模式,统计比例:

**Python** (`*.py`):
- 函数命名:`^def\s+(\w+)` → 统计 snake_case / camelCase / PascalCase 占比
- 类命名:`^class\s+(\w+)` → 统计同上
- 模块级常量:`^([A-Z_][A-Z0-9_]*)\s*=` → UPPER_SNAKE_CASE 验证
- 文件名:从 Glob 看 `*.py` 文件名

**TypeScript / JavaScript** (`*.ts`, `*.tsx`, `*.js`):
- 函数 / 类 / 常量同上
- React 组件:`^(?:export\s+)?(?:function|const)\s+(\w+)` → PascalCase 占比
- 文件名:kebab-case / camelCase / PascalCase 占比

**通用 — API 路由**:
- 扫 `(app|router|fastapi)\.(get|post|put|delete)\(['"]([^'"]+)` 提取所有路由
- 路径段统计:kebab-case(`/user-profile`)vs snake_case(`/user_profile`)vs camelCase(`/userProfile`)

**通用 — 数据库字段**:
- 扫 ORM 模型(`Column(...)` / `models.CharField()` / Prisma schema)
- 字段名统计 snake_case vs camelCase

### Step 3:提取数据契约

- 扫 API 响应(`return jsonify(...)` / `return {...}` / `Response({...})` / `.json({...})`)
- 提取响应字段名,统计**模板**:
  - 是否所有响应都有 `code` 字段?
  - 是否有 `data` 字段包裹业务数据?
  - 错误响应 `error` / `message` / `detail`?
- 如果 80% 以上响应符合同一模板 → 视为事实契约

### Step 4:提取错误处理风格

- 扫 `try / except`(Python)或 `try / catch`(TS/JS)位置:
  - 集中在 middleware 还是分散在每个函数?
- 扫日志调用(`logger.info / .error`):
  - 日志级别使用习惯
  - 是否结构化(JSON)还是纯字符串
- 扫异常类型:自定义 Exception 类多还是少?

### Step 5:提取代码风格量化指标

跑 Bash 统计:

```
# 单文件最大 / 平均行数
find src -name "*.py" -exec wc -l {} \; | sort -n | tail -5

# 平均函数长度(粗略)
grep -A 999 "^def " *.py | awk ...

# import 分段(看前 20 行的 import 顺序)
```

输出:
- 单文件行数 P50 / P95
- 函数行数 P50 / P95
- import 分段顺序(stdlib → third-party → local 还是混合)
- 缩进(检查源文件第一行后的缩进,空格 vs Tab)

### Step 6:产出契约草稿

按 corrections.md §1 项目契约的格式产出。每条标注**置信度**(覆盖率):

```markdown
## §1 项目契约(声明式规则 — 防一类问题)

### 命名
- Python 函数 snake_case(覆盖 47/50 = 94%)
- 类 PascalCase(38/40 = 95%)
- 常量 UPPER_SNAKE_CASE(12/12 = 100%)
- API 路由 kebab-case(28/31 = 90%)
- 数据库字段 snake_case(47/47 = 100%)

### API 数据契约
- 所有响应统一 `{code: int, message: str, data: any}`(89% 覆盖)
- 错误码 4xx 客户端错误 / 5xx 服务端错误

### 错误处理
- 后端 try-except 集中在 middleware(`src/middleware/error_handler.py`)
- 日志级别:INFO / WARN / ERROR 三级,结构化 JSON

### 代码风格
- 单文件 ≤ 300 行(P95 = 287)
- 函数 ≤ 40 行(P95 = 38)
- import 分三段:stdlib → third-party → local
- 缩进 4 空格
```

**对覆盖率 < 80% 的契约,不直接定为契约,而是标注"待用户决定"**:

```markdown
### 待用户决策(覆盖率不一致)
- API 路由命名:kebab-case 占 70%,snake_case 占 30% — 需要用户决定哪个为准
- 函数注释:有 docstring 占 40%,无注释占 60% — 是否要求 docstring?
```

### Step 7:呈交给用户审核

输出报告:
1. **扫描概览**:扫了多少文件 / 多少 API / 哪些语言
2. **高置信契约**(≥ 80% 覆盖):直接当草稿写入 §1
3. **待决策项**(60-80% 覆盖):列出选项让用户选
4. **明显反例**(< 60% 覆盖):不入契约,但报告作参考

用户确认后,通过 `[存档]` 的 `corrections_update` 写入 §1(用 `===SECTION===\n§1 项目契约\n[草稿]` 格式)。

---

## 反模式

- ❌ **直接写入 §1 不让用户审** — 自动提取≠用户认可,必须经过审核环节
- ❌ **覆盖率 60% 以下也写成契约** — 这是"伪契约",会误导未来 AI
- ❌ **跟代码事实不符的强行写入** — 如果代码混乱(覆盖率 30/30/40),应该报告"无明显契约,待用户主动设计",而非自己编造
- ❌ **跑了一次就完事** — 应该周期性跑(类似 omm-scan Layer 2),发现新漂移

---

## 输出示例

```
## 契约提取报告

扫描概览:
- 语言:Python(82 文件) + TypeScript(34 文件)
- API endpoints:47 个(FastAPI)
- ORM 模型:12 个(SQLAlchemy)

高置信契约(≥ 80% 覆盖,建议入 §1):
[详细列表...]

待用户决策(覆盖率不一致):
[详细列表...]

明显反例(< 60% 覆盖,不入契约,仅供参考):
[详细列表...]

下一步:用户审完后,跑 [存档] 用 corrections_update 把 §1 写入。
```
