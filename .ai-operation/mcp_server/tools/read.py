"""
Read tools -- project map reading, detail retrieval, and detail listing.
Contains: aio__force_architect_read, aio__detail_read, aio__detail_list
"""

from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


def register_read_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register read-related tools onto the MCP server instance."""

    @mcp.tool()
    def aio__force_architect_read() -> str:
        """
        [ENFORCEMENT TOOL] Force a full read of all project map files.

        This tool MUST be called when the user issues the [读档] command.
        Returns structured context report with smart budget management:
        - Dynamic files (activeContext, progress): always read in full (most important)
        - Static files (projectbrief, systemPatterns, techContext): full if budget allows,
          otherwise TOC-only (section titles) with "use aio__detail_read for full content"
        - Inventory: included if budget remains

        Applies prompt budget: 12KB total to prevent token overflow.
        """
        import re

        report = ["# Project Map Full State Report\n"]
        total_chars = 0

        # Pre-calculate total size to decide strategy
        total_size = 0
        for fn in REQUIRED_FILES.values():
            fp = PROJECT_MAP_DIR / fn
            if fp.exists():
                total_size += fp.stat().st_size

        budget_tight = total_size > MAX_TOTAL_CHARS

        # Priority order: dynamic files first (most important for continuity)
        priority_order = [
            ("activeContext", "activeContext.md", True),    # always full
            ("progress", "progress.md", True),              # always full
            ("conventions", "conventions.md", True),        # always full -- 二阶 contracts (naming/API/style)
            ("projectbrief", "projectbrief.md", False),     # TOC if tight
            ("systemPatterns", "systemPatterns.md", False),  # TOC if tight
            ("techContext", "techContext.md", False),        # TOC if tight
            ("inventory", "inventory.md", False),            # TOC if tight
        ]

        for label, filename, always_full in priority_order:
            filepath = PROJECT_MAP_DIR / filename
            if not filepath.exists():
                continue

            report.append(f"\n## [{label}] {filename}")
            content = filepath.read_text(encoding="utf-8")
            file_size = len(content)

            if always_full or not budget_tight:
                # Read full content (with per-file cap)
                if file_size > MAX_FILE_CHARS:
                    content = content[:MAX_FILE_CHARS] + "\n\n[truncated -- 4KB per-file limit]"
                if total_chars + len(content) > MAX_TOTAL_CHARS:
                    remaining = MAX_TOTAL_CHARS - total_chars
                    if remaining > 500:
                        content = content[:remaining] + "\n\n[truncated -- budget reached]"
                    else:
                        # Switch to TOC mode for this file
                        content = _generate_toc(content, filename)
                total_chars += len(content)
                report.append(content)
            else:
                # Budget-tight mode: show TOC only for static files
                toc = _generate_toc(content, filename)
                total_chars += len(toc)
                report.append(toc)

        # Also check details/ directory
        if DETAILS_DIR.exists():
            detail_files = sorted(DETAILS_DIR.glob("*.md"))
            if detail_files:
                detail_info = f"\n## [Details] {len(detail_files)} detail files available"
                for df in detail_files:
                    detail_info += f"\n  - {df.name} ({df.stat().st_size} bytes)"
                report.append(detail_info)

        # Discover and append sub-directory rules (rules.d/)
        rules_dir = Path(".ai-operation/rules.d")
        if rules_dir.exists():
            rule_files = sorted(rules_dir.glob("*.md"))
            rule_files = [f for f in rule_files if f.name != "README.md"]
            if rule_files:
                report.append("\n## [Sub-Directory Rules]")
                for rf in rule_files:
                    content = rf.read_text(encoding="utf-8")
                    if len(content) > MAX_FILE_CHARS:
                        content = content[:MAX_FILE_CHARS] + "\n\n[truncated]"
                    if total_chars + len(content) > MAX_TOTAL_CHARS:
                        remaining = MAX_TOTAL_CHARS - total_chars
                        if remaining > 200:
                            content = content[:remaining] + "\n\n[truncated -- budget reached]"
                        else:
                            report.append(f"\n### {rf.name}\n[omitted -- budget exhausted]")
                            continue
                    total_chars += len(content)
                    report.append(f"\n### {rf.name}\n{content}")

        # -- Cache file contents already read above to avoid re-reading --
        _file_cache = {}
        for label, filename, _ in priority_order:
            fp = PROJECT_MAP_DIR / filename
            if fp.exists():
                _file_cache[filename] = fp.read_text(encoding="utf-8")

        # -- Data Quality Checks (use cached content, no extra IO) --
        quality_warnings = []

        # Check 1: inventory.md still has [待填写] placeholders
        inv_text = _file_cache.get("inventory.md", "")
        if inv_text:
            placeholder_count = inv_text.count("[待填写")
            if placeholder_count >= 2:
                quality_warnings.append(
                    f"[!] inventory.md has {placeholder_count} unfilled sections. "
                    f"Use aio__inventory_append to populate."
                )

        # Check 2: systemPatterns vs techContext consistency
        sp_text = _file_cache.get("systemPatterns.md", "").lower()
        tc_text = _file_cache.get("techContext.md", "").lower()
        if sp_text and tc_text:
            stale_pairs = [
                ("langgraph", "自研 react", "systemPatterns mentions LangGraph but techContext says 自研 ReAct"),
                ("langchain", "零框架", "systemPatterns mentions LangChain but techContext says 零框架"),
            ]
            for old_term, new_term, msg in stale_pairs:
                if old_term in sp_text and new_term in tc_text:
                    quality_warnings.append(f"[!] STALE: {msg}")

        # Check 3: conventions.md missing or all placeholders
        conv_text = _file_cache.get("conventions.md", "")
        if not conv_text:
            quality_warnings.append("[i] conventions.md missing. Create during next [save].")
        elif conv_text.count("[待填写") >= 3:
            quality_warnings.append("[!] conventions.md has 3+ unfilled sections.")

        # Check 4: systemPatterns missing file tree (no scan_codebase output)
        sp_full = _file_cache.get("systemPatterns.md", "")
        if sp_full and not ("## Entry Points" in sp_full or "## Modules" in sp_full or "Codebase Scan" in sp_full):
            quality_warnings.append(
                "[!] systemPatterns has no file tree. Run aio__scan_codebase to add one."
            )

        # Check 5: conventions.md may contain first-order lessons
        if conv_text:
            first_order_signals = ["禁止", "不能", "不要", "必须先", "之前出过", "踩过坑"]
            signal_count = sum(1 for s in first_order_signals if s in conv_text)
            if signal_count >= 2:
                quality_warnings.append(
                    "[!] conventions.md may have first-order lessons (禁止/不能/踩过坑). "
                    "Move to corrections/{key}.md."
                )

        if quality_warnings:
            report.append("\n## Data Quality Warnings\n")
            for w in quality_warnings:
                report.append(f"  {w}")

        # -- Cleanup Reminder (lightweight: stat only, no file reading) --
        import time as _time
        cleanup_reasons = []

        ac_path = PROJECT_MAP_DIR / "activeContext.md"
        if ac_path.exists():
            ac_age_days = int((_time.time() - ac_path.stat().st_mtime) / 86400)
            if ac_age_days > 7:
                cleanup_reasons.append(f"activeContext.md last updated {ac_age_days} days ago")

        corrections_dir = PROJECT_MAP_DIR.parent / "corrections"
        if corrections_dir.exists():
            key_count = len(list(corrections_dir.glob("*.md")))
            if key_count > 10:
                cleanup_reasons.append(f"{key_count} experience keys (consider consolidating)")

        if cleanup_reasons:
            report.append("\n## Cleanup Reminder\n")
            for r in cleanup_reasons:
                report.append(f"  - {r}")
            report.append("  Run [整理] to consolidate.")

        # -- Orphan Reference Check (use cached sp_text, no re-read) --
        if sp_full:
            import re as _re
            # Longer extensions MUST come before their shorter prefixes so
            # regex alternation doesn't match .js inside state.json. The
            # (?!\w) tail enforces a word boundary so .js won't swallow the
            # `j` of .json even if ordering is wrong.
            referenced_paths = _re.findall(
                r'([\w./\-]+\.(?:json|yaml|py|ts|js|go|rs|sh|yml|md))(?!\w)',
                sp_full
            )
            orphans = []
            # Scan under project_map/ too -- overflow / detail files live
            # at .ai-operation/docs/project_map/details/*.md and are referenced
            # as `details/foo.md` from the parent file.
            pm_root = Path(".ai-operation/docs/project_map")
            for ref_path in set(referenced_paths):
                if ref_path.startswith("http") or ref_path.startswith("#"):
                    continue
                if (
                    not Path(ref_path).exists()
                    and not Path(".ai-operation", ref_path).exists()
                    and not (pm_root / ref_path).exists()
                ):
                    orphans.append(ref_path)

            if orphans:
                report.append(f"\n## Orphan References ({len(orphans)} found)\n")
                report.append("  systemPatterns references missing files:")
                for o in orphans[:10]:
                    report.append(f"    - {o}")

        # -- Skill Registry (no subprocess — just list available skills) --
        skills = _discover_skills()
        if skills:
            report.append("\n## Available Skills\n")
            for skill in skills:
                when_str = ", ".join(skill.get("when", [])) if skill.get("when") else "manual"
                report.append(
                    f"  - **{skill['name']}**: {skill.get('description', '')} "
                    f"[triggers: {when_str}]"
                )

        budget_pct = int(total_chars / MAX_TOTAL_CHARS * 100)
        report.append(f"\n---\nBudget: {total_chars}/{MAX_TOTAL_CHARS} ({budget_pct}%)")

        _audit("aio__force_architect_read", "SUCCESS",
               f"budget={budget_pct}%,chars={total_chars},warnings={len(quality_warnings)},skills={len(skills)}")
        return "\n".join(report)

    @mcp.tool()
    def aio__detail_read(
        detail_file: str,
    ) -> str:
        """
        [RETRIEVAL TOOL] Read a file from project_map or its detail subfiles.

        Use this tool in TWO situations:
        1. When [读档] shows "[TOC mode]" for a file -- call this with the filename
           (e.g., "systemPatterns.md") to get the full content.
        2. When [读档] shows "-> [详见 details/xxx.md]" -- call this with the detail
           filename to get the split section content.

        Args:
            detail_file: Filename to read. Can be:
                - A project_map file: "systemPatterns.md", "techContext.md", etc.
                - A detail subfile: "systemPatterns__可用单元清单.md"

        Returns:
            Full content of the requested file.
        """
        # First check if it's a direct project_map file
        direct_path = PROJECT_MAP_DIR / detail_file
        if direct_path.exists():
            content = direct_path.read_text(encoding="utf-8")
            _audit("aio__detail_read", "SUCCESS", f"direct:{detail_file}")
            return f"# Full content: {detail_file}\nSize: {len(content)} chars\n\n{content}"

        # Search across detail levels: details/, details/L1/, details/L2/, ...
        detail_path = DETAILS_DIR / detail_file
        if not detail_path.exists() and DETAILS_DIR.exists():
            for sub in sorted(DETAILS_DIR.iterdir()):
                if sub.is_dir() and (sub / detail_file).exists():
                    detail_path = sub / detail_file
                    break

        if not detail_path.exists():
            available = []
            # List project_map files
            available.extend(f.name for f in PROJECT_MAP_DIR.glob("*.md"))
            # List detail files
            if DETAILS_DIR.exists():
                available.extend(f"details/{f.name}" for f in DETAILS_DIR.glob("*.md"))
                for sub in sorted(DETAILS_DIR.iterdir()):
                    if sub.is_dir():
                        available.extend(f"details/{sub.name}/{f.name}" for f in sub.glob("*.md"))
            return (
                f"FAILED: '{detail_file}' not found.\n"
                f"Available:\n" + "\n".join(f"  - {a}" for a in sorted(available))
            )

        content = detail_path.read_text(encoding="utf-8")
        _audit("aio__detail_read", "SUCCESS", detail_file)

        return (
            f"# Detail: {detail_file}\n"
            f"Size: {len(content)} chars\n\n"
            f"{content}"
        )

    @mcp.tool()
    def aio__detail_list() -> str:
        """
        [RETRIEVAL TOOL] List all detail subfiles and their sizes.

        Use this to see what sections have been split out of parent files.

        Returns:
            List of detail files with sizes.
        """
        if not DETAILS_DIR.exists():
            return "No details directory found. No sections have been split yet."

        files = sorted(DETAILS_DIR.glob("*.md"))
        if not files:
            return "Details directory exists but is empty. No sections have been split yet."

        report = ["# Detail Files (分级子文件)\n"]
        total_size = 0
        for f in files:
            size = f.stat().st_size
            total_size += size
            report.append(f"  - {f.name} ({size:,} bytes)")

        report.append(f"\nTotal: {len(files)} files, {total_size:,} bytes")
        return "\n".join(report)
