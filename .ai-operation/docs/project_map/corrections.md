# Bootstrap Corrections Log

> 经验库。COUNT >= 3 自动升级到 conventions.md 成为项目契约。

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

---
DATE: 2026-04-08
CONTEXT: 实战验证（火火兔项目 V18 存档反复失败）
LESSON: Windows 上 subprocess.run(capture_output=True, timeout=N) 会死锁——git 子进程继承管道句柄，父进程被杀后子进程仍持有管道，communicate() 永远阻塞。必须用 Popen + DEVNULL 避免管道死锁。
COUNT: 1

---
DATE: 2026-04-08
CONTEXT: 实战验证（火火兔项目存档）
LESSON: inventory_update 参数传 NO_CHANGE_BECAUSE 会被当作内容 OVERWRITE 原文件。所有可选参数都必须检查 NO_CHANGE 前缀，不能只对核心 5 个文件做检查。
COUNT: 1

---
DATE: 2026-04-08
CONTEXT: 实战验证（火火兔项目存档）
LESSON: 静态文件没有 ===SECTION=== 时回退到 APPEND 模式会导致内容无限膨胀。每次存档追加一段 Auto-Archive，3 次存档后文件不可读。应该 OVERWRITE 而不是 APPEND。
COUNT: 1

---
DATE: 2026-04-08
CONTEXT: 火火兔项目 subtree 更新事故
LESSON: git subtree 和框架仓库的 .ai-operation/ 目录嵌套冲突，rm -rf .ai-operation 会删除 venv 等本地产物。分发方式应使用 setup.ps1 -Update 只覆盖框架代码，不碰本地产物。
COUNT: 1

---
DATE: 2026-04-08
CONTEXT: 对比 DeerFlow 记忆分层时漏判
LESSON: 对比外部项目时，先翻译回底层问题再比较，不要被对方的命名体系（如"6层分级"）迷惑。AI-Operation 的 auto-split + TOC + detail_read 已经是等价方案。
COUNT: 1
