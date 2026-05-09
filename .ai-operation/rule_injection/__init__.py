"""
Rule Injection Pipeline (议题 #014 v3.5 / 议题 #003 The Bridge 第一块砖)
========================================================================

每次用户提交输入时,在 AI 看到的输入开头注入一段"规则纸条"。
强制管道存在(物理 A 级),信任 AI 输出(议题 #013 同源精神)。

Architecture:
- container/  各条规则的源文本(每条规则一个 .md 文件)
- adapters/   编辑器适配器(claude_code / cursor / windsurf)
- engine.py   规则容器加载 + 纸条组装
- cli.py      命令行入口(install / uninstall / inject)

The Bridge 模块的物质化第一块砖。
"""

from .engine import build_paper, list_rules, RULE_CONTAINER_DIR

__all__ = ["build_paper", "list_rules", "RULE_CONTAINER_DIR"]
