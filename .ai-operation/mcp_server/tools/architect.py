"""
Architect Enforcement Tools (AI-Operation Framework)
=====================================================
MCP tools that enforce Level 4 Architect protocols.
All tool names use the `aio__` namespace prefix to avoid conflicts
with user project MCP tools.

The AI cannot bypass these tools. It MUST call them to complete the operation.
This is the "AI creates its own shackles and wears them" mechanism.
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Project map directory - relative to project root
PROJECT_MAP_DIR = Path(".ai-operation/docs/project_map")

# Flag file used to signal pre-commit hook that MCP tool is making the commit
MCP_COMMIT_FLAG = Path(".ai-operation/.mcp_commit_flag")

# Prompt budget limits (inspired by Claude Code internals)
MAX_FILE_CHARS = 4_000       # Max chars per project_map file injected into prompt
MAX_TOTAL_CHARS = 12_000     # Max total chars across all files

# TaskSpec workflow enforcement
TASKSPEC_DIR = Path(".ai-operation/docs")
TASKSPEC_FILE = TASKSPEC_DIR / "taskSpec.md"
TASKSPEC_APPROVED_FLAG = Path(".ai-operation/.taskspec_approved")
FAST_TRACK_FLAG = Path(".ai-operation/.fast_track")


def _set_mcp_flag():
    """Create flag file so git pre-commit hook allows project_map commits."""
    MCP_COMMIT_FLAG.parent.mkdir(parents=True, exist_ok=True)
    MCP_COMMIT_FLAG.write_text("mcp_tool_commit", encoding="utf-8")


def _clear_mcp_flag():
    """Remove flag file after commit."""
    if MCP_COMMIT_FLAG.exists():
        MCP_COMMIT_FLAG.unlink()

# The 5 canonical files defined in .clinerules
REQUIRED_FILES = {
    "projectbrief": "projectbrief.md",
    "systemPatterns": "systemPatterns.md",
    "techContext": "techContext.md",
    "activeContext": "activeContext.md",
    "progress": "progress.md",
}


def register_architect_tools(mcp: FastMCP):
    """Register all architect enforcement tools onto the MCP server instance."""

    @mcp.tool()
    def aio__force_architect_save(
        projectbrief_update: str,
        systemPatterns_update: str,
        techContext_update: str,
        activeContext_update: str,
        progress_update: str,
        session_compaction: str = "",
    ) -> str:
        """
        [CRITICAL ENFORCEMENT TOOL] Execute the Level 4 Architect Save Protocol.

        This tool MUST be called when the user issues the [存档] command.
        The AI agent MUST NOT manually edit project_map files or run git commands directly.
        All 5 update parameters are REQUIRED. Use "NO_CHANGE" only if that file truly has no updates.

        Args:
            projectbrief_update: Updates to core vision or business goals. "NO_CHANGE" if none.
            systemPatterns_update: New architectural rules discovered. "NO_CHANGE" if none.
            techContext_update: New tech stack constraints discovered. "NO_CHANGE" if none.
            activeContext_update: REQUIRED. Current focus, what was just done, immediate next steps.
            progress_update: REQUIRED. Tasks completed this session, updated TODO items.
            session_compaction: Optional. A compressed summary of the current conversation session.
                Include: tools used, key files modified, decisions made, pending work.
                This is written to activeContext.md as a recovery point for context window overflow.

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

        # Validate: activeContext and progress must never be NO_CHANGE
        if activeContext_update.strip() == "NO_CHANGE":
            return "REJECTED: activeContext_update cannot be NO_CHANGE. You must always update the current focus."
        if progress_update.strip() == "NO_CHANGE":
            return "REJECTED: progress_update cannot be NO_CHANGE. You must always record what was done this session."

        # Apply surgical updates (append-only to preserve history)
        changed_files = []
        for filename, content in updates.items():
            if content.strip() != "NO_CHANGE":
                filepath = PROJECT_MAP_DIR / filename
                if not filepath.parent.exists():
                    return f"FAILED: Directory {PROJECT_MAP_DIR} does not exist. Is this the correct project root?"
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(f"\n\n---\n### [MCP Auto-Archive]\n{content.strip()}\n")
                changed_files.append(filename)

        if not changed_files:
            return "WARNING: No files were updated. Verify nothing was missed this session."

        # Write session compaction summary (context overflow recovery point)
        if session_compaction and session_compaction.strip():
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            compaction_path = PROJECT_MAP_DIR / "activeContext.md"
            with open(compaction_path, "a", encoding="utf-8") as f:
                f.write(
                    f"\n\n---\n### [Session Compaction — {timestamp}]\n"
                    f"{session_compaction.strip()}\n"
                )
            if "activeContext.md" not in changed_files:
                changed_files.append("activeContext.md")

        # Execute git commit (with MCP flag to pass pre-commit hook)
        try:
            _set_mcp_flag()
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            commit_msg = f"chore: architect save [{', '.join(changed_files)}]"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                check=True, capture_output=True, text=True
            )
            # Clear taskSpec approval flag — forces new approval for next task
            if TASKSPEC_APPROVED_FLAG.exists():
                TASKSPEC_APPROVED_FLAG.unlink()
            if FAST_TRACK_FLAG.exists():
                FAST_TRACK_FLAG.unlink()

            return (
                f"SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Git commit: {result.stdout.strip()}\n"
                f"TaskSpec approval cleared — next code change requires new approval."
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            return (
                f"PARTIAL SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Git commit FAILED: {stderr}\n"
                f"Manual commit required."
            )
        finally:
            _clear_mcp_flag()

    @mcp.tool()
    def aio__force_architect_read() -> str:
        """
        [ENFORCEMENT TOOL] Force a full read of all 5 project map files.

        This tool MUST be called when the user issues the [读档] command.
        Returns the full content of all 5 files as a structured context report.
        Applies prompt budget: max 4KB per file, 12KB total to prevent token overflow.
        """
        report = ["# Project Map Full State Report\n"]
        total_chars = 0

        for label, filename in REQUIRED_FILES.items():
            filepath = PROJECT_MAP_DIR / filename
            report.append(f"\n## [{label}] {filename}")
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                # Apply per-file budget
                if len(content) > MAX_FILE_CHARS:
                    content = content[:MAX_FILE_CHARS] + "\n\n[truncated — exceeded 4KB per-file budget]"
                # Check total budget
                if total_chars + len(content) > MAX_TOTAL_CHARS:
                    remaining = MAX_TOTAL_CHARS - total_chars
                    if remaining > 200:
                        content = content[:remaining] + "\n\n[truncated — total 12KB prompt budget reached]"
                    else:
                        content = "[omitted — prompt budget exhausted]"
                total_chars += len(content)
                report.append(content)
            else:
                report.append(f"WARNING: File not found at {filepath}")

        report.append(f"\n---\nPrompt budget: {total_chars}/{MAX_TOTAL_CHARS} chars used")
        return "\n".join(report)

    @mcp.tool()
    def aio__force_garbage_collection(confirm: bool = False) -> str:
        """
        [ENFORCEMENT TOOL] Scan and list temporary/trash files for cleanup.

        This tool MUST be called when the user issues the [清理] command.
        Set confirm=True only after the user has reviewed the list and approved deletion.

        Args:
            confirm: If False, only lists files. If True, deletes them.
        """
        import glob
        import os

        patterns = [
            "patch_*.py", "test_*.py", "temp_*.py",
            "*.temp", "debug_*.py", "fix_*.py",
            "scripts/patch_*.py", "scripts/test_*.py",
        ]

        found_files = []
        for pattern in patterns:
            found_files.extend(glob.glob(pattern))
            found_files.extend(glob.glob(f"**/{pattern}", recursive=True))

        found_files = list(set(found_files))

        if not found_files:
            return "CLEAN: No temporary or trash files found."

        if not confirm:
            file_list = "\n".join(f"  - {f}" for f in sorted(found_files))
            return (
                f"PENDING CONFIRMATION\n"
                f"Found {len(found_files)} files to delete:\n{file_list}\n\n"
                f"Call this tool again with confirm=True to proceed with deletion."
            )

        deleted = []
        for f in found_files:
            try:
                os.remove(f)
                deleted.append(f)
            except OSError as e:
                pass

        return f"DELETED: {len(deleted)} files removed.\n" + "\n".join(f"  - {f}" for f in sorted(deleted))

    @mcp.tool()
    def aio__force_project_bootstrap_write(
        projectbrief_content: str,
        systemPatterns_content: str,
        techContext_content: str,
        activeContext_focus: str,
        progress_initial: str,
        user_confirmed: bool,
    ) -> str:
        """
        [BOOTSTRAP ENFORCEMENT TOOL] Merge AI-generated content into project_map templates.

        This tool MUST be called at Phase 4 of the project-bootstrap skill.
        It CANNOT be called unless user_confirmed=True.

        MERGE BEHAVIOR (not overwrite):
        - For the 3 static files (projectbrief, systemPatterns, techContext):
          Reads the existing template, finds [待填写...] placeholders, and replaces
          them with AI-generated content. Template structure (headers, fill instructions,
          examples) is PRESERVED. Unfilled sections keep their [待填写] placeholder.
        - For the 2 dynamic files (activeContext, progress):
          Generated fresh each time (they are session-specific).

        Use "SKIP" for any static file to leave it entirely untouched.
        This enables incremental initialization for large projects.

        Protocol reference: skills/project-bootstrap/SKILL.md (Phase 4)

        Args:
            projectbrief_content: Section fills for projectbrief.md, separated by
                "===SECTION===" delimiter (one fill per [待填写] placeholder, in order).
                Use "SKIP" to leave a section unfilled. Use "SKIP" for the entire param
                to skip this file completely.
            systemPatterns_content: Same format for systemPatterns.md.
            techContext_content: Same format for techContext.md.
            activeContext_focus: Current focus statement for activeContext.md.
            progress_initial: Initial milestone entry for progress.md.
            user_confirmed: MUST be True.

        Returns:
            Execution report with merge results and git commit status.
        """
        import re
        import datetime

        # Gate 1: Enforce user confirmation
        if not user_confirmed:
            return (
                "REJECTED: user_confirmed must be True.\n"
                "You MUST complete Phase 3 (calibration dialogue) and receive explicit user approval "
                "before calling this tool. Do NOT skip the calibration dialogue."
            )

        # Gate 2: Reject [TODO] (but allow SKIP and [待确认])
        for field_name, content in {
            "projectbrief_content": projectbrief_content,
            "systemPatterns_content": systemPatterns_content,
            "techContext_content": techContext_content,
            "activeContext_focus": activeContext_focus,
            "progress_initial": progress_initial,
        }.items():
            if "[TODO]" in content:
                return (
                    f"REJECTED: {field_name} still contains [TODO] placeholders.\n"
                    f"Use [待确认] for uncertain items, or SKIP to leave unfilled."
                )

        # Gate 3: Verify directory exists
        if not PROJECT_MAP_DIR.exists():
            return (
                f"FAILED: Directory {PROJECT_MAP_DIR} does not exist.\n"
                f"Ensure the framework scaffold has been copied into this project correctly."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        merge_report = []

        # ── Merge static files (preserve template structure) ──────────
        def merge_into_template(filepath, ai_content):
            """Replace [待填写...] placeholders in template, preserve everything else."""
            if ai_content.strip().upper() == "SKIP":
                return "SKIPPED"

            if not filepath.exists():
                # No template to merge into — write directly
                filepath.write_text(ai_content.strip(), encoding="utf-8")
                return "WRITTEN (no template found)"

            template = filepath.read_text(encoding="utf-8")

            # Find all [待填写...] placeholders in template
            placeholder_pattern = r'\[待填写[^\]]*\]'
            placeholders = list(re.finditer(placeholder_pattern, template))

            if not placeholders:
                # Template has no placeholders left — full overwrite (re-initialization)
                filepath.write_text(ai_content.strip(), encoding="utf-8")
                return "OVERWRITTEN (no placeholders in template)"

            # Split AI content by section delimiter
            sections = re.split(r'===SECTION===', ai_content)

            # Replace placeholders one-by-one, in order
            result = template
            filled_count = 0
            skipped_count = 0

            for i, match in enumerate(placeholders):
                if i < len(sections):
                    section_content = sections[i].strip()
                    if section_content.upper() == "SKIP" or not section_content:
                        skipped_count += 1
                        continue
                    # Replace this specific placeholder with AI content
                    result = result.replace(match.group(), section_content, 1)
                    filled_count += 1
                else:
                    skipped_count += 1

            # Update timestamp
            result = re.sub(
                r'\[由 `\[初始化项目\]` 写入日期\]',
                timestamp,
                result
            )
            result = re.sub(
                r'\[由 `\[存档\]` 写入日期和变更摘要\]',
                f"{timestamp} — bootstrap merge",
                result
            )

            filepath.write_text(result, encoding="utf-8")
            return f"MERGED ({filled_count} filled, {skipped_count} kept as template)"

        static_files = {
            "projectbrief.md": projectbrief_content,
            "systemPatterns.md": systemPatterns_content,
            "techContext.md": techContext_content,
        }

        written_files = []
        for filename, content in static_files.items():
            filepath = PROJECT_MAP_DIR / filename
            try:
                status = merge_into_template(filepath, content)
                merge_report.append(f"  {filename}: {status}")
                if status != "SKIPPED":
                    written_files.append(filename)
            except Exception as e:
                return f"FAILED: Could not process {filename}: {e}"

        # ── Generate dynamic files (always fresh) ─────────────────────
        if activeContext_focus.strip().upper() != "SKIP":
            active_path = PROJECT_MAP_DIR / "activeContext.md"
            active_path.write_text(
                f"# 当前工作焦点 (Active Context)\n\n"
                f"> 由 project-bootstrap 技能初始化于 {timestamp}\n\n"
                f"## 1. 当前焦点 (Current Focus)\n\n{activeContext_focus.strip()}\n\n"
                f"## 2. 正在处理的问题 (Active Issues)\n\n- 无\n\n"
                f"## 3. 即将执行的下一步 (Immediate Next Steps)\n\n"
                f"1. 检查所有 [待确认] 标注的字段，逐一确认或修正\n"
                f"2. 与用户确认第一个 taskSpec.md 的范围\n\n"
                f"> 上次更新时间：{timestamp}",
                encoding="utf-8"
            )
            written_files.append("activeContext.md")
            merge_report.append("  activeContext.md: GENERATED")
        else:
            merge_report.append("  activeContext.md: SKIPPED")

        if progress_initial.strip().upper() != "SKIP":
            progress_path = PROJECT_MAP_DIR / "progress.md"
            progress_path.write_text(
                f"# 进度与里程碑 (Progress)\n\n"
                f"> 由 project-bootstrap 技能初始化于 {timestamp}\n\n"
                f"## 已完成里程碑\n\n"
                f"- [{timestamp}] 项目接管完成，project_map 初始化\n\n"
                f"## 当前待办\n\n{progress_initial.strip()}\n\n"
                f"## 已知风险\n\n- 无",
                encoding="utf-8"
            )
            written_files.append("progress.md")
            merge_report.append("  progress.md: GENERATED")
        else:
            merge_report.append("  progress.md: SKIPPED")

        if not written_files:
            return "WARNING: All files were SKIPPED. No changes made."

        # ── Count remaining placeholders ──────────────────────────────
        remaining = 0
        for filename in ["projectbrief.md", "systemPatterns.md", "techContext.md"]:
            filepath = PROJECT_MAP_DIR / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                remaining += len(re.findall(r'\[待填写[^\]]*\]', content))

        # ── Git commit ────────────────────────────────────────────────
        try:
            _set_mcp_flag()
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"chore: bootstrap project map [{timestamp}]"],
                check=True, capture_output=True, text=True
            )
            return (
                f"SUCCESS: Project bootstrap merge complete.\n\n"
                f"Merge report:\n" + "\n".join(merge_report) + "\n\n"
                f"Remaining [待填写] placeholders: {remaining}\n"
                f"{'Re-run [初始化项目] to fill remaining sections.' if remaining > 0 else 'All sections filled!'}\n\n"
                f"Git commit: {result.stdout.strip()}\n\n"
                f"Next step: Run [读档] to verify the initialized state."
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            return (
                f"PARTIAL SUCCESS: Files merged but git commit failed.\n\n"
                f"Merge report:\n" + "\n".join(merge_report) + "\n\n"
                f"Remaining [待填写] placeholders: {remaining}\n"
                f"Git error: {stderr}\n"
                f"Manual commit required."
            )
        finally:
            _clear_mcp_flag()

    @mcp.tool()
    def aio__force_architect_report(
        files_modified: str,
        why: str,
        architecture_impact: str,
        next_steps: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Generate a structured Architect report.

        This tool MUST be called when the user issues the [汇报] command.
        The AI MUST NOT provide a free-form report — it must fill all 4 sections.

        Args:
            files_modified: List of files modified in this session (one per line).
            why: Explanation of why these changes were made.
            architecture_impact: How these changes affect the system architecture.
            next_steps: Exact next steps to take.

        Returns:
            Formatted architect report.
        """
        # Validate: no empty fields
        for field_name, value in {
            "files_modified": files_modified,
            "why": why,
            "architecture_impact": architecture_impact,
            "next_steps": next_steps,
        }.items():
            if not value or not value.strip():
                return f"REJECTED: {field_name} cannot be empty. All 4 report sections are mandatory."

        # Read current project state for context
        state_summary = ""
        active_ctx = PROJECT_MAP_DIR / "activeContext.md"
        if active_ctx.exists():
            state_summary = active_ctx.read_text(encoding="utf-8")[:500]

        report = (
            f"# Architect Report\n\n"
            f"## 1. Files Modified\n{files_modified.strip()}\n\n"
            f"## 2. Why\n{why.strip()}\n\n"
            f"## 3. Architecture Impact\n{architecture_impact.strip()}\n\n"
            f"## 4. Next Steps\n{next_steps.strip()}\n\n"
            f"---\n"
            f"### Current Context (from activeContext.md)\n{state_summary}\n"
        )

        return f"SUCCESS\n\n{report}"

    @mcp.tool()
    def aio__force_test_runner(
        test_target: str,
        test_command: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Run isolated module tests with mandatory pre-cleanup.

        This tool MUST be called when the user issues the [执行测试] command.
        It enforces:
        1. Automatic cleanup of dirty data and temp files BEFORE testing
        2. Tests run in isolation (single module/node, not full pipeline)
        3. Results are captured and returned as structured output

        Args:
            test_target: Which module or node to test (e.g., "IngestNode", "tests/test_ingest.py").
            test_command: The exact command to run (e.g., "python -m pytest tests/test_ingest.py -v").

        Returns:
            Test execution report with pre-cleanup results and test output.
        """
        import glob
        import os

        if not test_target or not test_target.strip():
            return "REJECTED: test_target cannot be empty. Specify which module to test."
        if not test_command or not test_command.strip():
            return "REJECTED: test_command cannot be empty. Specify the exact test command."

        # Gate: Reject full pipeline commands
        pipeline_keywords = ["--all", "full_pipeline", "run_all", "test_everything"]
        for kw in pipeline_keywords:
            if kw in test_command.lower():
                return (
                    f"REJECTED: Full pipeline testing is forbidden. "
                    f"Detected '{kw}' in test_command. Run tests node-by-node."
                )

        report_parts = ["# Test Execution Report\n"]
        report_parts.append(f"## Target: {test_target.strip()}\n")

        # Step 1: Pre-cleanup
        cleanup_patterns = [
            "*.temp", "temp_*.py", "debug_*.py",
            "tests/output/*.tmp", "tests/output/*.temp",
        ]
        cleaned = []
        for pattern in cleanup_patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                    cleaned.append(f)
                except OSError:
                    pass
            for f in glob.glob(f"**/{pattern}", recursive=True):
                try:
                    os.remove(f)
                    cleaned.append(f)
                except OSError:
                    pass

        if cleaned:
            report_parts.append(f"## Pre-Cleanup\nRemoved {len(cleaned)} temp files:\n")
            for f in sorted(set(cleaned)):
                report_parts.append(f"  - {f}\n")
        else:
            report_parts.append("## Pre-Cleanup\nNo temp files found. Environment clean.\n")

        # Step 2: Run the test
        report_parts.append(f"\n## Test Command\n```\n{test_command.strip()}\n```\n")

        try:
            result = subprocess.run(
                test_command.strip().split(),
                capture_output=True,
                text=True,
                timeout=300,
            )
            report_parts.append(f"\n## Exit Code: {result.returncode}\n")

            if result.stdout:
                stdout_trimmed = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
                report_parts.append(f"\n## STDOUT\n```\n{stdout_trimmed}\n```\n")
            if result.stderr:
                stderr_trimmed = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                report_parts.append(f"\n## STDERR\n```\n{stderr_trimmed}\n```\n")

            status = "PASSED" if result.returncode == 0 else "FAILED"
            return f"{status}\n\n" + "".join(report_parts)

        except subprocess.TimeoutExpired:
            return "FAILED: Test timed out after 300 seconds.\n\n" + "".join(report_parts)
        except FileNotFoundError:
            return (
                f"FAILED: Command not found. Verify the test command is correct.\n"
                f"Command: {test_command.strip()}\n\n" + "".join(report_parts)
            )

    # ═══════════════════════════════════════════════════════════════
    # TaskSpec Workflow Enforcement (升级第 1 层软约束为硬约束)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    def aio__force_taskspec_submit(
        task_goal: str,
        scope_and_impact: str,
        files_to_modify: str,
        technical_constraints: str,
        acceptance_criteria: str,
        doc_impact: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Submit a taskSpec draft for user approval.

        This tool MUST be called in Phase 1 (LEAD/Architect) before any code changes.
        The AI MUST NOT write, edit, or execute any code before calling this tool.

        After calling this tool, the AI must wait for user approval. Only after
        the user approves should the AI call aio__force_taskspec_approve.

        Args:
            task_goal: One sentence describing the core purpose of this task.
            scope_and_impact: Which modules/nodes are affected.
            files_to_modify: Exact list of files to change and what to change.
            technical_constraints: Limitations (dependencies, performance, isolation).
            acceptance_criteria: Specific test steps to verify completion.
            doc_impact: Which project_map docs need updating. "NONE" if no impact.

        Returns:
            The formatted taskSpec for user review.
        """
        import datetime

        # Validate: all fields must be non-empty
        fields = {
            "task_goal": task_goal,
            "scope_and_impact": scope_and_impact,
            "files_to_modify": files_to_modify,
            "technical_constraints": technical_constraints,
            "acceptance_criteria": acceptance_criteria,
            "doc_impact": doc_impact,
        }
        for name, value in fields.items():
            if not value or not value.strip():
                return f"REJECTED: {name} cannot be empty. All 6 taskSpec sections are mandatory."

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Build the taskSpec document
        spec_content = (
            f"# Task Specification\n\n"
            f"> Generated: {timestamp}\n"
            f"> Status: **PENDING APPROVAL**\n\n"
            f"## 1. Task Goal\n{task_goal.strip()}\n\n"
            f"## 2. Scope & Impact\n{scope_and_impact.strip()}\n\n"
            f"## 3. Files to Modify\n{files_to_modify.strip()}\n\n"
            f"## 4. Technical Constraints\n{technical_constraints.strip()}\n\n"
            f"## 5. Acceptance Criteria\n{acceptance_criteria.strip()}\n\n"
            f"## 6. Architecture Doc Impact\n{doc_impact.strip()}\n"
        )

        # Write the taskSpec file
        TASKSPEC_DIR.mkdir(parents=True, exist_ok=True)
        TASKSPEC_FILE.write_text(spec_content, encoding="utf-8")

        # Clear any previous approval flag
        if TASKSPEC_APPROVED_FLAG.exists():
            TASKSPEC_APPROVED_FLAG.unlink()

        return (
            f"SUCCESS: TaskSpec submitted for approval.\n\n"
            f"{spec_content}\n"
            f"---\n"
            f"⏸ Waiting for user approval. Do NOT write any code until approved.\n"
            f"After user says '批准/approved/ok go', call aio__force_taskspec_approve."
        )

    @mcp.tool()
    def aio__force_taskspec_approve(
        user_said: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Record user approval of the current taskSpec.

        This tool MUST be called after the user explicitly approves the taskSpec.
        It creates the approval flag that the git pre-commit hook checks before
        allowing code commits.

        Without this flag, git commits that modify project code files will be BLOCKED
        by the pre-commit hook.

        Args:
            user_said: The exact approval message from the user (e.g., "批准", "approved").

        Returns:
            Approval confirmation with execution permission granted.
        """
        # Gate 1: taskSpec file must exist
        if not TASKSPEC_FILE.exists():
            return (
                "REJECTED: No taskSpec found.\n"
                "You must call aio__force_taskspec_submit first to create a taskSpec."
            )

        # Gate 2: user_said must contain an approval signal
        approval_signals = ["批准", "approved", "ok go", "执行", "ok", "go", "yes", "可以", "同意"]
        if not any(signal in user_said.lower() for signal in approval_signals):
            return (
                f"REJECTED: '{user_said}' does not look like an approval.\n"
                f"Expected one of: {', '.join(approval_signals)}"
            )

        # Gate 3: Check this isn't a stale approval (taskSpec must be PENDING)
        spec_content = TASKSPEC_FILE.read_text(encoding="utf-8")
        if "PENDING APPROVAL" not in spec_content:
            return (
                "REJECTED: taskSpec is not in PENDING state.\n"
                "Submit a new taskSpec with aio__force_taskspec_submit first."
            )

        # Mark as approved
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Update taskSpec status
        updated_spec = spec_content.replace(
            "**PENDING APPROVAL**",
            f"**APPROVED** ({timestamp}, user: {user_said.strip()[:50]})"
        )
        TASKSPEC_FILE.write_text(updated_spec, encoding="utf-8")

        # Create approval flag for pre-commit hook
        TASKSPEC_APPROVED_FLAG.write_text(
            f"approved|{timestamp}|{user_said.strip()[:50]}",
            encoding="utf-8"
        )

        return (
            f"SUCCESS: TaskSpec APPROVED.\n"
            f"Approval recorded at {timestamp}.\n"
            f"You may now proceed to Phase 2 (WORKER) — write code per the approved spec.\n"
            f"The approval flag has been created. Git commits will be allowed.\n\n"
            f"Reminder: Execute ONLY what the taskSpec specifies. No extra changes."
        )

    @mcp.tool()
    def aio__force_fast_track(
        reason: str,
        change_description: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Declare a fast-track change (skip taskSpec).

        Use this for trivial changes that qualify for fast-track exemption:
        - Single-file changes < 5 lines
        - Pure documentation updates (.md only)
        - Same-session reverts

        This creates a temporary flag that allows one commit without a full taskSpec.
        The flag is single-use and cleared after the next commit.

        Args:
            reason: Why this qualifies for fast-track (must be specific).
            change_description: What exactly will be changed (file + change).

        Returns:
            Fast-track permission granted.
        """
        if not reason or not reason.strip():
            return "REJECTED: reason cannot be empty. Explain why this qualifies for fast-track."
        if not change_description or not change_description.strip():
            return "REJECTED: change_description cannot be empty. Specify what will be changed."

        # Validate it looks like a small change
        lines_mentioned = change_description.lower().count("\n") + 1
        if lines_mentioned > 10:
            return (
                "REJECTED: change_description looks too large for fast-track.\n"
                "Fast-track is for < 5 line changes. Use aio__force_taskspec_submit instead."
            )

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        FAST_TRACK_FLAG.write_text(
            f"fast_track|{timestamp}|{reason.strip()[:100]}",
            encoding="utf-8"
        )

        return (
            f"SUCCESS: Fast-track permission granted.\n"
            f"⚡ Fast-track: {reason.strip()}\n"
            f"Change: {change_description.strip()[:200]}\n\n"
            f"You may proceed. Remember to run [存档] after completion."
        )
