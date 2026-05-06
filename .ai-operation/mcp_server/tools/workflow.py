"""
Workflow tools -- taskSpec submit/approve, fast-track, architect report, test runner.
Contains: aio__force_taskspec_submit, aio__force_taskspec_approve,
          aio__force_fast_track, aio__force_architect_report, aio__force_test_runner
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *
from .bypass import has_bypass, clear_bypass, clear_all_bypasses, is_monitor_rule


def register_workflow_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register workflow-related tools onto the MCP server instance."""

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
        The AI MUST NOT provide a free-form report -- it must fill all 4 sections.

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

    # ===============================================================
    # TaskSpec Workflow Enforcement (升级第 1 层软约束为硬约束)
    # ===============================================================

    @mcp.tool()
    def aio__force_taskspec_submit(
        task_goal: str,
        scope_and_impact: str,
        files_to_modify: str,
        technical_constraints: str,
        acceptance_criteria: str,
        doc_impact: str,
        dry_run: str = "",
    ) -> str:
        """
        [ENFORCEMENT TOOL] Submit a taskSpec draft for user approval.

        This tool MUST be called in Phase 1 (LEAD/Architect) before any code changes.
        The AI MUST NOT write, edit, or execute any code before calling this tool.

        After calling this tool, the AI must wait for user approval. Only after
        the user approves should the AI call aio__force_taskspec_approve.

        Supports dry_run mode: pass dry_run="true" to validate all fields without
        writing any files. Returns a checklist of which rules pass/fail/are bypassable.
        Use this to check all issues at once before the real submit.

        Args:
            task_goal: One sentence describing the core purpose of this task.
            scope_and_impact: Which modules/nodes are affected.
            files_to_modify: Exact list of files to change and what to change.
            technical_constraints: Limitations (dependencies, performance, isolation).
            acceptance_criteria: Specific test steps to verify completion.
            doc_impact: Which project_map docs need updating. "NONE" if no impact.
            dry_run: Set to "true" to validate without writing. Returns all violations at once.

        Returns:
            The formatted taskSpec for user review, or dry-run validation report.
        """
        import datetime
        import re

        is_dry_run = dry_run.strip().lower() == "true" if dry_run else False

        _audit("aio__force_taskspec_submit", "CALLED", f"{'DRY_RUN ' if is_dry_run else ''}{task_goal[:100] if task_goal else ''}")

        loop_msg = _loop_guard("aio__force_taskspec_submit", task_goal[:100] if task_goal else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # -- Dry-run mode: collect all violations at once --------
        if is_dry_run:
            checks = []

            # Check 1: all fields non-empty
            for name, value in {
                "task_goal": task_goal, "scope_and_impact": scope_and_impact,
                "files_to_modify": files_to_modify, "technical_constraints": technical_constraints,
                "acceptance_criteria": acceptance_criteria, "doc_impact": doc_impact,
            }.items():
                if not value or not value.strip():
                    checks.append(f"  [X] {name}: REJECTED -- cannot be empty")
                else:
                    checks.append(f"  [OK] {name}: OK ({len(value.strip())} chars)")

            # Check 2: vague descriptions
            vague_found = False
            for pattern in ["根据你的发现", "based on your findings", "按需修改", "相关文件",
                            "等文件", "相关模块", "relevant files", "as needed"]:
                if pattern in files_to_modify.lower():
                    bypassed = has_bypass("taskspec.files_to_modify_vague")
                    status = "BYPASSED" if bypassed else "BYPASSABLE"
                    checks.append(f"  [!] files_to_modify: {status} -- contains '{pattern}'")
                    vague_found = True
                    break
            if not vague_found:
                checks.append(f"  [OK] files_to_modify vagueness: OK")

            # Check 3: file path presence
            has_path = re.search(r'[\w/\\]+\.\w{1,5}', files_to_modify) if files_to_modify else None
            if not has_path:
                bypassed = has_bypass("taskspec.files_to_modify_no_path")
                status = "BYPASSED" if bypassed else "BYPASSABLE"
                checks.append(f"  [!] files_to_modify paths: {status} -- no file paths found")
            else:
                checks.append(f"  [OK] files_to_modify paths: OK")

            report = "\n".join(checks)
            failures = sum(1 for c in checks if "[X]" in c)
            bypassable = sum(1 for c in checks if "[!]" in c and "BYPASSABLE" in c)
            bypassed_count = sum(1 for c in checks if "BYPASSED" in c)

            _audit("aio__force_taskspec_submit", "DRY_RUN",
                   f"failures={failures}, bypassable={bypassable}, bypassed={bypassed_count}")

            summary = f"DRY_RUN RESULT: {failures} hard failures, {bypassable} bypassable, {bypassed_count} already bypassed\n\n"
            if failures > 0:
                summary += "Fix all [X] items before real submit.\n"
            if bypassable > 0:
                summary += "[!] items can be fixed or bypassed via aio__bypass_violation.\n"
            if failures == 0 and bypassable == 0:
                summary += "[OK] All checks pass. Ready for real submit (remove dry_run).\n"

            return f"{summary}\n{report}"

        # -- Normal mode (not dry-run) ---------------------------

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

        # -- Sub-task self-containment check ----------------------
        # files_to_modify must contain actual file paths, not vague descriptions.
        # This enforces "synthesize, don't delegate" -- every sub-task must be specific.
        # These rules are BYPASSABLE -- user can authorize bypass with reason.
        RULE_VAGUE_FILES = "taskspec.files_to_modify_vague"
        RULE_NO_FILE_PATH = "taskspec.files_to_modify_no_path"

        vague_patterns = [
            "根据你的发现", "based on your findings", "按需修改", "相关文件",
            "等文件", "相关模块", "relevant files", "as needed",
        ]
        ftm_lower = files_to_modify.lower()
        for pattern in vague_patterns:
            if pattern in ftm_lower:
                if is_monitor_rule(RULE_VAGUE_FILES):
                    # Monitor mode: log but don't block
                    _audit("aio__force_taskspec_submit", "MONITOR", f"rule={RULE_VAGUE_FILES}, pattern={pattern}")
                    break
                elif has_bypass(RULE_VAGUE_FILES):
                    _audit("aio__force_taskspec_submit", "BYPASSED", f"rule={RULE_VAGUE_FILES}")
                    clear_bypass(RULE_VAGUE_FILES)
                    break
                else:
                    _audit("aio__force_taskspec_submit", "BYPASSABLE", f"vague files_to_modify: {pattern}")
                    return (
                        f"BYPASSABLE: files_to_modify contains vague description '{pattern}'.\n"
                        f"Rule: {RULE_VAGUE_FILES}\n\n"
                        f"Each file must be listed with its path and what specifically to change.\n"
                        f"Example:\n"
                        f"  - src/auth.py:42 -- add null check before token.decode()\n"
                        f"  - tests/test_auth.py -- add test for null token case\n\n"
                        f"Option 1: Fix the description and resubmit.\n"
                        f"Option 2: Ask user to authorize bypass -> call aio__bypass_violation(\n"
                        f"  rule_code=\"{RULE_VAGUE_FILES}\", user_said=\"<user's exact words>\")"
                    )

        # Must contain at least one file-like path (has / or \ or .py/.ts/.md etc)
        has_file_path_match = re.search(r'[\w/\\]+\.\w{1,5}', files_to_modify)
        if not has_file_path_match:
            if is_monitor_rule(RULE_NO_FILE_PATH):
                _audit("aio__force_taskspec_submit", "MONITOR", f"rule={RULE_NO_FILE_PATH}")
            elif has_bypass(RULE_NO_FILE_PATH):
                _audit("aio__force_taskspec_submit", "BYPASSED", f"rule={RULE_NO_FILE_PATH}")
                clear_bypass(RULE_NO_FILE_PATH)
            else:
                _audit("aio__force_taskspec_submit", "BYPASSABLE", "no file paths in files_to_modify")
                return (
                    f"BYPASSABLE: files_to_modify must contain at least one specific file path.\n"
                    f"Rule: {RULE_NO_FILE_PATH}\n\n"
                    f"Example: src/engine/pipeline.py, tests/test_pipeline.py\n"
                    f"Don't describe files generically -- name them.\n\n"
                    f"Option 1: Add file paths and resubmit.\n"
                    f"Option 2: Ask user to authorize bypass -> call aio__bypass_violation(\n"
                    f"  rule_code=\"{RULE_NO_FILE_PATH}\", user_said=\"<user's exact words>\")"
                )

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
            f"[PAUSE] Waiting for user approval. Do NOT write any code until approved.\n"
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
        _audit("aio__force_taskspec_approve", "CALLED", user_said[:50] if user_said else "")

        loop_msg = _loop_guard("aio__force_taskspec_approve", user_said[:50] if user_said else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg
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

        # Clear any consumed bypass flags (single-use, reset after approval)
        clear_all_bypasses()

        # -- Auto experience matching ----------------------------
        # Read the approved taskSpec, extract file paths/keywords,
        # match against corrections keys, and auto-load relevant experience.
        matched_experience = []
        corrections_dir = PROJECT_MAP_DIR.parent / "corrections"
        if corrections_dir.exists():
            available_keys = [f.stem for f in corrections_dir.glob("*.md")]
            spec_lower = spec_content.lower()

            # Keyword -> key mapping
            key_triggers = {
                "fileops": [".py", ".ts", ".js", "write", "edit", "file", "path",
                            "encoding", "utf-8", "bytes", "size"],
                "git": ["git", "commit", "branch", "merge", "push", "pull",
                        "checkout", "rebase", "stash"],
                "save": ["save", "存档", "project_map", "activecontext",
                         "progress", "corrections"],
                "analysis": ["analyze", "分析", "scan", "parse", "debug",
                             "investigate", "root cause"],
            }

            for key in available_keys:
                triggers = key_triggers.get(key, [key])  # fallback: key name itself
                if any(trigger in spec_lower for trigger in triggers):
                    key_file = corrections_dir / f"{key}.md"
                    if key_file.exists():
                        content = key_file.read_text(encoding="utf-8")
                        # Take first 500 chars as summary
                        summary = content[:500].strip()
                        if len(content) > 500:
                            summary += "..."
                        matched_experience.append(f"### [{key}]\n{summary}")

        experience_section = ""
        if matched_experience:
            experience_section = (
                f"\n\n## [!] Auto-loaded Experience ({len(matched_experience)} keys matched)\n"
                f"Read these BEFORE writing code:\n\n"
                + "\n\n".join(matched_experience)
                + "\n"
            )
            _audit("aio__force_taskspec_approve", "EXPERIENCE_MATCHED",
                   f"keys={len(matched_experience)}")

        return (
            f"SUCCESS: TaskSpec APPROVED.\n"
            f"Approval recorded at {timestamp}.\n"
            f"You may now proceed to Phase 2 (WORKER) -- write code per the approved spec.\n"
            f"The approval flag has been created. Git commits will be allowed.\n\n"
            f"Reminder: Execute ONLY what the taskSpec specifies. No extra changes."
            f"{experience_section}"
        )

    @mcp.tool()
    def aio__force_fast_track(
        reason: str,
        change_description: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Declare a fast-track change (skip taskSpec).

        Use this for trivial changes that qualify for fast-track exemption.
        The threshold is DYNAMIC based on trust score:
        - Low trust (recent corrections): < 3 lines, single file only
        - Normal trust: < 5 lines, single file
        - High trust (5+ clean saves): < 10 lines, single file

        This creates a temporary flag that allows one commit without a full taskSpec.
        The flag is single-use and cleared after the next commit.

        Args:
            reason: Why this qualifies for fast-track (must be specific).
            change_description: What exactly will be changed (file + change).

        Returns:
            Fast-track permission granted, with trust level shown.
        """
        import datetime
        import re

        _audit("aio__force_fast_track", "CALLED", reason[:80] if reason else "")

        loop_msg = _loop_guard("aio__force_fast_track", reason[:80] if reason else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        if not reason or not reason.strip():
            return "REJECTED: reason cannot be empty. Explain why this qualifies for fast-track."
        if not change_description or not change_description.strip():
            return "REJECTED: change_description cannot be empty. Specify what will be changed."

        # -- Trust Score Calculation ----------------------------------
        # Read corrections.md to assess recent error frequency
        corrections_path = PROJECT_MAP_DIR / "corrections.md"
        recent_corrections = 0
        consecutive_clean_saves = 0

        if corrections_path.exists():
            content = corrections_path.read_text(encoding="utf-8")
            # Count corrections from last 30 days
            dates = re.findall(r"DATE: (\d{4}-\d{2}-\d{2})", content)
            now = datetime.datetime.now()
            for d in dates:
                try:
                    dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                    if (now - dt).days <= 30:
                        recent_corrections += 1
                except ValueError:
                    pass

        # Check recent saves -- count NONE lessons as "clean saves"
        if corrections_path.exists():
            content = corrections_path.read_text(encoding="utf-8")
            entries = content.split("---")
            # Count consecutive entries from the end that are clean
            for entry in reversed(entries):
                if "LESSON:" in entry and "NONE" not in entry.upper():
                    break
                if "LESSON:" in entry:
                    consecutive_clean_saves += 1

        # Determine trust level and threshold
        if recent_corrections >= 3:
            trust_level = "LOW"
            max_lines = 3
            trust_reason = f"{recent_corrections} corrections in last 30 days"
        elif consecutive_clean_saves >= 5:
            trust_level = "HIGH"
            max_lines = 10
            trust_reason = f"{consecutive_clean_saves} consecutive clean saves"
        else:
            trust_level = "NORMAL"
            max_lines = 5
            trust_reason = "default threshold"

        # Validate change size against trust-adjusted threshold
        lines_mentioned = change_description.count("\n") + 1
        if lines_mentioned > max_lines:
            _audit("aio__force_fast_track", "REJECTED", f"trust={trust_level}, lines={lines_mentioned}>{max_lines}")
            return (
                f"REJECTED: Change too large for fast-track at current trust level.\n"
                f"Trust: {trust_level} ({trust_reason})\n"
                f"Max lines: {max_lines}, your change: {lines_mentioned} lines\n"
                f"Use aio__force_taskspec_submit instead."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        FAST_TRACK_FLAG.write_text(
            f"fast_track|{timestamp}|{reason.strip()[:100]}",
            encoding="utf-8"
        )

        _audit("aio__force_fast_track", "SUCCESS", f"trust={trust_level}")
        return (
            f"SUCCESS: Fast-track permission granted.\n"
            f"Trust level: {trust_level} ({trust_reason})\n"
            f"Threshold: < {max_lines} lines\n"
            f"[!] Fast-track: {reason.strip()}\n"
            f"Change: {change_description.strip()[:200]}\n\n"
            f"You may proceed. Remember to run [存档] after completion."
        )
