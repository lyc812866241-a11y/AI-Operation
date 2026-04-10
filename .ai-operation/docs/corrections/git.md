# Git 操作经验

- 大项目 git add 必须指定具体文件，不能 add 整个目录。否则 8000+ 文件的 repo 存档卡 10 分钟。
- Windows 上 subprocess.run(capture_output=True, timeout=N) 会死锁。必须用 Popen + stdin=DEVNULL。
- git subtree 和 .ai-operation/ 目录嵌套冲突，rm -rf 会删除 venv 等本地产物。用 setup.ps1 -Update。
