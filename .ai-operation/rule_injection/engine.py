"""
Rule container loader + paper assembler.
========================================

The container is just a directory of .md files. Each file is one rule.
The engine reads them in deterministic order and concatenates them into
a single "paper" that gets injected at the start of every user prompt.

Why per-file rules (not one big file):
  议题 #016 单一职责 + 易扩展:加新规则 = 新建一个 md 文件,不动壳。
  议题 #009 同 scope 内可独立进化。
"""

from pathlib import Path
from typing import List


# Container dir is relative to this file, NOT to cwd. The injection hook
# may be invoked from any working directory, so we anchor on the framework
# install path itself.
RULE_CONTAINER_DIR = Path(__file__).parent / "container"

# Paper version stamp (议题 #016 升级时同步:用版本识别旧 hook 是否要覆盖).
# Bump when paper assembly logic changes (rule format / order / framing).
PAPER_FORMAT_VERSION = "1.0"


def list_rules() -> List[Path]:
    """Return rule files in deterministic order (filename sort).

    Skips hidden files and non-.md files. Missing container dir = empty list.
    """
    if not RULE_CONTAINER_DIR.exists():
        return []
    return sorted(
        p for p in RULE_CONTAINER_DIR.glob("*.md")
        if not p.name.startswith(".")
    )


def build_paper() -> str:
    """Assemble all rules into a single paper string.

    Format (every paper looks like this):

        ## [AI-Operation Rule Injection v{version}]

        Each invocation of the AI must absorb the rules below before
        producing output. (强制管道存在,信任 AI 输出能力 -- 议题 #013 同源)

        ### Rule: language_style
        <body>

        ### Rule: <next_rule>
        <body>

        ## [End AI-Operation Rule Injection]

    The framing block tells the AI clearly what this is and where it
    starts/ends, so the AI can distinguish injected rules from the user's
    actual prompt that follows.
    """
    rules = list_rules()
    if not rules:
        # Container empty -- emit a minimal stamp so install verification
        # can still confirm the pipeline is wired, even before any rule
        # has been authored.
        return (
            f"## [AI-Operation Rule Injection v{PAPER_FORMAT_VERSION}]\n\n"
            f"(no rules currently registered)\n\n"
            f"## [End AI-Operation Rule Injection]\n"
        )

    parts = [
        f"## [AI-Operation Rule Injection v{PAPER_FORMAT_VERSION}]\n",
        "",
        "Each invocation of the AI must absorb the rules below before",
        "producing output. (强制管道存在,信任 AI 输出能力 -- 议题 #013 同源)",
        "",
    ]

    for rule_file in rules:
        try:
            body = rule_file.read_text(encoding="utf-8").strip()
        except OSError:
            # Don't let a single broken rule file kill the pipeline --
            # skip it, the rest still work.
            continue
        rule_id = rule_file.stem
        parts.append(f"### Rule: {rule_id}")
        parts.append("")
        parts.append(body)
        parts.append("")

    parts.append("## [End AI-Operation Rule Injection]")
    return "\n".join(parts) + "\n"
