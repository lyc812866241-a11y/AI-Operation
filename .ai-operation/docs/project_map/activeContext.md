# 当前工作焦点 (Active Context)

> [DYNAMIC] 每次 [存档] 自动更新。

## 1. 当前焦点

框架 v1.1 — 吸收外部洞察（vibe coding 帖子 + DeerFlow）+ 实战 bug 修复。5 个项目并行验证中。

## 2. 正在处理的问题

- Windows subprocess 死锁已修复（Popen + DEVNULL 替代 subprocess.run + capture_output）
- 存档 APPEND 膨胀 bug 已修复（静态文件改为 OVERWRITE）
- inventory NO_CHANGE 覆盖 bug 已修复
- setup.ps1 pip 自升级报错已修复（python -m pip）
- git add timeout 从 10s 调到 60s

## 3. 即将执行的下一步

1. 5 个项目实战验证新版框架（v1.1）
2. 确认 git commit 在大项目上能正常完成（60s timeout 够不够）
3. architect.py 拆分（已超 2200 行）
