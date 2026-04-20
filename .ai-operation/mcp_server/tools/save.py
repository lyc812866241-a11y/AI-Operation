"""
Save tools -- two-phase architect save protocol.
Contains: aio__force_architect_save, aio__force_architect_save_confirm
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *
from .cognitive_gate import is_save_pending, set_save_pending, clear_save_pending
from .bypass import has_bypass


class _SaveAbort(Exception):
    """Internal signal used by save Phase 2 guards to abort the write loop
    with a user-facing REJECTED message. Caller restores from snapshot
    and returns the message verbatim -- do NOT re-raise.
    """


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

        Section-title matching: leading "N. " numeric prefixes are ignored on BOTH sides.
        Example: the file has "## 1. 当前焦点", you pass `===SECTION===\n当前焦点\n...` -- matches.
        If ZERO sections match, the tool REJECTS the call (no silent no-op) and lists the actual
        section titles in the file so you can fix your keys.

        If you provide content WITHOUT any ===SECTION=== delimiters for a file that already has
        `##` sections, the tool REJECTS to prevent accidental full-file wipe. To deliberately
        REPLACE the entire file, prefix your content with `FULL_OVERWRITE_CONFIRMED:` on its
        own first line -- this explicit opt-in is the only path to total overwrite.

        Files that do NOT yet have any `##` sections (fresh templates, new files) accept raw
        content without delimiters -- that's the bootstrap path.

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
          "完成了三阶编导，继续优化生图"  <- too vague, no file paths, no details

        Args:
            projectbrief_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            systemPatterns_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            techContext_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            activeContext_update: REQUIRED. See detail requirements above. Min 200 chars.
            progress_update: REQUIRED. Each task with file path. Min 150 chars.
            lessons_learned: REQUIRED. Lessons from this session. "NONE" only if truly nothing learned.
            inventory_update: **FULL OVERWRITE MODE** -- whatever you pass replaces the entire
                inventory.md body. For INCREMENTAL additions (single new skill, module, API) use
                `aio__inventory_append` instead -- that's the safe path. Use this `inventory_update`
                parameter only when you intentionally rebuild the full list from scratch (e.g. after
                [整理]). If you use it: ALWAYS read inventory.md first, merge by hand, then pass the
                COMPLETE list here. Passing partial content will erase everything you didn't include.
            conventions_update: Optional. SECOND-ORDER contracts only (naming, API format, UI tokens,
                code style) -- structural rules that prevent a CLASS of bugs. Do NOT put specific
                incident lessons here (those go in corrections/{key}.md as first-order experience).
                Section-aware merge. Use ===SECTION=== delimiters. "NO_CHANGE_BECAUSE: [reason]" to skip.
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

        # Add conventions if provided (optional field -- default to NO_CHANGE)
        if conventions_update and conventions_update.strip():
            updates["conventions.md"] = conventions_update
        else:
            updates["conventions.md"] = "NO_CHANGE_BECAUSE: No convention changes this session"

        _audit("aio__force_architect_save", "CALLED")

        # -- Self-heal .gitignore before anything else ---------------
        # If the project's .gitignore is blocking project_map, auto-fix it
        # now so the Phase 2 commit can land without user intervention.
        try:
            gi_actions = _check_and_heal_gitignore(_audit)
            if gi_actions:
                _audit("aio__force_architect_save", "AUTO_FIX",
                       f"gitignore: {'; '.join(gi_actions)}")
        except Exception as e:
            _audit("aio__force_architect_save", "AUTO_FIX_ERROR", str(e)[:200])

        # -- Re-entrancy guard: only one save at a time --
        if is_save_pending():
            _audit("aio__force_architect_save", "REJECTED", "save already pending")
            return (
                "REJECTED: A save is already pending confirmation.\n"
                "Call aio__force_architect_save_confirm to complete the current save first,\n"
                "or wait for it to finish before starting a new one."
            )
        # -- Cognitive Gate check: must have read corrections before saving --
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

        # -- Loop detection ------------------------------------------
        _loop_warning = ""
        loop_msg = _loop_guard("aio__force_architect_save", activeContext_update[:100])
        if loop_msg:
            if "BLOCKED" in loop_msg:
                _audit("aio__force_architect_save", "LOOP_BLOCKED")
                return loop_msg
            _loop_warning = loop_msg  # will be prepended to result

        # -- Pre-save sanity check: read current file state ----------
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

        # Validate: NO bare "NO_CHANGE" allowed -- must provide reason
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
        # -- Auto-reflection: scan audit.log for session violations --
        # If AI was rejected/blocked/bypassed this session, it cannot claim "NONE" learned.
        session_violations = []
        audit_path = Path(".ai-operation/audit.log")
        if audit_path.exists():
            import json as _json
            try:
                log_lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
                # Read session_confirmed timestamp to filter current session only
                session_flag = Path(".ai-operation/.session_confirmed")
                # Scan last 100 lines (current session is recent)
                for line in log_lines[-100:]:
                    try:
                        entry = _json.loads(line)
                        status = entry.get("status", "")
                        if status in ("REJECTED", "BLOCKED", "BYPASSABLE", "BYPASSED",
                                      "BYPASS_GRANTED", "MONITOR", "LOOP_BLOCKED",
                                      "DANGEROUS_BLOCKED"):
                            tool = entry.get("tool", "")
                            details = entry.get("details", "")[:100]
                            session_violations.append(f"{tool}: {status} -- {details}")
                    except _json.JSONDecodeError:
                        continue
            except Exception:
                pass  # audit reading is best-effort

        if not lessons_learned or not lessons_learned.strip():
            if session_violations:
                violation_list = "\n".join(f"  - {v}" for v in session_violations[-10:])
                return (
                    f"REJECTED: lessons_learned cannot be empty.\n"
                    f"You were blocked/rejected {len(session_violations)} time(s) this session:\n"
                    f"{violation_list}\n\n"
                    f"Reflect on these violations. What caused them? How to avoid next time?\n"
                    f"Write lessons in 'category: lesson' format (e.g., 'fileops: always check encoding')."
                )
            return (
                "REJECTED: lessons_learned cannot be empty.\n"
                "Reflect on this session: any bugs hit, user corrections, gotchas discovered, "
                "or preferences expressed? Use 'NONE' only if truly nothing was learned."
            )

        # If AI wrote "NONE" but had violations, force reflection
        if lessons_learned.strip().upper() == "NONE" and session_violations:
            violation_list = "\n".join(f"  - {v}" for v in session_violations[-10:])
            return (
                f"REJECTED: You wrote 'NONE' but were blocked/rejected {len(session_violations)} time(s):\n"
                f"{violation_list}\n\n"
                f"You MUST reflect on these violations. 'NONE' is only valid when\n"
                f"you had zero rejections/blocks in this session."
            )

        # -- Information density validation ------------------------
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
                f"Bad:  '[OK] 完成了编导功能'\n"
                f"Good: '[OK] 新建 skills/director/formula_director.py (~300行): "
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

        # -- Git diff cross-validation ----------------------------
        # Compare what AI claims to have changed (activeContext) with
        # what git actually shows as changed. Warn on mismatch.
        project_changes = []
        mentioned = 0
        try:
            import subprocess as sp_diff
            diff_result = sp_diff.run(
                ["git", "diff", "--name-only"],
                capture_output=True, text=True, timeout=10,
                stdin=sp_diff.DEVNULL
            )
            if diff_result.returncode == 0 and diff_result.stdout.strip():
                changed_in_git = [f.strip() for f in diff_result.stdout.strip().split("\n") if f.strip()]
                # Filter out framework files -- only check project code
                project_changes = [f for f in changed_in_git if not f.startswith(".ai-operation/")]
                if project_changes:
                    mentioned = sum(1 for f in project_changes if any(part in ac for part in f.split("/")))
                    if mentioned == 0 and len(project_changes) <= 10:
                        _audit("aio__force_architect_save", "WARNING",
                               f"git shows {len(project_changes)} changed files not mentioned in activeContext")
                        # Will be shown in audit questions
        except Exception:
            pass  # git diff is best-effort, don't block save

        # -- Completion verification gate --------------------------
        # If activeContext claims completion, must include terminal evidence
        completion_keywords = ["完成", "完毕", "done", "completed", "finished", "已完成"]
        evidence_indicators = ["$", ">", "exit code", "output:", "stdout", "stderr", "ls -", "cat ", "wc "]
        ac_lower = ac.lower()
        if any(kw in ac_lower for kw in completion_keywords):
            if not any(ev in ac_lower for ev in evidence_indicators):
                _audit("aio__force_architect_save", "WARNING", "completion claimed without terminal evidence")
                # Warning only, not rejection -- prepended to diff preview later

        # -- Pointer format gate for static files -----------------
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

        # -- Inventory quality gate --------------------------------
        # Warn (not reject) if inventory is still empty after code exploration
        inv_path = PROJECT_MAP_DIR / "inventory.md"
        if inv_path.exists():
            inv_content = inv_path.read_text(encoding="utf-8")
            if inv_content.count("[待填写") >= 2:
                if not inventory_update or not inventory_update.strip() or inventory_update.strip().upper() == "SKIP":
                    # Don't reject -- but add a loud warning that will show in diff preview
                    _audit("aio__force_architect_save", "WARNING", "inventory still all placeholders")

        # -- Ingest propagation check ------------------------------
        # If AI created new files this session but inventory_update is NO_CHANGE,
        # warn that new assets should be reflected in inventory.
        # (Karpathy LLM Wiki pattern: one change should propagate to all related pages)
        audit_path = Path(".ai-operation/audit.log")
        if audit_path.exists():
            import json as _jcheck
            new_files_created = []
            try:
                log_lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
                for line in log_lines[-100:]:
                    try:
                        entry = _jcheck.loads(line)
                        if entry.get("tool") == "Write" and entry.get("status") == "EXECUTED":
                            detail = entry.get("details", "")
                            # Only flag non-framework files
                            if detail and not detail.startswith(".ai-operation/"):
                                new_files_created.append(detail[:80])
                    except _jcheck.JSONDecodeError:
                        continue
            except Exception:
                pass

            inv_is_skip = (
                not inventory_update
                or not inventory_update.strip()
                or inventory_update.strip().upper().startswith("NO_CHANGE")
                or inventory_update.strip().upper() == "SKIP"
            )
            if new_files_created and inv_is_skip and not has_bypass("save.ingest_propagation"):
                file_list = "\n".join(f"  - {f}" for f in new_files_created[:10])
                _audit("aio__force_architect_save", "WARNING",
                       f"ingest_propagation: {len(new_files_created)} new files but inventory NO_CHANGE")
                return (
                    f"BYPASSABLE: You created {len(new_files_created)} new file(s) this session "
                    f"but inventory_update is NO_CHANGE:\n{file_list}\n\n"
                    f"Rule: save.ingest_propagation\n\n"
                    f"New files/modules/APIs should be reflected in inventory_update.\n"
                    f"Option 1: Add them to inventory_update and resubmit.\n"
                    f"Option 2: If these are temporary/test files, bypass via aio__bypass_violation(\n"
                    f"  rule_code=\"save.ingest_propagation\", user_said=\"<reason>\")"
                )

        # ==========================================================
        # PHASE 1: PREPARE -- generate diff preview, stage to file
        # Do NOT write to project_map yet. Let AI review first.
        # ==========================================================
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
                    f"[!] {filename}: new update ({new_size} chars) is much smaller than "
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
                    f"[!] inventory.md: new list has ~{new_count} items but existing has "
                    f"~{old_count} items. Significant reduction -- did you read inventory.md first?"
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
        set_save_pending()  # Lock: prevent concurrent saves until confirm/reject

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
            report.append("## [!] SIZE WARNINGS\n")
            for w in warnings:
                report.append(f"  {w}")
            report.append("")

        report.append(f"## Lessons: {staged_lessons[:150]}")
        report.append("")

        # -- Self-Audit Checklist (forced reflection) -------------
        # The AI must answer each question before calling confirm.
        # This uses the current AI's own reasoning -- no external API needed.
        report.append("## [!] MANDATORY SELF-AUDIT (answer before confirming)\n")
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
                    f"[!] {fn} is shrinking from {old_size} to {new_size} chars. "
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
                    f"[!] CRITICAL: inventory.md still has {inv_placeholder_count} unfilled [待填写] sections. "
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
                "Knowledge hierarchy check: Did this session produce new lessons?\n"
                "  - Structural rules (naming/API/style that prevent a CLASS of bugs) "
                "-> conventions.md (二阶契约)\n"
                "  - Specific incident lessons (one-time pitfall) "
                "-> corrections/{key}.md (一阶经验)\n"
                "  Do NOT put specific operational lessons in conventions.md."
            )

        # Q7: Completion verification
        if any(kw in ac_lower for kw in completion_keywords):
            if not any(ev in ac_lower for ev in evidence_indicators):
                audit_questions.append(
                    "[!] You claim completion but activeContext has no terminal evidence "
                    "(command output, ls, cat, exit code). Add evidence or remove completion claim."
                )

        # Q8: Pointer format
        if not sp.upper().startswith("NO_CHANGE"):
            if long_content_lines:
                audit_questions.append(
                    f"[!] systemPatterns has {len(long_content_lines)} lines over 200 chars without file paths. "
                    f"project_map should be pointer-style: module name + file path + one-line description. "
                    f"Move detailed descriptions to the source files themselves."
                )

        # Q9: TaskSpec progress check
        taskspec_path = TASKSPEC_FILE
        if taskspec_path.exists():
            taskspec_content = taskspec_path.read_text(encoding="utf-8")
            if len(taskspec_content) > 50:
                audit_questions.append(
                    f"[!] Active taskSpec found. Review your approved plan:\n"
                    f"{taskspec_content[:500]}{'...' if len(taskspec_content) > 500 else ''}\n\n"
                    f"Check: which items are done? Which are not? "
                    f"Does your progress_update accurately reflect this?"
                )

        # Q10: Git diff cross-validation
        if project_changes and mentioned == 0:
            audit_questions.append(
                f"[!] git diff shows {len(project_changes)} changed project files "
                f"({', '.join(project_changes[:5])}) but NONE are mentioned in your "
                f"activeContext. Are you saving a complete picture of what happened?"
            )

        for i, q in enumerate(audit_questions, 1):
            report.append(f"{i}. {q}")
        report.append("")

        report.append(
            "-------------------------------------------\n"
            "After reviewing each question above:\n"
            "  [OK] All correct -> call aio__force_architect_save_confirm\n"
            "  [X] Something wrong -> call aio__force_architect_save with fixes"
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
        Phase 1 (save): validate + generate diff -> PENDING_REVIEW
        Phase 2 (confirm): apply writes + git commit -> SUCCESS

        Returns:
            Execution report with files updated and git commit status.
        """
        import json
        import datetime

        _audit("aio__force_architect_save_confirm", "CALLED")

        # -- Loop detection ------------------------------------------
        loop_msg = _loop_guard("aio__force_architect_save_confirm")
        if loop_msg and "BLOCKED" in loop_msg:
            _audit("aio__force_architect_save_confirm", "LOOP_BLOCKED")
            return loop_msg

        # Read staging file
        if not SAVE_STAGING_FILE.exists():
            clear_save_pending()
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

        # Phase 2 snapshot -- snapshots every .md under project_map/ before we
        # write. On exception (see outer try), we restore so AI never leaves
        # project_map half-corrupted.
        snapshot_ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        try:
            snapshot_dir = _snapshot_project_map(snapshot_ts)
        except Exception as e:
            snapshot_dir = None
            _audit("aio__force_architect_save_confirm", "SNAPSHOT_ERROR", str(e)[:200])

        try:
            for filename, content in staged_updates.items():
                filepath = PROJECT_MAP_DIR / filename

                if filename == "inventory.md":
                    # Inventory: full overwrite (documented in tool docstring).
                    inv_content = (
                        f"# Project Inventory (资产清单)\n\n"
                        f"> 上次更新：{timestamp}\n\n---\n\n"
                        f"{content}\n"
                    )
                    filepath.write_text(inv_content, encoding="utf-8")
                    merge_report.append(f"  {filename}: OVERWRITE")

                elif filename in STATIC_FILES:
                    # Static files: section-aware merge with defensive guards.
                    #
                    # Decision tree (prevents the three footguns observed in the
                    # wild -- silent zero-match, silent full-wipe, docstring
                    # saying APPEND while code OVERWRITE-d):
                    #   (a) FULL_OVERWRITE_CONFIRMED: prefix -> explicit OVERWRITE
                    #   (b) ===SECTION=== delimiters present -> merge; zero-match
                    #       is REJECTED with diagnostic (actual titles vs keys)
                    #   (c) existing file has `##` sections but no delimiters and
                    #       no confirm prefix -> REJECTED (would wipe the file)
                    #   (d) no existing sections (fresh template) -> OVERWRITE/CREATE
                    OVERWRITE_SENTINEL = "FULL_OVERWRITE_CONFIRMED:"
                    content_head = content.lstrip()

                    if content_head.startswith(OVERWRITE_SENTINEL):
                        # (a) explicit opt-in to full replace
                        body = content_head[len(OVERWRITE_SENTINEL):].lstrip("\n").lstrip()
                        filepath.write_text(body, encoding="utf-8")
                        merge_report.append(
                            f"  {filename}: FULL_OVERWRITE applied (explicit opt-in)"
                        )

                    elif filepath.exists() and "===SECTION===" in content:
                        # (b) section-aware merge; guard against zero-match.
                        existing = filepath.read_text(encoding="utf-8")
                        section_updates = {}
                        for section_block in content.split("===SECTION==="):
                            section_block = section_block.strip()
                            if not section_block:
                                continue
                            lines = section_block.split("\n", 1)
                            if len(lines) == 2:
                                section_updates[lines[0].strip()] = lines[1].strip()
                            else:
                                section_updates[lines[0].strip()] = ""

                        merged, changed_sections = _section_merge(existing, section_updates)

                        non_skip_keys = [
                            k for k, v in section_updates.items()
                            if v.strip().upper() != "SKIP"
                        ]
                        if non_skip_keys and not changed_sections:
                            # Zero-match silent no-op -- refuse instead of pretending success.
                            actual_titles = _extract_section_titles(existing)
                            actual_list = ", ".join(actual_titles) if actual_titles else "(none)"
                            keys_list = ", ".join(non_skip_keys)
                            _audit("aio__force_architect_save_confirm", "REJECTED",
                                   f"{filename} zero section match: keys={keys_list}")
                            raise _SaveAbort(
                                f"REJECTED: {filename} -- 0 of {len(non_skip_keys)} section updates matched.\n"
                                f"  Your keys:     [{keys_list}]\n"
                                f"  Actual titles: [{actual_list}]\n"
                                f"  Fix: copy the exact section name from the file "
                                f"(numeric prefixes like '1.' are auto-stripped on BOTH sides,\n"
                                f"  so don't include them; match the text after the number)."
                            )

                        filepath.write_text(merged, encoding="utf-8")
                        merge_report.append(
                            f"  {filename}: SECTION MERGE ({len(changed_sections)} sections updated: "
                            f"{', '.join(changed_sections) if changed_sections else 'none'})"
                        )

                    elif filepath.exists():
                        existing = filepath.read_text(encoding="utf-8")
                        existing_titles = _extract_section_titles(existing)
                        if existing_titles:
                            # (c) file has structure, AI passed a blob with no delimiters
                            # -> would wipe the file. Refuse.
                            _audit("aio__force_architect_save_confirm", "REJECTED",
                                   f"{filename} blob update on structured file")
                            raise _SaveAbort(
                                f"REJECTED: {filename} already has {len(existing_titles)} sections "
                                f"({', '.join(existing_titles[:5])}{'...' if len(existing_titles) > 5 else ''}) "
                                f"but you passed content with no ===SECTION=== delimiters.\n"
                                f"  This would WIPE the whole file. Two valid paths:\n"
                                f"  (1) Partial update: re-submit using ===SECTION===\\ntitle\\ncontent "
                                f"blocks, one per section you want to change.\n"
                                f"  (2) Full replace: prefix the very first line with "
                                f"'FULL_OVERWRITE_CONFIRMED:' -- this is the explicit opt-in."
                            )
                        # (d) template-shaped file (no `##` headers) -> overwrite safely
                        filepath.write_text(content, encoding="utf-8")
                        merge_report.append(
                            f"  {filename}: OVERWRITE (template shape -- no existing sections)"
                        )
                    else:
                        filepath.write_text(content, encoding="utf-8")
                        merge_report.append(f"  {filename}: CREATED")

                else:
                    # Dynamic files (activeContext, progress): append only
                    # No auto-compact -- cleanup is handled by [整理] skill (human-in-the-loop)
                    if filename in ("activeContext.md", "progress.md") and filepath.exists():
                        existing = filepath.read_text(encoding="utf-8")
                        file_bytes = len(existing.encode("utf-8"))
                        if file_bytes > DYNAMIC_FILE_MAX_BYTES:
                            merge_report.append(
                                f"  [!] {filename} is {file_bytes // 1024}KB (>{DYNAMIC_FILE_MAX_BYTES // 1024}KB). "
                                f"Run [整理] to clean up."
                            )

                    with open(filepath, "a", encoding="utf-8") as f:
                        f.write(f"\n\n---\n### [MCP Auto-Archive]\n{content}\n")
                    merge_report.append(f"  {filename}: APPEND")

                changed_files.append(filename)
        except _SaveAbort as e:
            # Our own guard fired. Restore from snapshot so earlier-iteration
            # writes don't leave project_map in a partial state.
            restored = _restore_from_snapshot(snapshot_dir) if snapshot_dir else []
            clear_save_pending()
            _audit("aio__force_architect_save_confirm", "ABORTED",
                   f"restored={len(restored)}")
            return (
                f"{e}\n\n"
                f"(no permanent changes -- {len(restored)} files restored from "
                f"snapshot {snapshot_ts})"
            )
        except Exception as e:
            # Unexpected error during Phase 2 writes. Roll back everything.
            restored = _restore_from_snapshot(snapshot_dir) if snapshot_dir else []
            clear_save_pending()
            _audit("aio__force_architect_save_confirm", "RESTORED",
                   f"error={str(e)[:120]} restored={len(restored)}")
            return (
                f"RESTORED: Phase 2 failed -- {str(e)[:200]}\n"
                f"Restored {len(restored)} files from snapshot {snapshot_ts}.\n"
                f"The save did NOT land; re-run aio__force_architect_save to try again."
            )

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

        # -- Write lessons to corrections key-value system ----------
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
                f"  Lessons: {len(lessons_lines)} entries -> corrections/{', '.join(updated_keys)}"
            )

        # Write compaction summary
        if staged_compaction:
            compaction_path = PROJECT_MAP_DIR / "activeContext.md"
            with open(compaction_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n### [Session Compaction -- {timestamp}]\n{staged_compaction}\n")
            if "activeContext.md" not in changed_files:
                changed_files.append("activeContext.md")

        # -- Regenerate SESSION_KEY for next session ------------
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

        # Clean up staging file and save-pending lock
        SAVE_STAGING_FILE.unlink()
        clear_save_pending()

        # -- Universal size limit enforcement (last safety net) ----
        # Catches ANY file that exceeded MAX_FILE_CHARS after all writes,
        # regardless of whether it has ## headers or not.
        for fn in list(REQUIRED_FILES.values()) + ["corrections.md"]:
            fp = PROJECT_MAP_DIR / fn
            overflow_result = _enforce_file_size_limit(fp)
            if overflow_result:
                merge_report.append(f"  [!] {overflow_result}")
                if fn not in changed_files:
                    changed_files.append(fn)

        # Self-heal .gitignore again in Phase 2 (idempotent). If a third
        # party wrote to .gitignore between Phase 1 and Phase 2 and re-blocked
        # project_map, catch it here.
        try:
            gi_actions_p2 = _check_and_heal_gitignore(_audit)
            if gi_actions_p2:
                _audit("aio__force_architect_save_confirm", "AUTO_FIX",
                       f"gitignore: {'; '.join(gi_actions_p2)}")
        except Exception as e:
            _audit("aio__force_architect_save_confirm", "AUTO_FIX_ERROR", str(e)[:200])

        # Build files_to_add for git commit.
        files_exist = {}
        files_to_add = []
        for cf in changed_files:
            filepath = PROJECT_MAP_DIR / cf
            files_exist[cf] = filepath.exists()
            if filepath.exists():
                files_to_add.append(str(filepath))
        if DETAILS_DIR.exists():
            for df in DETAILS_DIR.glob("*.md"):
                files_to_add.append(str(df))

        # If .gitignore is modified vs HEAD (heal may have touched it, or a
        # prior phase did), include it in this commit so the fix is persisted.
        try:
            diff_check = subprocess.run(
                ["git", "diff", "HEAD", "--name-only", ".gitignore"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                text=True,
            )
            if diff_check.returncode == 0 and diff_check.stdout.strip():
                files_to_add.append(".gitignore")
        except Exception:
            pass

        # Non-blocking commit via shared helper (git add -f + stderr capture
        # + flag transaction all live in constants.py now).
        commit_msg = f"chore: architect save [{', '.join(changed_files)}]"
        git_status, git_diag = git_commit_nonblocking(files_to_add, commit_msg, _audit)
        git_diag["files_exist"] = files_exist

        # Format diagnostics for debugging
        diag_str = ""
        if git_status != "committed" and git_diag:
            import json as json_mod
            diag_str = f"\n\nGit Diagnostics (for debugging):\n{json_mod.dumps(git_diag, indent=2, ensure_ascii=False)}"

        _audit("aio__force_architect_save_confirm", "SUCCESS",
               f"files={','.join(changed_files)},git={git_status},cwd={git_diag.get('cwd','?')}")
        git_hint = 'Run `git add .ai-operation/docs/project_map/ && git commit -m "save"` if git failed.' if git_status != 'committed' else 'TaskSpec approval cleared.'
        return (
            f"SUCCESS\n"
            f"Files updated: {', '.join(changed_files)}\n"
            f"Merge details:\n" + "\n".join(merge_report) + "\n\n"
            f"Git: {git_status}\n"
            f"{git_hint}"
            f"{diag_str}"
        )
