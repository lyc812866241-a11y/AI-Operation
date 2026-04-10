"""
Save tools — two-phase architect save protocol.
Contains: aio__force_architect_save, aio__force_architect_save_confirm
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


def register_save_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register save-related tools onto the MCP server instance."""

    @mcp.tool()
    def aio__force_architect_save(
        projectbrief_update: str,
        systemPatterns_update: str,
        techContext_update: str,
        activeContext_update: str,
        progress_update: str,
        lessons_learned: str,
        inventory_update: str = "",
        conventions_update: str = "",
        session_compaction: str = "",
    ) -> str:
        """
        [CRITICAL ENFORCEMENT TOOL] Execute the Level 4 Architect Save Protocol.

        This tool MUST be called when the user issues the [存档] command.
        The AI agent MUST NOT manually edit project_map files or run git commands directly.

        CRITICAL: For ALL 6 file parameters (5 core + conventions), you must EITHER:
          - Provide update content (see format below)
          - Write "NO_CHANGE_BECAUSE: [specific reason]" explaining WHY no update is needed

        Simply writing "NO_CHANGE" is REJECTED. You must justify why each file doesn't need updating.

        SECTION-AWARE MERGE (for static files: projectbrief, systemPatterns, techContext, conventions):
        Instead of dumping all content as one blob, use ===SECTION=== delimiters to target
        specific sections. The tool will update ONLY those sections, leaving others untouched.

        Format:
          "可用单元清单\nnew table content here\n===SECTION===\n架构约束\nnew constraint here"

        Each block: first line = section title to match, rest = new content for that section.
        Sections not mentioned are left unchanged. Use SKIP as content to explicitly skip a section.
        If no ===SECTION=== delimiters found, falls back to append mode (backward compatible).

        MINIMUM DETAIL REQUIREMENTS (MCP tool will REJECT if too vague):
        - activeContext_update must mention specific FILE PATHS that were changed
        - activeContext_update must be at least 200 chars
        - progress_update must list each completed task with the FILE it touched
        - progress_update must be at least 150 chars
        - For static files with actual content (not NO_CHANGE_BECAUSE): must be at least 100 chars

        EXAMPLE of GOOD activeContext_update (this level of detail is the MINIMUM):
          "当前焦点：Node 4B 公式模式生图方案优化
           刚完成：
           - src/engine/pipeline_engine.py (+186/-17): Node 1 自动扫描 inbox 视频带前缀防覆盖;
             Node 2 轨道B 调用 formula_director 三阶编导; Node 4B 按内容分流产品还原 vs 意境场景
           - skills/director/formula_director.py (新建 ~300行): round_1_analyze + round_2_adapt
             + round_3a_visual_design + round_3b_to_prompt, 并发5
           下一步：Node 4B 分流改用 LLM 判断; 产品还原换 imagen-4.0-ultra"

        EXAMPLE of BAD activeContext_update (will be REJECTED):
          "完成了三阶编导，继续优化生图"  ← too vague, no file paths, no details

        Args:
            projectbrief_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            systemPatterns_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            techContext_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            activeContext_update: REQUIRED. See detail requirements above. Min 200 chars.
            progress_update: REQUIRED. Each task with file path. Min 150 chars.
            lessons_learned: REQUIRED. Lessons from this session. "NONE" only if truly nothing learned.
            inventory_update: Optional but CRITICAL for list data. If this session created, discovered,
                or modified a list of items (skills, modules, APIs, models), provide the COMPLETE LIST
                here. This is FULL OVERWRITE, not append — if you list 40 skills, the file will have
                exactly 40 skills. Always read inventory.md first and merge, don't rely on memory alone.
            conventions_update: Optional. Project-wide conventions (naming, API format, UI tokens, error
                handling patterns). Section-aware merge like other static files. Use ===SECTION===
                delimiters. Use "NO_CHANGE_BECAUSE: [reason]" to skip. Conventions are proactive
                contracts that prevent consistency errors before they happen.
            session_compaction: Optional. Compressed summary of conversation for context overflow recovery.

        Returns:
            Execution report with files updated and git commit status.
        """
        updates = {
            "projectbrief.md": projectbrief_update,
            "systemPatterns.md": systemPatterns_update,
            "techContext.md": techContext_update,
            "activeContext.md": activeContext_update,
            "progress.md": progress_update,
        }

        # Add conventions if provided (optional field — default to NO_CHANGE)
        if conventions_update and conventions_update.strip():
            updates["conventions.md"] = conventions_update
        else:
            updates["conventions.md"] = "NO_CHANGE_BECAUSE: No convention changes this session"

        _audit("aio__force_architect_save", "CALLED")

        # ── Cognitive Gate check: must have read corrections before saving ──
        # Only enforced when corrections.md has a SESSION_KEY (framework is fully set up)
        session_flag = Path(".ai-operation/.session_confirmed")
        corrections_path_check = PROJECT_MAP_DIR / "corrections.md"
        if corrections_path_check.exists():
            corr_check = corrections_path_check.read_text(encoding="utf-8")
            if "SESSION_KEY:" in corr_check and not session_flag.exists():
                _audit("aio__force_architect_save", "REJECTED", "session not confirmed")
                return (
                    "REJECTED: You have not confirmed reading project context.\n"
                    "Read corrections.md, then call aio__confirm_read(session_key=...) first.\n"
                    "This ensures your save reflects awareness of project-specific experience."
                )

        # ── Loop detection ──────────────────────────────────────────
        _loop_warning = ""
        loop_msg = _loop_guard("aio__force_architect_save", activeContext_update[:100])
        if loop_msg:
            if "BLOCKED" in loop_msg:
                _audit("aio__force_architect_save", "LOOP_BLOCKED")
                return loop_msg
            _loop_warning = loop_msg  # will be prepended to result

        # ── Pre-save sanity check: read current file state ──────────
        # Show AI the current file sizes so it can detect if its update
        # is suspiciously smaller than what's already there
        pre_save_state = {}
        for fn in REQUIRED_FILES.values():
            fp = PROJECT_MAP_DIR / fn
            if fp.exists():
                pre_save_state[fn] = len(fp.read_text(encoding="utf-8"))
            else:
                pre_save_state[fn] = 0

        # Check for suspicious data loss: if an update is content (not NO_CHANGE)
        # but much shorter than a previous update to the same file, warn
        for fn, new_content in updates.items():
            stripped = new_content.strip()
            if stripped.upper().startswith("NO_CHANGE"):
                continue
            old_size = pre_save_state.get(fn, 0)
            new_size = len(stripped)
            # If old file has substantial content and new update is tiny, warn
            if old_size > 500 and new_size < old_size * 0.3:
                _audit("aio__force_architect_save", "WARNING",
                       f"{fn} update ({new_size} chars) much smaller than existing ({old_size} chars)")

        # Validate: NO bare "NO_CHANGE" allowed — must provide reason
        # Build static file validation list (conventions is optional, only validate if provided)
        static_validations = {
            "projectbrief_update": projectbrief_update,
            "systemPatterns_update": systemPatterns_update,
            "techContext_update": techContext_update,
        }
        if conventions_update and conventions_update.strip():
            static_validations["conventions_update"] = conventions_update

        for filename, content in static_validations.items():
            stripped = content.strip()
            if stripped == "NO_CHANGE":
                _audit("aio__force_architect_save", "REJECTED", f"{filename} bare NO_CHANGE")
                return (
                    f"REJECTED: {filename} cannot be bare 'NO_CHANGE'.\n"
                    f"You must write 'NO_CHANGE_BECAUSE: [reason]' explaining why this file "
                    f"does not need updating based on what happened in this session.\n"
                    f"This forces you to actually review whether the file needs an update.\n\n"
                    f"Examples:\n"
                    f"  NO_CHANGE_BECAUSE: This session only fixed a UI bug, no vision change\n"
                    f"  NO_CHANGE_BECAUSE: No new modules added, only modified existing IngestNode internals\n"
                    f"  NO_CHANGE_BECAUSE: No new dependencies or tech constraints discovered"
                )

        # Validate: activeContext and progress must never be NO_CHANGE at all
        if "NO_CHANGE" in activeContext_update.strip().upper() and "BECAUSE" not in activeContext_update.upper():
            _audit("aio__force_architect_save", "REJECTED", "activeContext was NO_CHANGE")
            return "REJECTED: activeContext_update cannot be NO_CHANGE. You must always update the current focus."
        if "NO_CHANGE" in progress_update.strip().upper() and "BECAUSE" not in progress_update.upper():
            return "REJECTED: progress_update cannot be NO_CHANGE. You must always record what was done this session."
        if not lessons_learned or not lessons_learned.strip():
            return (
                "REJECTED: lessons_learned cannot be empty.\n"
                "Reflect on this session: any bugs hit, user corrections, gotchas discovered, "
                "or preferences expressed? Use 'NONE' only if truly nothing was learned."
            )

        # ── Information density validation ────────────────────────
        # Reject updates that are too vague to be useful as project memory.
        # A future AI reading these files must be able to pick up exactly where you left off.

        MIN_ACTIVE_CONTEXT_CHARS = 200
        MIN_PROGRESS_CHARS = 150
        MIN_STATIC_UPDATE_CHARS = 100

        ac = activeContext_update.strip()
        if len(ac) < MIN_ACTIVE_CONTEXT_CHARS:
            _audit("aio__force_architect_save", "REJECTED", f"activeContext too short ({len(ac)} chars)")
            return (
                f"REJECTED: activeContext_update is only {len(ac)} chars (minimum {MIN_ACTIVE_CONTEXT_CHARS}).\n\n"
                f"Your update must include:\n"
                f"  - SPECIFIC FILE PATHS that were changed (e.g., src/engine/pipeline_engine.py)\n"
                f"  - WHAT was changed in each file (e.g., 'Node 1 自动扫描 inbox 视频')\n"
                f"  - NEXT STEP with enough detail that a new AI can execute it\n\n"
                f"Think: if a completely new AI reads ONLY this text, can it continue your work?\n"
                f"If not, add more detail."
            )

        pg = progress_update.strip()
        if len(pg) < MIN_PROGRESS_CHARS:
            _audit("aio__force_architect_save", "REJECTED", f"progress too short ({len(pg)} chars)")
            return (
                f"REJECTED: progress_update is only {len(pg)} chars (minimum {MIN_PROGRESS_CHARS}).\n\n"
                f"Each completed task must include the FILE it touched.\n"
                f"Bad:  '✅ 完成了编导功能'\n"
                f"Good: '✅ 新建 skills/director/formula_director.py (~300行): "
                f"round_1_analyze + round_2_adapt + round_3a/3b 并发画面设计'"
            )

        # Check static file updates for minimum substance
        static_content_checks = [
            ("projectbrief_update", projectbrief_update),
            ("systemPatterns_update", systemPatterns_update),
            ("techContext_update", techContext_update),
        ]
        if conventions_update and conventions_update.strip():
            static_content_checks.append(("conventions_update", conventions_update))
        for label, content in static_content_checks:
            stripped = content.strip()
            if stripped.upper().startswith("NO_CHANGE_BECAUSE"):
                continue
            if len(stripped) < MIN_STATIC_UPDATE_CHARS:
                _audit("aio__force_architect_save", "REJECTED", f"{label} too short ({len(stripped)} chars)")
                return (
                    f"REJECTED: {label} is only {len(stripped)} chars (minimum {MIN_STATIC_UPDATE_CHARS}).\n"
                    f"Static file updates must be specific enough to be useful as permanent documentation.\n"
                    f"Include file paths, function names, and architectural reasoning."
                )

        # Check activeContext contains at least one file path indicator
        path_indicators = ["/", ".py", ".js", ".ts", ".md", ".json", ".yaml", ".toml", "src/", "skills/"]
        has_path = any(indicator in ac for indicator in path_indicators)
        if not has_path:
            _audit("aio__force_architect_save", "REJECTED", "activeContext has no file paths")
            return (
                "REJECTED: activeContext_update contains no file paths.\n\n"
                "You must mention the specific files you worked on.\n"
                "Bad:  '完成了编导功能优化'\n"
                "Good: 'src/engine/pipeline_engine.py: Node 2 轨道B 调用 formula_director 三阶编导'"
            )

        # ── Git diff cross-validation ────────────────────────────
        # Compare what AI claims to have changed (activeContext) with
        # what git actually shows as changed. Warn on mismatch.
        try:
            import subprocess as sp_diff
            diff_result = sp_diff.run(
                ["git", "diff", "--name-only"],
                capture_output=True, text=True, timeout=10,
                stdin=sp_diff.DEVNULL
            )
            if diff_result.returncode == 0 and diff_result.stdout.strip():
                changed_in_git = [f.strip() for f in diff_result.stdout.strip().split("\n") if f.strip()]
                # Filter out framework files — only check project code
                project_changes = [f for f in changed_in_git if not f.startswith(".ai-operation/")]
                if project_changes:
                    mentioned = sum(1 for f in project_changes if any(part in ac for part in f.split("/")))
                    if mentioned == 0 and len(project_changes) <= 10:
                        _audit("aio__force_architect_save", "WARNING",
                               f"git shows {len(project_changes)} changed files not mentioned in activeContext")
                        # Will be shown in audit questions
        except Exception:
            pass  # git diff is best-effort, don't block save

        # ── Completion verification gate ──────────────────────────
        # If activeContext claims completion, must include terminal evidence
        completion_keywords = ["完成", "完毕", "done", "completed", "finished", "已完成"]
        evidence_indicators = ["$", ">", "exit code", "output:", "stdout", "stderr", "ls -", "cat ", "wc "]
        ac_lower = ac.lower()
        if any(kw in ac_lower for kw in completion_keywords):
            if not any(ev in ac_lower for ev in evidence_indicators):
                _audit("aio__force_architect_save", "WARNING", "completion claimed without terminal evidence")
                # Warning only, not rejection — prepended to diff preview later

        # ── Pointer format gate for static files ─────────────────
        # systemPatterns should be pointer-style (module + path + short description)
        # Lines > 200 chars without a file path indicator are likely content leaking in
        sp = systemPatterns_update.strip()
        if not sp.upper().startswith("NO_CHANGE"):
            long_content_lines = []
            for line in sp.split("\n"):
                stripped_line = line.strip()
                if len(stripped_line) > 200 and not any(ind in stripped_line for ind in path_indicators):
                    long_content_lines.append(stripped_line[:80] + "...")
            if long_content_lines:
                _audit("aio__force_architect_save", "WARNING",
                       f"systemPatterns has {len(long_content_lines)} lines > 200 chars without file paths")

        # ── Inventory quality gate ────────────────────────────────
        # Warn (not reject) if inventory is still empty after code exploration
        inv_path = PROJECT_MAP_DIR / "inventory.md"
        if inv_path.exists():
            inv_content = inv_path.read_text(encoding="utf-8")
            if inv_content.count("[待填写") >= 2:
                if not inventory_update or not inventory_update.strip() or inventory_update.strip().upper() == "SKIP":
                    # Don't reject — but add a loud warning that will show in diff preview
                    _audit("aio__force_architect_save", "WARNING", "inventory still all placeholders")

        # ══════════════════════════════════════════════════════════
        # PHASE 1: PREPARE — generate diff preview, stage to file
        # Do NOT write to project_map yet. Let AI review first.
        # ══════════════════════════════════════════════════════════
        import json
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        diff_preview = []
        warnings = []
        staged_updates = {}
        skipped_files = []

        for filename, content in updates.items():
            stripped = content.strip()

            if stripped.upper().startswith("NO_CHANGE_BECAUSE:"):
                reason = stripped.split(":", 1)[1].strip() if ":" in stripped else "unspecified"
                skipped_files.append(f"{filename}: {reason[:80]}")
                continue

            filepath = PROJECT_MAP_DIR / filename
            old_content = filepath.read_text(encoding="utf-8") if filepath.exists() else "[file does not exist]"
            old_size = len(old_content)
            new_size = len(stripped)

            # Detect suspicious shrinkage
            if old_size > 500 and new_size < old_size * 0.3:
                warnings.append(
                    f"⚠️ {filename}: new update ({new_size} chars) is much smaller than "
                    f"existing content ({old_size} chars). Possible data loss?"
                )

            # Build diff preview
            diff_preview.append(f"### {filename}")
            diff_preview.append(f"  Current size: {old_size} chars")
            diff_preview.append(f"  Update size:  {new_size} chars")
            diff_preview.append(f"  Update preview: {stripped[:200]}{'...' if len(stripped) > 200 else ''}")
            diff_preview.append("")

            staged_updates[filename] = stripped

        # Stage inventory if provided (but respect NO_CHANGE_BECAUSE)
        inv_stripped = inventory_update.strip() if inventory_update else ""
        if inv_stripped and inv_stripped.upper() != "SKIP" and not inv_stripped.upper().startswith("NO_CHANGE"):
            inv_path = PROJECT_MAP_DIR / "inventory.md"
            old_inv = inv_path.read_text(encoding="utf-8") if inv_path.exists() else ""
            old_count = old_inv.count("- [") if old_inv else 0
            new_count = inventory_update.count("- ") + inventory_update.count("- [")
            if old_count > 0 and new_count < old_count * 0.5:
                warnings.append(
                    f"⚠️ inventory.md: new list has ~{new_count} items but existing has "
                    f"~{old_count} items. Significant reduction — did you read inventory.md first?"
                )
            staged_updates["inventory.md"] = inventory_update.strip()
            diff_preview.append(f"### inventory.md (OVERWRITE)")
            diff_preview.append(f"  Old items: ~{old_count}")
            diff_preview.append(f"  New items: ~{new_count}")
            diff_preview.append("")

        # Stage lessons
        staged_lessons = lessons_learned.strip()

        # Stage compaction
        staged_compaction = session_compaction.strip() if session_compaction else ""

        # Write staging file
        staging_data = {
            "timestamp": timestamp,
            "updates": staged_updates,
            "skipped": skipped_files,
            "lessons": staged_lessons,
            "compaction": staged_compaction,
        }
        SAVE_STAGING_FILE.parent.mkdir(parents=True, exist_ok=True)
        SAVE_STAGING_FILE.write_text(json.dumps(staging_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Build the review report
        report = ["PENDING_REVIEW: Save prepared but NOT yet written.\n"]
        report.append("## Diff Preview\n")
        report.extend(diff_preview)

        if skipped_files:
            report.append("## Skipped (NO_CHANGE_BECAUSE)\n")
            for s in skipped_files:
                report.append(f"  - {s}")
            report.append("")

        if warnings:
            report.append("## ⚠️ SIZE WARNINGS\n")
            for w in warnings:
                report.append(f"  {w}")
            report.append("")

        report.append(f"## Lessons: {staged_lessons[:150]}")
        report.append("")

        # ── Self-Audit Checklist (forced reflection) ─────────────
        # The AI must answer each question before calling confirm.
        # This uses the current AI's own reasoning — no external API needed.
        report.append("## ⚡ MANDATORY SELF-AUDIT (answer before confirming)\n")
        report.append("You MUST think through each question below. If ANY answer is 'no',")
        report.append("call aio__force_architect_save again with corrected content.\n")

        # Build specific audit questions based on what changed
        audit_questions = []

        # Q1: Data completeness
        for fn, content in staged_updates.items():
            old_size = pre_save_state.get(fn, 0)
            new_size = len(content)
            if old_size > 300 and new_size < old_size * 0.5:
                audit_questions.append(
                    f"⚠️ {fn} is shrinking from {old_size} to {new_size} chars. "
                    f"Did you read the current {fn} before writing? Is anything lost?"
                )

        # Q2: Inventory consistency
        inv_path = PROJECT_MAP_DIR / "inventory.md"
        if inv_path.exists():
            inv_content = inv_path.read_text(encoding="utf-8")
            inv_placeholder_count = inv_content.count("[待填写")
            inv_count = inv_content.count("- [")
            if inv_placeholder_count >= 2:
                audit_questions.append(
                    f"⚠️ CRITICAL: inventory.md still has {inv_placeholder_count} unfilled [待填写] sections. "
                    f"You have NO asset inventory. If you scanned or explored the codebase in this session, "
                    f"you MUST populate inventory_update with discovered skills, modules, APIs, and data models. "
                    f"Do NOT leave inventory empty after a code exploration session."
                )
            elif inv_count > 0:
                audit_questions.append(
                    f"inventory.md currently has {inv_count} items. "
                    f"Did this session discover/create any new items that should be added?"
                )

        # Q3: Skipped file justification
        for s in skipped_files:
            audit_questions.append(
                f"You skipped {s}. Given what happened in this session, "
                f"is this truly unchanged?"
            )

        # Q4: Active context accuracy
        audit_questions.append(
            "Does your activeContext_update accurately describe what JUST happened "
            "and what the IMMEDIATE next step is? Compare it against what you actually "
            "did in this conversation."
        )

        # Q5: Progress accuracy
        audit_questions.append(
            "Does your progress_update list ALL tasks completed this session? "
            "Check: did you create files, modify functions, add dependencies, "
            "or make decisions that aren't reflected?"
        )

        # Q6: Conventions consistency
        conv_path = PROJECT_MAP_DIR / "conventions.md"
        if conv_path.exists():
            audit_questions.append(
                "Did this session establish any new naming patterns, API formats, "
                "UI decisions, or error handling conventions? If so, did you update "
                "conventions.md? If you corrected the AI on a consistency issue, "
                "that correction should become a convention."
            )

        # Q7: Completion verification
        if any(kw in ac_lower for kw in completion_keywords):
            if not any(ev in ac_lower for ev in evidence_indicators):
                audit_questions.append(
                    "⚠️ You claim completion but activeContext has no terminal evidence "
                    "(command output, ls, cat, exit code). Add evidence or remove completion claim."
                )

        # Q8: Pointer format
        if not sp.upper().startswith("NO_CHANGE"):
            if long_content_lines:
                audit_questions.append(
                    f"⚠️ systemPatterns has {len(long_content_lines)} lines over 200 chars without file paths. "
                    f"project_map should be pointer-style: module name + file path + one-line description. "
                    f"Move detailed descriptions to the source files themselves."
                )

        # Q9: Git diff cross-validation
        try:
            if project_changes and mentioned == 0:
                audit_questions.append(
                    f"⚠️ git diff shows {len(project_changes)} changed project files "
                    f"({', '.join(project_changes[:5])}) but NONE are mentioned in your "
                    f"activeContext. Are you saving a complete picture of what happened?"
                )
        except NameError:
            pass  # project_changes not defined if git diff failed

        for i, q in enumerate(audit_questions, 1):
            report.append(f"{i}. {q}")
        report.append("")

        report.append(
            "───────────────────────────────────────────\n"
            "After reviewing each question above:\n"
            "  ✅ All correct → call aio__force_architect_save_confirm\n"
            "  ❌ Something wrong → call aio__force_architect_save with fixes"
        )

        _audit("aio__force_architect_save", "PREPARED",
               f"staged={len(staged_updates)}, audit_questions={len(audit_questions)}")
        result = "\n".join(report)
        return f"{_loop_warning}\n\n{result}" if _loop_warning else result

    @mcp.tool()
    def aio__force_architect_save_confirm() -> str:
        """
        [PHASE 2: COMMIT] Execute the staged save after AI self-review.

        This tool MUST be called after aio__force_architect_save returns PENDING_REVIEW.
        It reads the staging file, applies all updates, writes lessons, and commits.

        The two-phase save ensures AI reviews the diff before writing:
        Phase 1 (save): validate + generate diff → PENDING_REVIEW
        Phase 2 (confirm): apply writes + git commit → SUCCESS

        Returns:
            Execution report with files updated and git commit status.
        """
        import json
        import datetime

        _audit("aio__force_architect_save_confirm", "CALLED")

        # ── Loop detection ──────────────────────────────────────────
        loop_msg = _loop_guard("aio__force_architect_save_confirm")
        if loop_msg and "BLOCKED" in loop_msg:
            _audit("aio__force_architect_save_confirm", "LOOP_BLOCKED")
            return loop_msg

        # Read staging file
        if not SAVE_STAGING_FILE.exists():
            return (
                "REJECTED: No staged save found.\n"
                "You must call aio__force_architect_save first to prepare the save."
            )

        staging_data = json.loads(SAVE_STAGING_FILE.read_text(encoding="utf-8"))
        timestamp = staging_data["timestamp"]
        staged_updates = staging_data["updates"]
        staged_lessons = staging_data["lessons"]
        staged_compaction = staging_data.get("compaction", "")

        DYNAMIC_FILE_MAX_BYTES = 8_000  # Compact dynamic files when exceeding 8KB
        STATIC_FILES = {"projectbrief.md", "systemPatterns.md", "techContext.md", "conventions.md"}
        changed_files = []
        merge_report = []

        for filename, content in staged_updates.items():
            filepath = PROJECT_MAP_DIR / filename

            if filename == "inventory.md":
                # Inventory: full overwrite
                inv_content = (
                    f"# Project Inventory (资产清单)\n\n"
                    f"> 上次更新：{timestamp}\n\n---\n\n"
                    f"{content}\n"
                )
                filepath.write_text(inv_content, encoding="utf-8")
                merge_report.append(f"  {filename}: OVERWRITE")

            elif filename in STATIC_FILES:
                # Static files: section-aware merge
                # AI passes content as "section_title: content" pairs separated by ===SECTION===
                # Or as a single block (falls back to append)
                if filepath.exists() and "===SECTION===" in content:
                    existing = filepath.read_text(encoding="utf-8")
                    # Parse section updates from AI content
                    section_updates = {}
                    for section_block in content.split("===SECTION==="):
                        section_block = section_block.strip()
                        if not section_block:
                            continue
                        # First line is the section title hint
                        lines = section_block.split("\n", 1)
                        if len(lines) == 2:
                            section_updates[lines[0].strip()] = lines[1].strip()
                        else:
                            section_updates[lines[0].strip()] = ""

                    merged, changed_sections = _section_merge(existing, section_updates)
                    filepath.write_text(merged, encoding="utf-8")
                    merge_report.append(
                        f"  {filename}: SECTION MERGE ({len(changed_sections)} sections updated: "
                        f"{', '.join(changed_sections) if changed_sections else 'none'})"
                    )
                elif filepath.exists():
                    # No ===SECTION=== delimiter — full overwrite of static file.
                    # APPEND was causing infinite content duplication. Static files
                    # should be replaced entirely when AI provides a full update.
                    # For partial updates, AI MUST use ===SECTION=== delimiters.
                    filepath.write_text(content, encoding="utf-8")
                    merge_report.append(f"  {filename}: OVERWRITE (no section delimiters — use ===SECTION=== for partial updates)")
                else:
                    filepath.write_text(content, encoding="utf-8")
                    merge_report.append(f"  {filename}: CREATED")

            else:
                # Dynamic files (activeContext, progress): append only
                # No auto-compact — cleanup is handled by [整理] skill (human-in-the-loop)
                if filename in ("activeContext.md", "progress.md") and filepath.exists():
                    existing = filepath.read_text(encoding="utf-8")
                    file_bytes = len(existing.encode("utf-8"))
                    if file_bytes > DYNAMIC_FILE_MAX_BYTES:
                        merge_report.append(
                            f"  ⚠️ {filename} is {file_bytes // 1024}KB (>{DYNAMIC_FILE_MAX_BYTES // 1024}KB). "
                            f"Run [整理] to clean up."
                        )

                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(f"\n\n---\n### [MCP Auto-Archive]\n{content}\n")
                merge_report.append(f"  {filename}: APPEND")

            changed_files.append(filename)

        # Auto-split oversized sections to detail subfiles
        split_report = []
        for fn in ["projectbrief.md", "systemPatterns.md", "techContext.md", "conventions.md"]:
            fp = PROJECT_MAP_DIR / fn
            splits = _auto_split_oversized_sections(fp)
            if splits:
                split_report.extend(splits)
                if fn not in changed_files:
                    changed_files.append(fn)
        if split_report:
            merge_report.append("  Auto-split oversized sections:")
            for s in split_report:
                merge_report.append(f"    - {s}")

        # Auto-compact corrections.md if oversized
        corrections_archive = _compact_corrections(PROJECT_MAP_DIR / "corrections.md")
        if corrections_archive:
            merge_report.append(f"  {corrections_archive}")
            if "corrections.md" not in changed_files:
                changed_files.append("corrections.md")

        # ── Write lessons to corrections key-value system ──────────
        # Lessons go to corrections/{key}.md files (values).
        # New keys are registered in corrections.md (index).
        # AI specifies category with "category: lesson text" format.
        # If no category prefix, defaults to "general".
        if staged_lessons and staged_lessons.upper() != "NONE":
            corrections_dir = PROJECT_MAP_DIR.parent / "corrections"
            corrections_dir.mkdir(parents=True, exist_ok=True)
            corrections_index = PROJECT_MAP_DIR / "corrections.md"

            lessons_lines = [l.strip() for l in staged_lessons.split("\n") if l.strip()]
            updated_keys = set()

            for lesson in lessons_lines:
                lesson_text = lesson.lstrip("- ").strip()
                if not lesson_text:
                    continue

                # Parse "category: lesson" format, default to "general"
                if ":" in lesson_text and len(lesson_text.split(":", 1)[0].strip()) < 30:
                    key = lesson_text.split(":", 1)[0].strip().lower().replace(" ", "_")
                    detail = lesson_text.split(":", 1)[1].strip()
                else:
                    key = "general"
                    detail = lesson_text

                # Append to corrections/{key}.md
                key_file = corrections_dir / f"{key}.md"
                if key_file.exists():
                    existing = key_file.read_text(encoding="utf-8")
                    if detail not in existing:
                        with open(key_file, "a", encoding="utf-8") as f:
                            f.write(f"\n- {detail}")
                else:
                    key_file.write_text(f"# {key} 经验\n\n- {detail}\n", encoding="utf-8")

                updated_keys.add(key)

            # Register new keys in corrections.md index
            if corrections_index.exists():
                index_content = corrections_index.read_text(encoding="utf-8")
                for key in updated_keys:
                    if f"- {key}" not in index_content:
                        # Insert before SESSION_KEY line
                        if "SESSION_KEY:" in index_content:
                            index_content = index_content.replace(
                                "SESSION_KEY:",
                                f"- {key}\n\nSESSION_KEY:"
                            )
                        else:
                            index_content += f"\n- {key}\n"
                        corrections_index.write_text(index_content, encoding="utf-8")

                if "corrections.md" not in changed_files:
                    changed_files.append("corrections.md")

            merge_report.append(
                f"  Lessons: {len(lessons_lines)} entries → corrections/{', '.join(updated_keys)}"
            )

        # Write compaction summary
        if staged_compaction:
            compaction_path = PROJECT_MAP_DIR / "activeContext.md"
            with open(compaction_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n### [Session Compaction — {timestamp}]\n{staged_compaction}\n")
            if "activeContext.md" not in changed_files:
                changed_files.append("activeContext.md")

        # ── Regenerate SESSION_KEY for next session ────────────
        # Forces next session's AI to re-read corrections.md to get the new key
        import secrets
        new_key = secrets.token_hex(4)
        corrections_path = PROJECT_MAP_DIR / "corrections.md"
        if corrections_path.exists():
            corr_content = corrections_path.read_text(encoding="utf-8")
            # Replace existing key or append new one
            if "SESSION_KEY:" in corr_content:
                import re as re_key
                corr_content = re_key.sub(r'SESSION_KEY:.*', f'SESSION_KEY: {new_key}', corr_content)
            else:
                corr_content += f"\n\nSESSION_KEY: {new_key}\n"
            corrections_path.write_text(corr_content, encoding="utf-8")
            if "corrections.md" not in changed_files:
                changed_files.append("corrections.md")

        # Invalidate current session confirmation (next session must re-confirm)
        session_flag = Path(".ai-operation/.session_confirmed")
        if session_flag.exists():
            session_flag.unlink()

        # Clean up staging file
        SAVE_STAGING_FILE.unlink()

        # ── Copy last conversation from Claude Code ──────────────
        # Claude Code VSCode stores conversations as .jsonl files in
        # ~/.claude/projects/{project-dir-name}/{session-id}.jsonl
        # We copy the most recently modified .jsonl to sessions/last_conversation.jsonl
        # so the next session can read the full previous conversation.
        session_status = ""
        try:
            import glob as glob_mod
            home = str(Path.home())
            claude_projects_dir = Path(home) / ".claude" / "projects"
            if claude_projects_dir.exists():
                cwd_str = str(Path.cwd())
                # Find matching project directory by checking all project dirs
                best_match = None
                best_match_len = 0
                for proj_dir in claude_projects_dir.iterdir():
                    if not proj_dir.is_dir():
                        continue
                    # Convert dir name back to path fragments for matching
                    # e.g., "c--Users-Administrator-AI-Operation" should match "C:\Users\Administrator\AI-Operation"
                    dir_parts = [p for p in proj_dir.name.split("-") if p]
                    cwd_parts = [p for p in cwd_str.replace("\\", "/").replace(":", "").split("/") if p]
                    # Check if dir_parts match cwd_parts (case-insensitive)
                    if len(dir_parts) == len(cwd_parts):
                        if all(a.lower() == b.lower() for a, b in zip(dir_parts, cwd_parts)):
                            if len(dir_parts) > best_match_len:
                                best_match = proj_dir
                                best_match_len = len(dir_parts)

                if best_match:
                    jsonl_files = sorted(
                        glob_mod.glob(str(best_match / "*.jsonl")),
                        key=lambda f: Path(f).stat().st_mtime,
                        reverse=True
                    )
                    if jsonl_files:
                        sessions_dir = PROJECT_MAP_DIR.parent / "sessions"
                        sessions_dir.mkdir(parents=True, exist_ok=True)
                        dest = sessions_dir / "last_conversation.jsonl"
                        import shutil
                        shutil.copy2(jsonl_files[0], str(dest))
                        size_kb = Path(jsonl_files[0]).stat().st_size // 1024
                        session_status = f"conversation saved ({size_kb}KB)"
                        merge_report.append(f"  Session: copied {Path(jsonl_files[0]).name} → sessions/last_conversation.jsonl ({size_kb}KB)")
        except Exception as e:
            session_status = f"session copy failed: {str(e)[:80]}"

        # ── Universal size limit enforcement (last safety net) ────
        # Catches ANY file that exceeded MAX_FILE_CHARS after all writes,
        # regardless of whether it has ## headers or not.
        for fn in list(REQUIRED_FILES.values()) + ["corrections.md"]:
            fp = PROJECT_MAP_DIR / fn
            overflow_result = _enforce_file_size_limit(fp)
            if overflow_result:
                merge_report.append(f"  ⚠️ {overflow_result}")
                if fn not in changed_files:
                    changed_files.append(fn)

        # Git commit — non-blocking fire-and-forget on Windows
        # WHY: subprocess.run(timeout=N) with capture_output=True deadlocks on Windows
        # when git spawns child processes. Python kills the parent but children hold the
        # pipe open, causing communicate() to block forever. The only safe approach is
        # Popen without waiting — files are already written, git commit is best-effort.
        git_status = "not attempted"
        git_diag = {}
        try:
            import shutil
            import time

            _set_mcp_flag()

            # ── Diagnostics: capture environment BEFORE any git calls ──
            git_diag["cwd"] = str(Path.cwd())
            git_diag["project_map_dir"] = str(PROJECT_MAP_DIR.resolve()) if PROJECT_MAP_DIR.exists() else "MISSING"
            git_diag["git_path"] = shutil.which("git") or "NOT FOUND"
            git_diag["files_exist"] = {}

            files_to_add = []
            for cf in changed_files:
                filepath = PROJECT_MAP_DIR / cf
                git_diag["files_exist"][cf] = filepath.exists()
                if filepath.exists():
                    files_to_add.append(str(filepath))
            if DETAILS_DIR.exists():
                for df in DETAILS_DIR.glob("*.md"):
                    files_to_add.append(str(df))

            git_diag["files_to_add_count"] = len(files_to_add)

            if files_to_add:
                # DEVNULL only — PIPE deadlocks on Windows (confirmed twice)
                t0 = time.time()
                add_proc = subprocess.Popen(
                    ["git", "add"] + files_to_add,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                try:
                    add_proc.wait(timeout=60)
                    git_diag["add_time"] = f"{time.time() - t0:.1f}s"
                    git_diag["add_rc"] = add_proc.returncode
                except subprocess.TimeoutExpired:
                    add_proc.kill()
                    add_proc.wait()
                    git_diag["add_time"] = f"{time.time() - t0:.1f}s (TIMEOUT)"
                    git_status = "git add timed out"

                if add_proc.returncode == 0:
                    commit_msg = f"chore: architect save [{', '.join(changed_files)}]"
                    t1 = time.time()
                    commit_proc = subprocess.Popen(
                        ["git", "commit", "--no-verify", "--no-status", "-m", commit_msg, "--"] + files_to_add,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    try:
                        commit_proc.wait(timeout=30)
                        git_diag["commit_time"] = f"{time.time() - t1:.1f}s"
                        git_diag["commit_rc"] = commit_proc.returncode
                        if commit_proc.returncode == 0:
                            git_status = "committed"
                        else:
                            git_status = f"commit exited {commit_proc.returncode}"
                    except subprocess.TimeoutExpired:
                        commit_proc.kill()
                        commit_proc.wait()
                        git_diag["commit_time"] = f"{time.time() - t1:.1f}s (TIMEOUT)"
                        git_status = "commit timed out — run manually"
        except Exception as e:
            git_status = f"error: {str(e)[:100]}"
        finally:
            _clear_mcp_flag()
            if TASKSPEC_APPROVED_FLAG.exists():
                TASKSPEC_APPROVED_FLAG.unlink()
            if FAST_TRACK_FLAG.exists():
                FAST_TRACK_FLAG.unlink()

        # Format diagnostics for debugging
        diag_str = ""
        if git_status != "committed" and git_diag:
            import json as json_mod
            diag_str = f"\n\nGit Diagnostics (for debugging):\n{json_mod.dumps(git_diag, indent=2, ensure_ascii=False)}"

        _audit("aio__force_architect_save_confirm", "SUCCESS",
               f"files={','.join(changed_files)},git={git_status},cwd={git_diag.get('cwd','?')}")
        return (
            f"SUCCESS\n"
            f"Files updated: {', '.join(changed_files)}\n"
            f"Merge details:\n" + "\n".join(merge_report) + "\n\n"
            f"Git: {git_status}\n"
            f"{'Run `git add .ai-operation/docs/project_map/ && git commit -m \"save\"` if git failed.' if git_status != 'committed' else 'TaskSpec approval cleared.'}"
            f"{diag_str}"
        )
