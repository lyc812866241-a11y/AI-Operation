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
    # 议题 #014 v3:补 propose 阶段(用户审单方案 → 平行候选选择)
    # ===============================================================

    @mcp.tool()
    def aio__force_taskspec_propose(
        user_intent: str,
        proposals: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] List ≥2 candidate proposals before taskspec_submit.

        This tool MUST be called FIRST when the user issues [提需] or 功能开发.
        Purpose: protect user's taste judgment by forcing parallel candidates
        with explicit trade-offs, instead of the AI compressing into a single
        spec that the user can only accept/reject in series.

        After calling this tool, the AI must wait for the user to choose one
        proposal, then call aio__force_taskspec_submit with chosen_proposal_id.

        Args:
            user_intent: The user's original natural-language request.
            proposals: JSON list of >=2 candidates. Each item must have:
                {"id": "A"|"B"|..., "label": str, "approach": str, "tradeoffs": str}
                All four fields non-empty. Example:
                [
                  {"id":"A","label":"Email+password","approach":"...","tradeoffs":"..."},
                  {"id":"B","label":"OAuth only","approach":"...","tradeoffs":"..."}
                ]

        Returns:
            Formatted proposal sheet for user to choose from.
        """
        import datetime
        import json

        _audit("aio__force_taskspec_propose", "CALLED", user_intent[:100] if user_intent else "")

        loop_msg = _loop_guard("aio__force_taskspec_propose", user_intent[:100] if user_intent else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # Validate user_intent
        if not user_intent or not user_intent.strip():
            return "REJECTED: user_intent cannot be empty. Pass the user's original request."

        # Parse proposals JSON
        if not proposals or not proposals.strip():
            return "REJECTED: proposals cannot be empty. Pass a JSON list of >=2 candidates."

        try:
            parsed = json.loads(proposals)
        except json.JSONDecodeError as e:
            return (
                f"REJECTED: proposals must be valid JSON. Parse error: {str(e)[:120]}\n\n"
                f"Expected format:\n"
                f'  [{{"id":"A","label":"...","approach":"...","tradeoffs":"..."}}, ...]'
            )

        if not isinstance(parsed, list):
            return "REJECTED: proposals must be a JSON list (array), got " + type(parsed).__name__

        # Enforce >= 2 candidates (taste needs comparison anchors)
        if len(parsed) < 2:
            return (
                f"REJECTED: must list at least 2 proposals (got {len(parsed)}).\n"
                f"Single-option tasks should go through aio__force_fast_track instead.\n"
                f"Taste judgment needs parallel comparison anchors -- one option = no choice."
            )

        # Validate each proposal has all 4 required fields, non-empty
        REQUIRED_FIELDS = ("id", "label", "approach", "tradeoffs")
        seen_ids = set()
        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                return f"REJECTED: proposals[{i}] must be an object, got {type(item).__name__}"
            for fld in REQUIRED_FIELDS:
                v = item.get(fld)
                if not v or not isinstance(v, str) or not v.strip():
                    return (
                        f"REJECTED: proposals[{i}].{fld} missing or empty. "
                        f"All 4 fields ({', '.join(REQUIRED_FIELDS)}) are mandatory."
                    )
            pid = item["id"].strip()
            if pid in seen_ids:
                return f"REJECTED: duplicate proposal id '{pid}'. Each proposal needs a unique id."
            seen_ids.add(pid)

        # Build the proposal sheet for user
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        sheet_parts = [
            f"# TaskSpec Proposals\n",
            f"> Generated: {timestamp}\n",
            f"> Status: **AWAITING USER CHOICE**\n",
            f"\n## User Intent\n{user_intent.strip()}\n",
            f"\n## Candidates ({len(parsed)})\n",
        ]
        for item in parsed:
            sheet_parts.append(
                f"\n### [{item['id'].strip()}] {item['label'].strip()}\n"
                f"**Approach**: {item['approach'].strip()}\n\n"
                f"**Trade-offs**: {item['tradeoffs'].strip()}\n"
            )
        sheet = "".join(sheet_parts)

        # Persist proposed flag (single-use; consumed on submit success)
        TASKSPEC_PROPOSED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        flag_payload = {
            "timestamp": timestamp,
            "user_intent": user_intent.strip(),
            "proposal_ids": [item["id"].strip() for item in parsed],
            "proposals": parsed,
        }
        TASKSPEC_PROPOSED_FLAG.write_text(
            json.dumps(flag_payload, ensure_ascii=False),
            encoding="utf-8",
        )

        # Clear any prior approval flag (new proposal cycle invalidates old approval)
        if TASKSPEC_APPROVED_FLAG.exists():
            TASKSPEC_APPROVED_FLAG.unlink()

        _audit("aio__force_taskspec_propose", "SUCCESS",
               f"intent={user_intent[:50]}, n={len(parsed)}")

        return (
            f"SUCCESS: {len(parsed)} proposals listed for user choice.\n\n"
            f"{sheet}\n"
            f"---\n"
            f"[PAUSE] Waiting for user to choose one proposal id (e.g. 'A' or 'B').\n"
            f"After user picks, call aio__force_taskspec_submit with "
            f"chosen_proposal_id=<picked_id> + the 6 spec sections."
        )

    @mcp.tool()
    def aio__force_taskspec_submit(
        task_goal: str,
        scope_and_impact: str,
        files_to_modify: str,
        technical_constraints: str,
        acceptance_criteria: str,
        doc_impact: str,
        chosen_proposal_id: str = "",
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
            chosen_proposal_id: Which proposal id (e.g. "A") the user picked from
                the prior aio__force_taskspec_propose call. Must match an id in
                the active proposed flag. BYPASSABLE if no proposal was ever made
                (e.g. routing through fast_track context).
            dry_run: Set to "true" to validate without writing. Returns all violations at once.

        Returns:
            The formatted taskSpec for user review, or dry-run validation report.
        """
        import datetime
        import json
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

        # -- Propose flag gate (议题 #014 v3) --------------------
        # Default: submit must follow a prior aio__force_taskspec_propose call.
        # BYPASSABLE rule -- user can authorize bypass for cases where parallel
        # candidates do not apply (e.g. mechanical fix that escalates beyond
        # fast_track but truly has only one reasonable path).
        RULE_NO_PROPOSE = "taskspec.no_prior_propose"
        RULE_INVALID_PROPOSAL_ID = "taskspec.invalid_proposal_id"
        chosen_label = ""
        chosen_approach = ""

        if TASKSPEC_PROPOSED_FLAG.exists():
            try:
                payload = json.loads(TASKSPEC_PROPOSED_FLAG.read_text(encoding="utf-8"))
                proposal_ids = payload.get("proposal_ids", [])
                proposals_list = payload.get("proposals", [])
            except (json.JSONDecodeError, OSError):
                # Corrupt flag -- treat as missing
                proposal_ids = []
                proposals_list = []

            cid = (chosen_proposal_id or "").strip()
            if not cid:
                return (
                    f"REJECTED: chosen_proposal_id is required when a propose flag is active.\n"
                    f"Available ids: {proposal_ids}\n"
                    f"Pass the id the user picked (e.g. chosen_proposal_id=\"A\")."
                )
            if cid not in proposal_ids:
                if is_monitor_rule(RULE_INVALID_PROPOSAL_ID):
                    _audit("aio__force_taskspec_submit", "MONITOR",
                           f"rule={RULE_INVALID_PROPOSAL_ID}, cid={cid}")
                elif has_bypass(RULE_INVALID_PROPOSAL_ID):
                    _audit("aio__force_taskspec_submit", "BYPASSED",
                           f"rule={RULE_INVALID_PROPOSAL_ID}")
                    clear_bypass(RULE_INVALID_PROPOSAL_ID)
                else:
                    return (
                        f"REJECTED: chosen_proposal_id '{cid}' not in proposed list {proposal_ids}.\n"
                        f"Either pass a valid id or call aio__force_taskspec_propose again "
                        f"with the user's actual choice."
                    )
            else:
                # Capture chosen proposal's label + approach for spec header
                for item in proposals_list:
                    if isinstance(item, dict) and item.get("id", "").strip() == cid:
                        chosen_label = (item.get("label") or "").strip()
                        chosen_approach = (item.get("approach") or "").strip()
                        break
        else:
            # No propose flag -- BYPASSABLE rule
            if is_monitor_rule(RULE_NO_PROPOSE):
                _audit("aio__force_taskspec_submit", "MONITOR", f"rule={RULE_NO_PROPOSE}")
            elif has_bypass(RULE_NO_PROPOSE):
                _audit("aio__force_taskspec_submit", "BYPASSED", f"rule={RULE_NO_PROPOSE}")
                clear_bypass(RULE_NO_PROPOSE)
            else:
                _audit("aio__force_taskspec_submit", "BYPASSABLE", "no prior propose")
                return (
                    f"BYPASSABLE: no prior aio__force_taskspec_propose call detected.\n"
                    f"Rule: {RULE_NO_PROPOSE}\n\n"
                    f"Default flow: [提需] -> propose (>=2 candidates) -> user picks "
                    f"-> submit -> approve.\n\n"
                    f"Option 1: Call aio__force_taskspec_propose first with >=2 candidates, "
                    f"wait for user's pick, then resubmit with chosen_proposal_id.\n"
                    f"Option 2: Use aio__force_fast_track if change is trivial enough.\n"
                    f"Option 3: Ask user to authorize bypass -> call aio__bypass_violation(\n"
                    f"  rule_code=\"{RULE_NO_PROPOSE}\", user_said=\"<user's exact words>\")"
                )

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

        # Optional chosen-proposal header (议题 #014 v3)
        chosen_section = ""
        if chosen_label or chosen_approach:
            chosen_section = (
                f"## 0. Chosen Proposal\n"
                f"**[{(chosen_proposal_id or '').strip()}] {chosen_label}**\n\n"
                f"{chosen_approach}\n\n"
            )

        # Build the taskSpec document
        spec_content = (
            f"# Task Specification\n\n"
            f"> Generated: {timestamp}\n"
            f"> Status: **PENDING APPROVAL**\n\n"
            f"{chosen_section}"
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

        # Consume the propose flag (single-use; new propose cycle for next task)
        if TASKSPEC_PROPOSED_FLAG.exists():
            TASKSPEC_PROPOSED_FLAG.unlink()

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
                         "corrections"],
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

    # ===============================================================
    # Acceptance Closure (议题 #022 — 三层代理 VERIFIER 阶段)
    # ===============================================================
    # Flow:
    #   acceptance_propose  -> AI lists what to verify (3 categories)
    #   acceptance_approve  -> user signs off on the list
    #   acceptance_run      -> AI runs the tests; on failure enters fix loop
    #                          (counter-tracked, max 3 rounds, then forced stop)
    #   verified flag       -> [存档] gate checks this; missing => save rejected
    # Fast-track path is exempt (no taskspec => no acceptance required).

    @mcp.tool()
    def aio__force_acceptance_propose(
        unit_tests: str,
        integration_tests: str,
        business_flow: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Propose an acceptance checklist after WORKER finishes code.

        Must be called BEFORE the user can approve any acceptance, and BEFORE
        running any verification. Three categories, all required (use "NONE: <reason>"
        to explicitly skip a category — never an empty string).

        Args:
            unit_tests: Concrete test commands (one per line, e.g.
                "python -m pytest tests/test_foo.py -v"). NONE: <reason> to skip.
            integration_tests: Concrete module-level test commands. NONE: <reason> to skip.
            business_flow: Natural-language description of the end-to-end user paths
                to manually walk through (e.g. "1. login with new email
                2. add item to cart 3. checkout via wechat pay 4. verify order
                appears in history"). NONE: <reason> to skip.

        Returns:
            The formatted acceptance checklist for user review, or REJECTED.
        """
        import datetime
        import json

        _audit("aio__force_acceptance_propose", "CALLED")

        loop_msg = _loop_guard("aio__force_acceptance_propose", unit_tests[:80] if unit_tests else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # Validate: each field must be non-empty (NONE allowed but must be explicit)
        fields = {
            "unit_tests": unit_tests,
            "integration_tests": integration_tests,
            "business_flow": business_flow,
        }
        for name, value in fields.items():
            if not value or not value.strip():
                return (
                    f"REJECTED: {name} cannot be empty. "
                    f"All 3 categories must be addressed. Use 'NONE: <reason>' "
                    f"to explicitly skip a category."
                )

        # Reject "bare NONE" without reason (same pattern as save's NO_CHANGE_BECAUSE)
        for name, value in fields.items():
            stripped = value.strip()
            if stripped.upper() == "NONE":
                return (
                    f"REJECTED: {name} is bare 'NONE'. "
                    f"You must write 'NONE: <reason>' explaining WHY this category is skipped. "
                    f"e.g. 'NONE: pure docs change, no code to test'"
                )

        # At least one category must have real content (not all NONE)
        non_none_count = sum(
            1 for v in fields.values() if not v.strip().upper().startswith("NONE")
        )
        if non_none_count == 0:
            return (
                "REJECTED: All 3 categories are skipped as NONE. "
                "If truly nothing to verify, use aio__force_fast_track instead "
                "(acceptance is for non-trivial changes)."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        payload = {
            "timestamp": timestamp,
            "unit_tests": unit_tests.strip(),
            "integration_tests": integration_tests.strip(),
            "business_flow": business_flow.strip(),
        }

        # New propose cycle invalidates any prior approve/verified/fix state
        for flag in (ACCEPTANCE_APPROVED_FLAG, ACCEPTANCE_VERIFIED_FLAG,
                     ACCEPTANCE_FIX_COUNTER_FLAG, ACCEPTANCE_FIX_HISTORY_FLAG):
            if flag.exists():
                flag.unlink()

        ACCEPTANCE_PROPOSED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ACCEPTANCE_PROPOSED_FLAG.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _audit("aio__force_acceptance_propose", "SUCCESS",
               f"non_none={non_none_count}/3")

        sheet = (
            f"# Acceptance Checklist (议题 #022)\n\n"
            f"> Generated: {timestamp}\n"
            f"> Status: **AWAITING USER APPROVAL**\n\n"
            f"## 1. Unit Tests\n{unit_tests.strip()}\n\n"
            f"## 2. Integration Tests\n{integration_tests.strip()}\n\n"
            f"## 3. Business Flow (manual walk-through)\n{business_flow.strip()}\n"
        )

        return (
            f"SUCCESS: Acceptance checklist proposed.\n\n"
            f"{sheet}\n"
            f"---\n"
            f"[PAUSE] Waiting for user approval. After user says '批准/ok go',\n"
            f"call aio__force_acceptance_approve."
        )

    @mcp.tool()
    def aio__force_acceptance_approve(user_said: str) -> str:
        """
        [ENFORCEMENT TOOL] Record user approval of the proposed acceptance checklist.

        Must follow aio__force_acceptance_propose. Gates the acceptance_run tool.

        Args:
            user_said: Exact user approval text (e.g. "批准", "ok go", "approved").

        Returns:
            Approval confirmation or REJECTED.
        """
        import datetime

        _audit("aio__force_acceptance_approve", "CALLED", user_said[:50] if user_said else "")

        loop_msg = _loop_guard("aio__force_acceptance_approve", user_said[:50] if user_said else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        if not ACCEPTANCE_PROPOSED_FLAG.exists():
            return (
                "REJECTED: No acceptance checklist proposed. "
                "Call aio__force_acceptance_propose first."
            )

        approval_signals = ["批准", "approved", "ok go", "执行", "ok", "go",
                            "yes", "可以", "同意"]
        if not any(sig in (user_said or "").lower() for sig in approval_signals):
            return (
                f"REJECTED: '{user_said}' does not look like approval. "
                f"Expected one of: {', '.join(approval_signals)}"
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        ACCEPTANCE_APPROVED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ACCEPTANCE_APPROVED_FLAG.write_text(
            f"approved|{timestamp}|{(user_said or '').strip()[:50]}",
            encoding="utf-8",
        )

        _audit("aio__force_acceptance_approve", "SUCCESS")

        return (
            f"SUCCESS: Acceptance checklist APPROVED at {timestamp}.\n"
            f"You may now call aio__force_acceptance_run to execute the verification.\n"
            f"On failure, the tool will enter a fix loop (max {ACCEPTANCE_MAX_FIX_ROUNDS} rounds)."
        )

    @mcp.tool()
    def aio__force_acceptance_run(
        unit_test_cmd: str,
        integration_test_cmd: str,
        business_flow_result: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Run the approved acceptance checklist; manage fix loop.

        Behavior:
          - Requires aio__force_acceptance_approve already called.
          - Runs unit_test_cmd + integration_test_cmd (NONE: <reason> to skip).
          - Reads business_flow_result (AI-reported, since business flow can't be
            auto-run). Must contain only success markers OR explicit failure markers.
          - All three pass => write VERIFIED_FLAG, clear fix counter, return SUCCESS.
          - Any failure => increment fix counter, append to history, return
            FIX_LOOP_REQUIRED with failure details. Max 3 rounds; round 3 returns
            FIX_LOOP_EXHAUSTED and refuses further attempts until user intervenes.

        Args:
            unit_test_cmd: Shell command to run unit tests (e.g.
                "python -m pytest tests/foo -v"). "NONE: <reason>" to skip.
            integration_test_cmd: Shell command for integration tests.
                "NONE: <reason>" to skip.
            business_flow_result: AI-reported result of manually walking the
                business flow. MUST contain explicit "PASS" or "FAIL" markers
                per step (e.g. "step 1: login PASS / step 2: checkout FAIL because ...").
                "NONE: <reason>" to skip.

        Returns:
            One of: SUCCESS (verified), FIX_LOOP_REQUIRED (try again),
            FIX_LOOP_EXHAUSTED (stop and ask user), REJECTED (preconditions wrong).
        """
        import datetime
        import json

        _audit("aio__force_acceptance_run", "CALLED")

        loop_msg = _loop_guard("aio__force_acceptance_run", unit_test_cmd[:80] if unit_test_cmd else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # Gate 1: must have approved checklist
        if not ACCEPTANCE_APPROVED_FLAG.exists():
            return (
                "REJECTED: No approved acceptance checklist. "
                "Run aio__force_acceptance_propose -> aio__force_acceptance_approve first."
            )

        # Gate 2: check fix counter — if already exhausted, refuse to re-run
        current_round = 0
        if ACCEPTANCE_FIX_COUNTER_FLAG.exists():
            try:
                current_round = int(ACCEPTANCE_FIX_COUNTER_FLAG.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                current_round = 0
        if current_round >= ACCEPTANCE_MAX_FIX_ROUNDS:
            history = ""
            if ACCEPTANCE_FIX_HISTORY_FLAG.exists():
                history = ACCEPTANCE_FIX_HISTORY_FLAG.read_text(encoding="utf-8")
            return (
                f"REJECTED: FIX_LOOP_EXHAUSTED — already used {current_round} fix rounds "
                f"(max {ACCEPTANCE_MAX_FIX_ROUNDS}).\n\n"
                f"Stop and ask the user how to proceed. Options:\n"
                f"  1. User issues new taskspec for a different approach (counter resets)\n"
                f"  2. User authorizes fast-track override\n"
                f"  3. User explicitly resets counter (delete .acceptance_fix_counter)\n\n"
                f"Fix history:\n{history}"
            )

        # Validate three input fields non-empty
        fields = {
            "unit_test_cmd": unit_test_cmd,
            "integration_test_cmd": integration_test_cmd,
            "business_flow_result": business_flow_result,
        }
        for name, value in fields.items():
            if not value or not value.strip():
                return (
                    f"REJECTED: {name} cannot be empty. "
                    f"Use 'NONE: <reason>' to skip a category."
                )

        # Helper: detect explicit "skip" markers without false-matching real commands
        # that happen to start with the letters NONE (e.g. `nonexistent_xyz`).
        def _is_skip_marker(s: str) -> bool:
            u = (s or "").strip().upper()
            return u == "NONE" or u.startswith("NONE:") or u.startswith("NONE ")

        # Helper: run a shell test command
        def _run_test(cmd: str) -> tuple:
            """Returns (status, rc, stdout, stderr) where status in {'pass','fail','skip','env_error'}."""
            stripped = cmd.strip()
            if _is_skip_marker(stripped):
                return ("skip", 0, f"(skipped: {stripped})", "")
            # Forbid pipeline-wide commands (same gate as test_runner)
            for kw in ("--all", "full_pipeline", "run_all", "test_everything"):
                if kw in stripped.lower():
                    return ("env_error", -1, "",
                            f"REJECTED: contains '{kw}' (full pipeline forbidden)")
            try:
                result = subprocess.run(
                    stripped.split(),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                status = "pass" if result.returncode == 0 else "fail"
                # Truncate output to keep return manageable
                out = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
                err = result.stderr[-1500:] if len(result.stderr) > 1500 else result.stderr
                return (status, result.returncode, out, err)
            except subprocess.TimeoutExpired:
                return ("env_error", -1, "", "TIMEOUT after 300s")
            except FileNotFoundError:
                return ("env_error", -1, "", f"command not found: {stripped.split()[0] if stripped.split() else ''}")
            except Exception as e:
                return ("env_error", -1, "", f"unexpected: {str(e)[:200]}")

        # Run unit + integration tests
        unit_status, unit_rc, unit_out, unit_err = _run_test(unit_test_cmd)
        integ_status, integ_rc, integ_out, integ_err = _run_test(integration_test_cmd)

        # Evaluate business_flow_result (AI-reported)
        # Pass condition: contains no "FAIL" markers (case insensitive)
        bf_stripped = business_flow_result.strip()
        if _is_skip_marker(bf_stripped):
            bf_status = "skip"
            bf_summary = bf_stripped
        elif "FAIL" in bf_stripped.upper():
            bf_status = "fail"
            bf_summary = bf_stripped[:1500]
        else:
            # Sanity: must contain a positive marker (PASS or ✓ or "成功")
            positive_markers = ["PASS", "✓", "成功", "通过", "OK"]
            has_positive = any(m in bf_stripped.upper() if m.isascii() else m in bf_stripped
                               for m in positive_markers)
            if not has_positive:
                bf_status = "fail"
                bf_summary = (
                    f"Reported result has no explicit PASS marker. AI must report "
                    f"per-step PASS or FAIL. Raw report:\n{bf_stripped[:1000]}"
                )
            else:
                bf_status = "pass"
                bf_summary = bf_stripped[:800]

        # Special handling: env_error in cmds means "can't even run the tests" —
        # this is NOT a fix loop case (fixing code won't help). Stop and ask user.
        env_problems = []
        if unit_status == "env_error":
            env_problems.append(f"unit_tests env_error: {unit_err}")
        if integ_status == "env_error":
            env_problems.append(f"integration_tests env_error: {integ_err}")
        if env_problems:
            _audit("aio__force_acceptance_run", "ENV_ERROR", "; ".join(env_problems)[:200])
            return (
                f"ENV_ERROR: tests could not be run (not a fix-loop case).\n\n"
                + "\n".join(env_problems)
                + "\n\nStop and ask the user — fixing code won't resolve a test "
                f"environment problem."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Compose status summary
        statuses = {"unit": unit_status, "integration": integ_status, "business": bf_status}
        all_pass = all(s in ("pass", "skip") for s in statuses.values())

        if all_pass:
            # SUCCESS — write verified flag, clear fix state
            ACCEPTANCE_VERIFIED_FLAG.parent.mkdir(parents=True, exist_ok=True)
            verified_payload = {
                "timestamp": timestamp,
                "unit": statuses["unit"],
                "integration": statuses["integration"],
                "business": statuses["business"],
                "fix_rounds_used": current_round,
            }
            ACCEPTANCE_VERIFIED_FLAG.write_text(
                json.dumps(verified_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # Clean fix counter / history
            for f in (ACCEPTANCE_FIX_COUNTER_FLAG, ACCEPTANCE_FIX_HISTORY_FLAG):
                if f.exists():
                    f.unlink()

            _audit("aio__force_acceptance_run", "SUCCESS",
                   f"rounds_used={current_round}")
            return (
                f"SUCCESS: All acceptance categories passed.\n"
                f"  - Unit: {statuses['unit']}\n"
                f"  - Integration: {statuses['integration']}\n"
                f"  - Business flow: {statuses['business']}\n"
                f"Fix rounds used: {current_round}\n\n"
                f"VERIFIED flag written. You may now call [存档] / aio__force_architect_save."
            )

        # FAILURE PATH — enter / continue fix loop
        new_round = current_round + 1
        ACCEPTANCE_FIX_COUNTER_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ACCEPTANCE_FIX_COUNTER_FLAG.write_text(str(new_round), encoding="utf-8")

        # Append to history
        round_entry = (
            f"## Round {new_round} @ {timestamp}\n"
            f"Unit: {statuses['unit']}\n"
            f"  stdout-tail: {unit_out[-500:] if unit_out else '(empty)'}\n"
            f"  stderr-tail: {unit_err[-500:] if unit_err else '(empty)'}\n"
            f"Integration: {statuses['integration']}\n"
            f"  stdout-tail: {integ_out[-500:] if integ_out else '(empty)'}\n"
            f"  stderr-tail: {integ_err[-500:] if integ_err else '(empty)'}\n"
            f"Business flow: {statuses['business']}\n"
            f"  report-summary: {bf_summary[:400]}\n"
            f"---\n"
        )
        history_existing = ""
        if ACCEPTANCE_FIX_HISTORY_FLAG.exists():
            history_existing = ACCEPTANCE_FIX_HISTORY_FLAG.read_text(encoding="utf-8")
        ACCEPTANCE_FIX_HISTORY_FLAG.write_text(history_existing + round_entry, encoding="utf-8")

        # Decide: continue fix loop or exhausted
        if new_round >= ACCEPTANCE_MAX_FIX_ROUNDS:
            _audit("aio__force_acceptance_run", "EXHAUSTED", f"round={new_round}")
            return (
                f"FIX_LOOP_EXHAUSTED: round {new_round}/{ACCEPTANCE_MAX_FIX_ROUNDS} failed.\n\n"
                f"Stop and ask the user how to proceed.\n\n"
                f"Latest failure summary:\n{round_entry}\n"
                f"Subsequent acceptance_run calls will be rejected until user intervenes."
            )

        _audit("aio__force_acceptance_run", "FIX_LOOP_REQUIRED",
               f"round={new_round}, unit={statuses['unit']}, "
               f"integ={statuses['integration']}, bf={statuses['business']}")
        return (
            f"FIX_LOOP_REQUIRED: round {new_round}/{ACCEPTANCE_MAX_FIX_ROUNDS}.\n\n"
            f"Status: unit={statuses['unit']}, "
            f"integration={statuses['integration']}, business={statuses['business']}\n\n"
            f"You MUST fix the code and re-run acceptance. Do NOT try to bypass "
            f"by going straight to [存档] — save will be rejected without VERIFIED flag.\n\n"
            f"This round's failure:\n{round_entry}"
        )

    # ===============================================================
    # Visual Closure (议题 #023 — 前端视觉化闭环)
    # ===============================================================
    # Two-stage flow:
    #   1. designer_translate (上游): user natural language -> designer spec
    #      - propose: AI writes the translated spec
    #      - approve: user signs off on the spec
    #      - downstream WORKER reads designer_spec.md
    #   2. visual closure (下游): code -> visual verification
    #      - visual_propose: AI proposes a keypoint checklist
    #      - visual_approve: user signs off on the checklist
    #      - visual_verify: AI runs Playwright MCP for screenshots, self-evaluates
    #        keypoints; fix loop on failure (max 3 rounds, independent counter
    #        from acceptance fix loop)
    #
    # Format policy (议题 #023 用户拍板): designer spec and keypoint checklists
    # are FREE-FORM TEXT, not fixed-field tables. The AI structures them per
    # context. Only minimal length / content checks are enforced.

    @mcp.tool()
    def aio__force_designer_translate_propose(
        user_intent: str,
        translated_spec: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] AI translates user's natural-language visual intent
        into a designer-language spec (free-form text, not a fixed schema).

        Used at the front of any frontend / visual taskspec. The translated
        spec lands at .ai-operation/docs/designer_spec.md and feeds downstream
        WORKER code generation.

        Args:
            user_intent: The user's original natural-language description
                (e.g. "我想要一个简洁的、给中年女性看的护肤首页,不要太花哨").
            translated_spec: AI's structured restatement in designer language.
                FREE FORM — let the AI choose the structure that fits the
                context (color palette, tone, layout density, hierarchy,
                target audience, device, references, anti-patterns, ...).
                Minimum 150 chars to avoid trivial responses.

        Returns:
            The proposed spec, awaiting user approval.
        """
        import datetime

        _audit("aio__force_designer_translate_propose", "CALLED",
               user_intent[:100] if user_intent else "")

        loop_msg = _loop_guard("aio__force_designer_translate_propose",
                               user_intent[:80] if user_intent else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        if not user_intent or not user_intent.strip():
            return "REJECTED: user_intent cannot be empty."
        if not translated_spec or not translated_spec.strip():
            return "REJECTED: translated_spec cannot be empty."
        if len(translated_spec.strip()) < 150:
            return (
                f"REJECTED: translated_spec is too short ({len(translated_spec.strip())} chars). "
                f"Minimum 150 chars to ensure meaningful translation. "
                f"A real designer spec covers multiple visual dimensions "
                f"(tone, palette, hierarchy, audience, device, references)."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Persist the spec to a markdown file (becomes part of project memory)
        DESIGNER_SPEC_FILE.parent.mkdir(parents=True, exist_ok=True)
        spec_doc = (
            f"# Designer Spec (议题 #023)\n\n"
            f"> Generated: {timestamp}\n"
            f"> Status: **AWAITING USER APPROVAL**\n\n"
            f"## Original User Intent\n{user_intent.strip()}\n\n"
            f"## AI-Translated Designer Language\n{translated_spec.strip()}\n"
        )
        DESIGNER_SPEC_FILE.write_text(spec_doc, encoding="utf-8")

        # Clear any prior approval / downstream visual state from a previous cycle
        for f in (DESIGNER_SPEC_APPROVED_FLAG,
                  VISUAL_KEYPOINTS_PROPOSED_FLAG, VISUAL_KEYPOINTS_APPROVED_FLAG,
                  VISUAL_VERIFIED_FLAG, VISUAL_FIX_COUNTER_FLAG,
                  VISUAL_FIX_HISTORY_FLAG):
            if f.exists():
                f.unlink()

        DESIGNER_SPEC_PROPOSED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        DESIGNER_SPEC_PROPOSED_FLAG.write_text(
            f"proposed|{timestamp}|{len(translated_spec.strip())}chars",
            encoding="utf-8",
        )

        _audit("aio__force_designer_translate_propose", "SUCCESS",
               f"{len(translated_spec.strip())} chars")

        return (
            f"SUCCESS: Designer spec proposed.\n\n"
            f"{spec_doc}\n"
            f"---\n"
            f"[PAUSE] Waiting for user approval. After user says '批准/ok go',\n"
            f"call aio__force_designer_translate_approve."
        )

    @mcp.tool()
    def aio__force_designer_translate_approve(user_said: str) -> str:
        """
        [ENFORCEMENT TOOL] Record user approval of the translated designer spec.

        Args:
            user_said: User approval text.

        Returns:
            Approval recorded; spec is now the canonical input for WORKER.
        """
        import datetime

        _audit("aio__force_designer_translate_approve", "CALLED",
               user_said[:50] if user_said else "")

        loop_msg = _loop_guard("aio__force_designer_translate_approve",
                               user_said[:50] if user_said else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        if not DESIGNER_SPEC_PROPOSED_FLAG.exists():
            return (
                "REJECTED: No designer spec proposed. "
                "Call aio__force_designer_translate_propose first."
            )

        approval_signals = ["批准", "approved", "ok go", "执行", "ok", "go",
                            "yes", "可以", "同意"]
        if not any(sig in (user_said or "").lower() for sig in approval_signals):
            return (
                f"REJECTED: '{user_said}' does not look like approval. "
                f"Expected one of: {', '.join(approval_signals)}"
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        DESIGNER_SPEC_APPROVED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        DESIGNER_SPEC_APPROVED_FLAG.write_text(
            f"approved|{timestamp}|{(user_said or '').strip()[:50]}",
            encoding="utf-8",
        )

        # Update spec doc status header
        if DESIGNER_SPEC_FILE.exists():
            try:
                content = DESIGNER_SPEC_FILE.read_text(encoding="utf-8")
                updated = content.replace(
                    "**AWAITING USER APPROVAL**",
                    f"**APPROVED** ({timestamp})",
                )
                DESIGNER_SPEC_FILE.write_text(updated, encoding="utf-8")
            except OSError:
                pass

        _audit("aio__force_designer_translate_approve", "SUCCESS")

        return (
            f"SUCCESS: Designer spec APPROVED at {timestamp}.\n"
            f"WORKER can now read .ai-operation/docs/designer_spec.md "
            f"and generate frontend code per the spec.\n"
            f"After code is written, call aio__force_visual_propose to start "
            f"the visual verification closure."
        )

    @mcp.tool()
    def aio__force_visual_propose(visual_keypoints: str) -> str:
        """
        [ENFORCEMENT TOOL] AI proposes a visual-verification checklist after
        finishing frontend code. Free-form text — the AI structures the
        keypoints per context.

        Typical keypoints (AI picks what's relevant):
          - 第一层级元素位置 / 主色对照 / 信息层级强度 / 留白密度 /
            移动端响应 / 字体一致性 / 视觉对标参考...

        Args:
            visual_keypoints: AI's proposed checklist. Free form but must
                cover at least 2 distinct keypoints (heuristic: contains 2+
                newline-separated bullets or numbered items). Minimum 80 chars.

        Returns:
            The proposed checklist, awaiting user approval.
        """
        import datetime
        import re

        _audit("aio__force_visual_propose", "CALLED")

        loop_msg = _loop_guard("aio__force_visual_propose",
                               visual_keypoints[:80] if visual_keypoints else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        if not visual_keypoints or not visual_keypoints.strip():
            return "REJECTED: visual_keypoints cannot be empty."
        stripped = visual_keypoints.strip()
        if len(stripped) < 80:
            return (
                f"REJECTED: visual_keypoints too short ({len(stripped)} chars). "
                f"Minimum 80 chars. A real checklist covers multiple visual aspects."
            )

        # Heuristic: count "items" — newlines + bullet markers + numbers
        item_pattern = re.compile(r"^\s*(?:[-*+•]|\d+[.\)、])", re.MULTILINE)
        item_count = len(item_pattern.findall(stripped))
        if item_count < 2:
            return (
                f"REJECTED: visual_keypoints must contain at least 2 distinct "
                f"keypoints (bullet-style or numbered). Found {item_count}. "
                f"Use lines starting with '-', '*', or '1.', '2.' etc."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # New propose cycle invalidates downstream state
        for flag in (VISUAL_KEYPOINTS_APPROVED_FLAG, VISUAL_VERIFIED_FLAG,
                     VISUAL_FIX_COUNTER_FLAG, VISUAL_FIX_HISTORY_FLAG):
            if flag.exists():
                flag.unlink()

        VISUAL_KEYPOINTS_PROPOSED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        VISUAL_KEYPOINTS_PROPOSED_FLAG.write_text(
            f"---\ntimestamp: {timestamp}\nitems: {item_count}\n---\n{stripped}\n",
            encoding="utf-8",
        )

        _audit("aio__force_visual_propose", "SUCCESS", f"items={item_count}")

        return (
            f"SUCCESS: Visual checklist proposed ({item_count} keypoints).\n\n"
            f"## Proposed Visual Verification Checklist\n\n"
            f"{stripped}\n\n"
            f"---\n"
            f"[PAUSE] Waiting for user approval. After user says '批准/ok go',\n"
            f"call aio__force_visual_approve."
        )

    @mcp.tool()
    def aio__force_visual_approve(user_said: str) -> str:
        """
        [ENFORCEMENT TOOL] Record user approval of the visual keypoint checklist.

        Args:
            user_said: User approval text.

        Returns:
            Approval recorded; next step is aio__force_visual_verify.
        """
        import datetime

        _audit("aio__force_visual_approve", "CALLED",
               user_said[:50] if user_said else "")

        loop_msg = _loop_guard("aio__force_visual_approve",
                               user_said[:50] if user_said else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        if not VISUAL_KEYPOINTS_PROPOSED_FLAG.exists():
            return (
                "REJECTED: No visual checklist proposed. "
                "Call aio__force_visual_propose first."
            )

        approval_signals = ["批准", "approved", "ok go", "执行", "ok", "go",
                            "yes", "可以", "同意"]
        if not any(sig in (user_said or "").lower() for sig in approval_signals):
            return (
                f"REJECTED: '{user_said}' does not look like approval. "
                f"Expected one of: {', '.join(approval_signals)}"
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        VISUAL_KEYPOINTS_APPROVED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        VISUAL_KEYPOINTS_APPROVED_FLAG.write_text(
            f"approved|{timestamp}|{(user_said or '').strip()[:50]}",
            encoding="utf-8",
        )

        _audit("aio__force_visual_approve", "SUCCESS")

        return (
            f"SUCCESS: Visual checklist APPROVED at {timestamp}.\n"
            f"You may now call aio__force_visual_verify after running Playwright "
            f"MCP screenshots and self-evaluating each keypoint.\n"
            f"On failure, the tool enters a fix loop (max {VISUAL_MAX_FIX_ROUNDS} rounds, "
            f"independent of the acceptance fix counter)."
        )

    @mcp.tool()
    def aio__force_visual_verify(
        keypoint_results: str,
        screenshots_meta: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Submit the AI-reported visual verification verdict.

        The AI is expected to:
          1. Call the Playwright MCP server (separate MCP tool, installed by
             setup.sh/setup.ps1) to launch a headless browser and take
             screenshots of the rendered frontend.
          2. Use its own multimodal vision capability to inspect each screenshot
             against the approved keypoint checklist.
          3. Submit a per-keypoint verdict to this tool.

        This tool does NOT call Playwright itself — it gates the result the AI
        reports. 议题 #013 同源精神: 强制路径, 信任内容.

        Args:
            keypoint_results: AI-reported verdict per keypoint. MUST contain
                explicit PASS or FAIL markers per keypoint (case-insensitive),
                e.g. "1. 第一层级按钮位置 PASS (主按钮在视觉中心)
                      2. 主色对照 FAIL (实际偏冷,spec 要求暖色)".
                Free form otherwise. Minimum 100 chars.
            screenshots_meta: Brief description of which screenshots were taken
                (paths or descriptions; e.g. "homepage 375x812 + 1440x900,
                checkout-page 375x812"). Minimum 30 chars.

        Returns:
            SUCCESS (verified), FIX_LOOP_REQUIRED, FIX_LOOP_EXHAUSTED, or REJECTED.
        """
        import datetime

        _audit("aio__force_visual_verify", "CALLED")

        loop_msg = _loop_guard("aio__force_visual_verify",
                               keypoint_results[:80] if keypoint_results else "")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # Gate 1: approved checklist must exist
        if not VISUAL_KEYPOINTS_APPROVED_FLAG.exists():
            return (
                "REJECTED: No approved visual checklist. "
                "Run aio__force_visual_propose -> aio__force_visual_approve first."
            )

        # Gate 2: check fix counter
        current_round = 0
        if VISUAL_FIX_COUNTER_FLAG.exists():
            try:
                current_round = int(VISUAL_FIX_COUNTER_FLAG.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                current_round = 0
        if current_round >= VISUAL_MAX_FIX_ROUNDS:
            history = ""
            if VISUAL_FIX_HISTORY_FLAG.exists():
                history = VISUAL_FIX_HISTORY_FLAG.read_text(encoding="utf-8")
            return (
                f"REJECTED: VISUAL_FIX_LOOP_EXHAUSTED — already used {current_round} fix rounds "
                f"(max {VISUAL_MAX_FIX_ROUNDS}).\n\n"
                f"Stop and ask the user how to proceed.\n\n"
                f"Visual fix history:\n{history}"
            )

        # Validate input lengths
        if not keypoint_results or len(keypoint_results.strip()) < 100:
            return (
                f"REJECTED: keypoint_results too short "
                f"({len(keypoint_results.strip()) if keypoint_results else 0} chars). "
                f"Minimum 100 chars. Report a PASS/FAIL verdict per keypoint with reasoning."
            )
        if not screenshots_meta or len(screenshots_meta.strip()) < 30:
            return (
                f"REJECTED: screenshots_meta too short. "
                f"Describe which screenshots were taken (paths / viewport sizes / page names)."
            )

        # Must contain explicit PASS or FAIL markers
        kr_upper = keypoint_results.upper()
        has_pass = "PASS" in kr_upper or "✓" in keypoint_results or "通过" in keypoint_results
        has_fail = "FAIL" in kr_upper or "✗" in keypoint_results or "不通过" in keypoint_results or "不符" in keypoint_results

        if not has_pass and not has_fail:
            return (
                "REJECTED: keypoint_results must contain explicit PASS or FAIL "
                "markers per keypoint. Use 'PASS' / 'FAIL' / '✓' / '✗' / '通过' / '不通过'. "
                "Per-keypoint verdict is mandatory."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        overall_pass = has_pass and not has_fail

        if overall_pass:
            # SUCCESS — write verified flag, clear fix state
            VISUAL_VERIFIED_FLAG.parent.mkdir(parents=True, exist_ok=True)
            import json
            verified_payload = {
                "timestamp": timestamp,
                "fix_rounds_used": current_round,
                "screenshots_meta": screenshots_meta.strip()[:500],
                "keypoint_summary": keypoint_results.strip()[:1500],
            }
            VISUAL_VERIFIED_FLAG.write_text(
                json.dumps(verified_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            for f in (VISUAL_FIX_COUNTER_FLAG, VISUAL_FIX_HISTORY_FLAG):
                if f.exists():
                    f.unlink()

            _audit("aio__force_visual_verify", "SUCCESS",
                   f"rounds_used={current_round}")
            return (
                f"SUCCESS: Visual verification PASSED.\n"
                f"Fix rounds used: {current_round}\n"
                f"Screenshots: {screenshots_meta.strip()[:200]}\n\n"
                f"VISUAL_VERIFIED flag written. The visual gate of [存档] is "
                f"satisfied (still requires acceptance VERIFIED if applicable)."
            )

        # FAILURE — enter fix loop
        new_round = current_round + 1
        VISUAL_FIX_COUNTER_FLAG.parent.mkdir(parents=True, exist_ok=True)
        VISUAL_FIX_COUNTER_FLAG.write_text(str(new_round), encoding="utf-8")

        round_entry = (
            f"## Visual Round {new_round} @ {timestamp}\n"
            f"Screenshots: {screenshots_meta.strip()[:300]}\n"
            f"Keypoint verdict:\n{keypoint_results.strip()[:2000]}\n"
            f"---\n"
        )
        history_existing = ""
        if VISUAL_FIX_HISTORY_FLAG.exists():
            history_existing = VISUAL_FIX_HISTORY_FLAG.read_text(encoding="utf-8")
        VISUAL_FIX_HISTORY_FLAG.write_text(
            history_existing + round_entry, encoding="utf-8"
        )

        if new_round >= VISUAL_MAX_FIX_ROUNDS:
            _audit("aio__force_visual_verify", "EXHAUSTED", f"round={new_round}")
            return (
                f"VISUAL_FIX_LOOP_EXHAUSTED: round {new_round}/{VISUAL_MAX_FIX_ROUNDS} failed.\n\n"
                f"Stop and ask user.\n\n"
                f"Latest verdict:\n{round_entry}\n"
                f"Subsequent visual_verify calls will be rejected until user intervenes."
            )

        _audit("aio__force_visual_verify", "FIX_LOOP_REQUIRED",
               f"round={new_round}")
        return (
            f"VISUAL_FIX_LOOP_REQUIRED: round {new_round}/{VISUAL_MAX_FIX_ROUNDS}.\n\n"
            f"Visual verification failed. You MUST fix the frontend code, "
            f"re-run Playwright screenshots, and re-call this tool.\n"
            f"Do NOT bypass by going to [存档] — save rejects without VISUAL_VERIFIED.\n\n"
            f"This round's verdict:\n{round_entry}"
        )
