"""
Read tools — project map reading, detail retrieval, and detail listing.
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
            ("conventions", "conventions.md", True),        # always full — AI needs contracts when coding
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
                    content = content[:MAX_FILE_CHARS] + "\n\n[truncated — 4KB per-file limit]"
                if total_chars + len(content) > MAX_TOTAL_CHARS:
                    remaining = MAX_TOTAL_CHARS - total_chars
                    if remaining > 500:
                        content = content[:remaining] + "\n\n[truncated — budget reached]"
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
                            content = content[:remaining] + "\n\n[truncated — budget reached]"
                        else:
                            report.append(f"\n### {rf.name}\n[omitted — budget exhausted]")
                            continue
                    total_chars += len(content)
                    report.append(f"\n### {rf.name}\n{content}")

        # ── Auto-Save Reminder ────────────────────────────────────
        # Estimate total project_map size. If growing large, recommend [存档].
        total_map_size = 0
        for filename in REQUIRED_FILES.values():
            fp = PROJECT_MAP_DIR / filename
            if fp.exists():
                total_map_size += fp.stat().st_size

        budget_pct = int(total_chars / MAX_TOTAL_CHARS * 100)
        report.append(f"\n---\nPrompt budget: {total_chars}/{MAX_TOTAL_CHARS} chars ({budget_pct}% used)")
        report.append(f"Project map total size: {total_map_size:,} bytes")

        if budget_pct >= 70:
            report.append(
                f"\n⚠️ WARNING: Prompt budget at {budget_pct}%. "
                f"activeContext.md may be growing too large. "
                f"Consider running [存档] with session_compaction to compress older entries, "
                f"or manually trim activeContext.md via [清理]."
            )
        if total_map_size > 50_000:
            report.append(
                f"\n⚠️ WARNING: Project map total size ({total_map_size:,} bytes) exceeds 50KB. "
                f"Some content may be truncated during [读档]. "
                f"Consider archiving older entries in activeContext.md and progress.md."
            )

        # ── Data Quality Checks ────────────────────────────────────
        quality_warnings = []

        # Check 1: inventory.md still has [待填写] placeholders
        inv_path = PROJECT_MAP_DIR / "inventory.md"
        if inv_path.exists():
            inv_content = inv_path.read_text(encoding="utf-8")
            placeholder_count = inv_content.count("[待填写")
            if placeholder_count >= 2:
                quality_warnings.append(
                    f"⚠️ inventory.md has {placeholder_count} unfilled [待填写] sections. "
                    f"You have NO asset inventory. After scanning the codebase, "
                    f"use aio__inventory_append to populate skills, APIs, data models."
                )

        # Check 2: systemPatterns.md vs techContext.md consistency
        sp_path = PROJECT_MAP_DIR / "systemPatterns.md"
        tc_path = PROJECT_MAP_DIR / "techContext.md"
        if sp_path.exists() and tc_path.exists():
            sp_content = sp_path.read_text(encoding="utf-8").lower()
            tc_content = tc_path.read_text(encoding="utf-8").lower()
            # Extract tech keywords from techContext, check if systemPatterns contradicts
            stale_pairs = [
                ("langgraph", "自研 react", "systemPatterns still mentions LangGraph but techContext says 自研 ReAct"),
                ("langchain", "零框架", "systemPatterns still mentions LangChain but techContext says 零框架依赖"),
                ("gemini", "minimax", "systemPatterns still mentions Gemini but techContext says MiniMax"),
                ("gpt-4", "minimax", "systemPatterns still mentions GPT-4 but techContext says MiniMax"),
            ]
            for old_term, new_term, msg in stale_pairs:
                if old_term in sp_content and new_term in tc_content:
                    quality_warnings.append(f"⚠️ STALE DATA: {msg}. Update systemPatterns.md during next [存档].")

        # Check 3: conventions.md missing or all placeholders
        conv_path = PROJECT_MAP_DIR / "conventions.md"
        if not conv_path.exists():
            quality_warnings.append(
                "ℹ️ conventions.md does not exist yet. Create it during next [存档] "
                "to define naming, API, and code style conventions."
            )
        elif conv_path.exists():
            conv_content = conv_path.read_text(encoding="utf-8")
            if conv_content.count("[待填写") >= 3:
                quality_warnings.append(
                    "⚠️ conventions.md has 3+ unfilled sections. "
                    "Fill in project conventions during next [存档] to improve code consistency."
                )

        if quality_warnings:
            report.append("\n## 🔍 Data Quality Warnings\n")
            for w in quality_warnings:
                report.append(f"  {w}")

        # ── Cleanup Reminder ────────────────────────────────────
        # Auto-detect stale project_map and remind user to run [整理]
        import time as _time
        cleanup_reasons = []

        # Check 1: activeContext.md mtime > 7 days
        ac_path = PROJECT_MAP_DIR / "activeContext.md"
        if ac_path.exists():
            ac_age_days = int((_time.time() - ac_path.stat().st_mtime) / 86400)
            if ac_age_days > 7:
                cleanup_reasons.append(f"activeContext.md last updated {ac_age_days} days ago")

        # Check 2: corrections key count > 10
        corrections_dir = PROJECT_MAP_DIR.parent / "corrections"
        if corrections_dir.exists():
            key_count = len(list(corrections_dir.glob("*.md")))
            if key_count > 10:
                cleanup_reasons.append(f"{key_count} experience keys (consider consolidating)")

        # Check 3: audit.log > 500 lines
        audit_path = Path(".ai-operation/audit.log")
        if audit_path.exists():
            audit_lines = audit_path.read_text(encoding="utf-8").count("\n")
            if audit_lines > 500:
                cleanup_reasons.append(f"audit.log has {audit_lines} lines")

        if cleanup_reasons:
            report.append("\n## 🧹 Cleanup Reminder\n")
            report.append("  project_map may need cleanup. Reasons:")
            for r in cleanup_reasons:
                report.append(f"    - {r}")
            report.append("  Consider running [整理] to consolidate and trim.")

        # ── Orphan Reference Check (Lint) ──────────────────────
        # Verify that file paths mentioned in systemPatterns.md actually exist.
        # Inspired by Karpathy's LLM Wiki "lint" workflow.
        sp_path = PROJECT_MAP_DIR / "systemPatterns.md"
        if sp_path.exists():
            import re as _re
            sp_content = sp_path.read_text(encoding="utf-8")
            # Extract file paths from systemPatterns (patterns like path/to/file.ext)
            referenced_paths = _re.findall(
                r'[`|]?\s*([\w./\-]+\.(?:py|ts|js|go|rs|sh|ps1|yml|yaml|json|md))\s*[`|]?',
                sp_content
            )
            orphans = []
            for ref_path in set(referenced_paths):
                # Skip obvious non-file references and framework internals
                if ref_path.startswith("http") or ref_path.startswith("#"):
                    continue
                full_path = Path(ref_path)
                if not full_path.exists():
                    # Also check relative to .ai-operation/
                    alt_path = Path(".ai-operation") / ref_path
                    if not alt_path.exists():
                        orphans.append(ref_path)

            if orphans:
                report.append(f"\n## 👻 Orphan References ({len(orphans)} found)\n")
                report.append("  systemPatterns.md references files that don't exist:")
                for o in orphans[:10]:
                    report.append(f"    - `{o}` — missing or renamed")
                report.append("  Update systemPatterns.md during next [存档] or [整理].")

        # ── Skill Registry (frontmatter-driven) ────────────────
        # Show available skills with their trigger conditions.
        # Skills with `paths` are only shown if current git status touches matching files.
        skills = _discover_skills()
        if skills:
            # Get current git-modified files for conditional activation
            import subprocess as _sp
            try:
                git_result = _sp.run(
                    ["git", "diff", "--name-only", "HEAD"],
                    capture_output=True, text=True, timeout=10
                )
                changed_files_git = set(git_result.stdout.strip().split("\n")) if git_result.stdout.strip() else set()
                # Also add staged files
                git_staged = _sp.run(
                    ["git", "diff", "--name-only", "--cached"],
                    capture_output=True, text=True, timeout=10
                )
                if git_staged.stdout.strip():
                    changed_files_git.update(git_staged.stdout.strip().split("\n"))
            except Exception:
                changed_files_git = set()

            import fnmatch
            report.append("\n## 📋 Available Skills\n")
            for skill in skills:
                skill_paths = skill.get("paths", [])
                # If skill has paths filter, only show if any changed file matches
                if skill_paths:
                    matched = any(
                        fnmatch.fnmatch(cf, pat)
                        for cf in changed_files_git
                        for pat in skill_paths
                    )
                    if not matched and changed_files_git:
                        continue  # Skip: no matching files in current changes

                when_str = ", ".join(skill.get("when", [])) if skill.get("when") else "manual"
                report.append(
                    f"  - **{skill['name']}**: {skill.get('description', '')} "
                    f"[triggers: {when_str}]"
                )

        _audit("aio__force_architect_read", "SUCCESS", f"budget={budget_pct}%,size={total_map_size},quality_warnings={len(quality_warnings)},cleanup_reasons={len(cleanup_reasons)},skills={len(skills)}")
        return _budget_truncate("\n".join(report))

    @mcp.tool()
    @mcp.tool()
    def aio__detail_read(
        detail_file: str,
    ) -> str:
        """
        [RETRIEVAL TOOL] Read a file from project_map or its detail subfiles.

        Use this tool in TWO situations:
        1. When [读档] shows "[TOC mode]" for a file — call this with the filename
           (e.g., "systemPatterns.md") to get the full content.
        2. When [读档] shows "→ [详见 details/xxx.md]" — call this with the detail
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
