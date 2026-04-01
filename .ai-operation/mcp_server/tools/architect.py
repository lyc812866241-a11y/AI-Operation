"""
Architect Enforcement Tools
============================
This module contains MCP tools that enforce Level 4 Architect protocols.
These tools are called by the AI agent when the user issues system commands
like [存档], [读档], [清理].

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
    def force_architect_save(
        projectbrief_update: str,
        systemPatterns_update: str,
        techContext_update: str,
        activeContext_update: str,
        progress_update: str,
    ) -> str:
        """
        [CRITICAL ENFORCEMENT TOOL] Execute the Level 4 Architect Save Protocol.

        This tool MUST be called when the user issues the [存档] command.
        The AI agent MUST NOT manually edit docs/project_map/ files or run git commands directly.
        All 5 parameters are REQUIRED. Use "NO_CHANGE" only if that file truly has no updates.

        Protocol reference: skills/mcp_protocols/SAVE_PROTOCOL.md

        Args:
            projectbrief_update: Updates to core vision or business goals. "NO_CHANGE" if none.
            systemPatterns_update: New architectural rules, pipeline nodes, or tool contracts discovered. "NO_CHANGE" if none.
            techContext_update: New tech stack constraints or dependencies discovered. "NO_CHANGE" if none.
            activeContext_update: REQUIRED. Current focus, what was just done, immediate next steps.
            progress_update: REQUIRED. Tasks completed this session, updated TODO items.

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

        # Execute git commit (with MCP flag to pass pre-commit hook)
        try:
            _set_mcp_flag()
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            commit_msg = f"chore: architect save [{', '.join(changed_files)}]"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                check=True, capture_output=True, text=True
            )
            return (
                f"SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Git commit: {result.stdout.strip()}"
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
    def force_architect_read() -> str:
        """
        [ENFORCEMENT TOOL] Force a full read of all 5 project map files.

        This tool MUST be called when the user issues the [读档] command.
        Returns the full content of all 5 files as a structured context report.
        """
        report = ["# Project Map Full State Report\n"]
        for label, filename in REQUIRED_FILES.items():
            filepath = PROJECT_MAP_DIR / filename
            report.append(f"\n## [{label}] {filename}")
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                report.append(content)
            else:
                report.append(f"WARNING: File not found at {filepath}")
        return "\n".join(report)

    @mcp.tool()
    def force_garbage_collection(confirm: bool = False) -> str:
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
    def force_project_bootstrap_write(
        projectbrief_content: str,
        systemPatterns_content: str,
        techContext_content: str,
        activeContext_focus: str,
        progress_initial: str,
        user_confirmed: bool,
    ) -> str:
        """
        [BOOTSTRAP ENFORCEMENT TOOL] Write all 5 project_map files after user calibration.

        This tool MUST be called at Phase 4 of the project-bootstrap skill.
        It CANNOT be called unless user_confirmed=True, which requires the AI to have
        completed the Phase 3 calibration dialogue and received explicit user approval.

        This is the enforcement gate that prevents the AI from skipping the calibration
        dialogue and writing project_map files directly.

        Protocol reference: skills/project-bootstrap/SKILL.md (Phase 4)

        Args:
            projectbrief_content: Full content for projectbrief.md (no [TODO] placeholders allowed).
            systemPatterns_content: Full content for systemPatterns.md (no [TODO] placeholders allowed).
            techContext_content: Full content for techContext.md (no [TODO] placeholders allowed).
            activeContext_focus: Current focus statement for activeContext.md (from user's Phase 3.4 answer).
            progress_initial: Initial milestone entry for progress.md.
            user_confirmed: MUST be True. Set to True only after user has reviewed and approved
                            the Phase 3 calibration draft. If False, this tool will reject the call.

        Returns:
            Execution report with files written and git commit status.
        """
        # Gate 1: Enforce user confirmation
        if not user_confirmed:
            return (
                "REJECTED: user_confirmed must be True.\n"
                "You MUST complete Phase 3 (calibration dialogue) and receive explicit user approval "
                "before calling this tool. Do NOT skip the calibration dialogue."
            )

        # Gate 2: Reject any content that still contains [TODO] placeholders
        fields = {
            "projectbrief_content": projectbrief_content,
            "systemPatterns_content": systemPatterns_content,
            "techContext_content": techContext_content,
            "activeContext_focus": activeContext_focus,
            "progress_initial": progress_initial,
        }
        for field_name, content in fields.items():
            if "[TODO]" in content:
                return (
                    f"REJECTED: {field_name} still contains [TODO] placeholders.\n"
                    f"All placeholders must be replaced with real content before writing. "
                    f"Use [待确认] for uncertain items, never [TODO]."
                )

        # Gate 3: Verify project_map directory exists
        if not PROJECT_MAP_DIR.exists():
            return (
                f"FAILED: Directory {PROJECT_MAP_DIR} does not exist.\n"
                f"Ensure the framework scaffold has been copied into this project correctly."
            )

        # Build file contents with source tracing header
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        file_map = {
            "projectbrief.md": projectbrief_content.strip(),
            "systemPatterns.md": systemPatterns_content.strip(),
            "techContext.md": techContext_content.strip(),
            "activeContext.md": (
                f"# 当前工作焦点 (Active Context)\n\n"
                f"> 由 project-bootstrap 技能初始化于 {timestamp}\n\n"
                f"## 1. 当前焦点 (Current Focus)\n\n{activeContext_focus.strip()}\n\n"
                f"## 2. 正在处理的问题 (Active Issues)\n\n- 无\n\n"
                f"## 3. 即将执行的下一步 (Immediate Next Steps)\n\n"
                f"1. 检查所有 [待确认] 标注的字段，逐一确认或修正\n"
                f"2. 与用户确认第一个 taskSpec.md 的范围\n\n"
                f"> 上次更新时间：{timestamp}"
            ),
            "progress.md": (
                f"# 进度与里程碑 (Progress)\n\n"
                f"> 由 project-bootstrap 技能初始化于 {timestamp}\n\n"
                f"## 已完成里程碑\n\n"
                f"- [{timestamp}] 项目接管完成，project_map 初始化\n\n"
                f"## 当前待办\n\n{progress_initial.strip()}\n\n"
                f"## 已知风险\n\n- 无"
            ),
        }

        # Write all 5 files (full overwrite, replacing templates)
        written_files = []
        for filename, content in file_map.items():
            filepath = PROJECT_MAP_DIR / filename
            try:
                filepath.write_text(content, encoding="utf-8")
                written_files.append(filename)
            except Exception as e:
                return f"FAILED: Could not write {filename}: {e}"

        # Git commit (with MCP flag to pass pre-commit hook)
        try:
            _set_mcp_flag()
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"chore: bootstrap project map [{timestamp}]"],
                check=True, capture_output=True, text=True
            )
            return (
                f"SUCCESS: Project bootstrap complete.\n"
                f"Files written: {', '.join(written_files)}\n"
                f"Git commit: {result.stdout.strip()}\n\n"
                f"Next step: Run [读档] to verify the initialized state."
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            return (
                f"PARTIAL SUCCESS: Files written but git commit failed.\n"
                f"Files written: {', '.join(written_files)}\n"
                f"Git error: {stderr}\n"
                f"Manual commit required: git add .ai-operation/docs/project_map/ && git commit -m 'chore: bootstrap project map'"
            )
        finally:
            _clear_mcp_flag()

    @mcp.tool()
    def force_architect_report(
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
    def force_test_runner(
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
