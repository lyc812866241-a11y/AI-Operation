# Bootstrap Corrections Log

> 经验库。COUNT >= 3 自动升级为 SKILL.md 检查项。

---
DATE: 2026-04-07
CONTEXT: 实战验证（火火兔项目）
LESSON: 文件大小检查必须用字节数 len(content.encode("utf-8"))，不能用字符数 len(content)。中文 1 字符 = 3 字节。
COUNT: 1

---
DATE: 2026-04-07
CONTEXT: 实战验证（火火兔项目）
LESSON: corrections.md 头部说明文字可能占 14KB，实际条目只有 3 条。归档逻辑不能只看条目数，要先瘦身头部。
COUNT: 1

---
DATE: 2026-04-07
CONTEXT: 实战验证（火火兔项目）
LESSON: 大项目 git add 必须指定具体文件，不能 add 整个目录。git commit 用 --no-verify 跳过 hook 扫描。否则 8000+ 文件的 repo 存档卡 10 分钟。
COUNT: 1

---
DATE: 2026-04-07
CONTEXT: 实战验证（多项目）
LESSON: AI 存档时写"完成了编导功能"就过关——信息密度校验（200 字符 + 文件路径）是必须的，否则存档毫无还原价值。
COUNT: 1

---
DATE: 2026-04-07
CONTEXT: 实战验证（火火兔项目）
LESSON: 12KB 提示词预算对真实项目太紧。7 个文件 × 平均 2KB = 就超了。扩到 50KB（约 12K token，占 1M 上下文的 1.2%）。
COUNT: 1

---
DATE: 2026-04-07
CONTEXT: 实战验证（火火兔项目）
LESSON: 自进化机制只绑在 [初始化项目]（一辈子跑一次），日常开发占 90% 时间但没有经验捕获。lessons_learned 必须是 [存档] 的强制参数。
COUNT: 1
