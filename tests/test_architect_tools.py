"""
Tests for AI-Operation Framework — MCP Architect Enforcement Tools
===================================================================
Tests the core enforcement mechanisms: parameter validation, template merge,
trust scoring, audit logging, and flag lifecycle.

Run: python -m pytest tests/ -v
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Mock the mcp module before importing architect tools
# (mcp[cli] is only installed in the framework venv, not system Python)
sys.modules["mcp"] = MagicMock()
sys.modules["mcp.server"] = MagicMock()
sys.modules["mcp.server.fastmcp"] = MagicMock()

# Add mcp_server to path
REPO_ROOT = Path(__file__).parent.parent
MCP_SERVER_DIR = REPO_ROOT / ".ai-operation" / "mcp_server"
sys.path.insert(0, str(MCP_SERVER_DIR))


class TestSetup:
    """Mixin for creating isolated test environments."""

    def create_temp_project(self):
        """Create a temporary project directory with framework scaffold."""
        self.tmpdir = tempfile.mkdtemp(prefix="aio_test_")
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

        # Create minimal scaffold
        project_map = Path(".ai-operation/docs/project_map")
        project_map.mkdir(parents=True)
        Path(".ai-operation/docs").mkdir(parents=True, exist_ok=True)
        Path(".ai-operation/rules.d").mkdir(parents=True)
        Path(".ai-operation/.mcp_commit_flag").parent.mkdir(parents=True, exist_ok=True)

        # Write template files
        for filename in ["projectbrief.md", "systemPatterns.md", "techContext.md",
                         "activeContext.md", "progress.md"]:
            (project_map / filename).write_text(f"# {filename}\n[待填写]\n", encoding="utf-8")

        # Write corrections.md
        (project_map / "corrections.md").write_text(
            "# Bootstrap Corrections Log\n_暂无记录_\n", encoding="utf-8"
        )

        return self.tmpdir

    def cleanup_temp_project(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestSaveValidation(unittest.TestCase, TestSetup):
    """Test aio__force_architect_save parameter validation."""

    def setUp(self):
        self.create_temp_project()
        # Register tools on a mock MCP
        self.mcp = MagicMock()
        self.mcp.tool = lambda: lambda f: f  # Decorator passthrough
        from tools.architect import register_architect_tools
        self.tools = {}
        original_tool = self.mcp.tool

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def test_rejects_bare_no_change_on_static_files(self):
        """Bare NO_CHANGE without reason is rejected for all 3 static files."""
        result = self.tools["aio__force_architect_save"](
            projectbrief_update="NO_CHANGE",
            systemPatterns_update="NO_CHANGE_BECAUSE: no arch change",
            techContext_update="NO_CHANGE_BECAUSE: no tech change",
            activeContext_update="Working on tests",
            progress_update="✅ Added tests",
            lessons_learned="NONE",
        )
        self.assertIn("REJECTED", result)
        self.assertIn("projectbrief_update", result)
        self.assertIn("NO_CHANGE_BECAUSE", result)

    def test_accepts_no_change_because_with_reason(self):
        """NO_CHANGE_BECAUSE: with a reason is accepted."""
        with patch("subprocess.run"):
            result = self.tools["aio__force_architect_save"](
                projectbrief_update="NO_CHANGE_BECAUSE: only fixed a typo, no vision change",
                systemPatterns_update="NO_CHANGE_BECAUSE: no new modules",
                techContext_update="NO_CHANGE_BECAUSE: no new dependencies",
                activeContext_update=(
                    "Current focus: validating NO_CHANGE_BECAUSE mechanism in tests/test_architect_tools.py\n"
                    "Just completed: modified .ai-operation/mcp_server/tools/architect.py parameter validation logic, "
                    "added NO_CHANGE_BECAUSE enforcement that rejects bare NO_CHANGE without justification reason\n"
                    "Next step: run full pytest suite to confirm all 21 tests pass across the test matrix"
                ),
                progress_update=(
                    "DONE architect.py: added NO_CHANGE_BECAUSE validation, bare NO_CHANGE now REJECTED\n"
                    "DONE tests/test_architect_tools.py: added 2 new tests covering NO_CHANGE_BECAUSE scenarios\n"
                    "TODO run full CI matrix to confirm cross-platform compatibility"
                ),
                lessons_learned="NONE",
            )
        self.assertTrue(result.startswith("PENDING_REVIEW"), f"Expected PENDING_REVIEW, got: {result[:80]}")

    def test_rejects_no_change_active_context(self):
        result = self.tools["aio__force_architect_save"](
            projectbrief_update="NO_CHANGE_BECAUSE: no change",
            systemPatterns_update="NO_CHANGE_BECAUSE: no change",
            techContext_update="NO_CHANGE_BECAUSE: no change",
            activeContext_update="NO_CHANGE",
            progress_update="did stuff",
            lessons_learned="NONE",
        )
        self.assertIn("REJECTED", result)
        self.assertIn("activeContext", result)

    def test_rejects_no_change_progress(self):
        result = self.tools["aio__force_architect_save"](
            projectbrief_update="NO_CHANGE_BECAUSE: no change",
            systemPatterns_update="NO_CHANGE_BECAUSE: no change",
            techContext_update="NO_CHANGE_BECAUSE: no change",
            activeContext_update="Working on tests",
            progress_update="NO_CHANGE",
            lessons_learned="NONE",
        )
        self.assertIn("REJECTED", result)
        self.assertIn("progress", result)

    def test_rejects_empty_lessons_learned(self):
        result = self.tools["aio__force_architect_save"](
            projectbrief_update="NO_CHANGE_BECAUSE: no change",
            systemPatterns_update="NO_CHANGE_BECAUSE: no change",
            techContext_update="NO_CHANGE_BECAUSE: no change",
            activeContext_update="Working on tests",
            progress_update="✅ Added tests",
            lessons_learned="",
        )
        self.assertIn("REJECTED", result)
        self.assertIn("lessons_learned", result)

    def test_accepts_none_lessons(self):
        """NONE is valid for lessons_learned when nothing was learned."""
        with patch("subprocess.run"):
            result = self.tools["aio__force_architect_save"](
                projectbrief_update="NO_CHANGE_BECAUSE: no change",
                systemPatterns_update="NO_CHANGE_BECAUSE: no change",
                techContext_update="NO_CHANGE_BECAUSE: no change",
                activeContext_update=(
                    "Current focus: verifying that lessons_learned=NONE is accepted by the MCP save tool\n"
                    "Just completed: modified tests/test_architect_tools.py to add NONE lessons test case, "
                    "ensuring the tool does not reject valid NONE input when no lessons were learned\n"
                    "Next step: confirm corrections.md has no new entries written when NONE is provided"
                ),
                progress_update=(
                    "DONE tests/test_architect_tools.py: verified NONE lessons scenario is not REJECTED by tool\n"
                    "TODO check corrections.md was not written to when lessons_learned is NONE"
                ),
                lessons_learned="NONE",
            )
        # Should not be REJECTED (may fail on git, that's ok)
        self.assertTrue(result.startswith("PENDING_REVIEW"), f"Expected PENDING_REVIEW, got: {result[:80]}")


class TestTaskSpecWorkflow(unittest.TestCase, TestSetup):
    """Test the taskSpec submit → approve → flag lifecycle."""

    def setUp(self):
        self.create_temp_project()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        mcp = MagicMock()
        mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def test_submit_creates_taskspec_file(self):
        result = self.tools["aio__force_taskspec_submit"](
            task_goal="Add user authentication",
            scope_and_impact="src/auth/ module",
            files_to_modify="src/auth/login.py (new)",
            technical_constraints="Use bcrypt, no plaintext",
            acceptance_criteria="pytest tests/test_auth.py passes",
            doc_impact="systemPatterns.md needs auth module entry",
        )
        self.assertIn("SUCCESS", result)
        self.assertTrue(Path(".ai-operation/docs/taskSpec.md").exists())
        content = Path(".ai-operation/docs/taskSpec.md").read_text()
        self.assertIn("PENDING APPROVAL", content)
        self.assertIn("Add user authentication", content)

    def test_submit_rejects_empty_fields(self):
        result = self.tools["aio__force_taskspec_submit"](
            task_goal="",
            scope_and_impact="something",
            files_to_modify="file.py",
            technical_constraints="none",
            acceptance_criteria="test passes",
            doc_impact="NONE",
        )
        self.assertIn("REJECTED", result)
        self.assertIn("task_goal", result)

    def test_approve_requires_taskspec_exists(self):
        result = self.tools["aio__force_taskspec_approve"](user_said="批准")
        self.assertIn("REJECTED", result)
        self.assertIn("No taskSpec found", result)

    def test_approve_validates_approval_signal(self):
        # First submit
        self.tools["aio__force_taskspec_submit"](
            task_goal="Test",
            scope_and_impact="Test",
            files_to_modify="test.py",
            technical_constraints="none",
            acceptance_criteria="test",
            doc_impact="NONE",
        )
        # Try with invalid signal
        result = self.tools["aio__force_taskspec_approve"](user_said="我不确定")
        self.assertIn("REJECTED", result)
        self.assertIn("does not look like an approval", result)

    def test_approve_creates_flag(self):
        self.tools["aio__force_taskspec_submit"](
            task_goal="Test feature",
            scope_and_impact="Test",
            files_to_modify="test.py",
            technical_constraints="none",
            acceptance_criteria="test passes",
            doc_impact="NONE",
        )
        result = self.tools["aio__force_taskspec_approve"](user_said="批准")
        self.assertIn("SUCCESS", result)
        self.assertTrue(Path(".ai-operation/.taskspec_approved").exists())

    def test_full_lifecycle(self):
        """Submit → approve → verify flag → clear on save simulation."""
        # Submit
        self.tools["aio__force_taskspec_submit"](
            task_goal="Full lifecycle test",
            scope_and_impact="Tests",
            files_to_modify="test.py",
            technical_constraints="none",
            acceptance_criteria="passes",
            doc_impact="NONE",
        )
        # Approve
        self.tools["aio__force_taskspec_approve"](user_said="approved")
        self.assertTrue(Path(".ai-operation/.taskspec_approved").exists())

        # Simulate save clearing the flag
        flag = Path(".ai-operation/.taskspec_approved")
        flag.unlink()
        self.assertFalse(flag.exists())


class TestTrustScore(unittest.TestCase, TestSetup):
    """Test the dynamic trust-based fast-track threshold."""

    def setUp(self):
        self.create_temp_project()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        mcp = MagicMock()
        mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def test_normal_trust_allows_5_lines(self):
        result = self.tools["aio__force_fast_track"](
            reason="Fix typo in variable name",
            change_description="line 1\nline 2\nline 3\nline 4",
        )
        self.assertIn("SUCCESS", result)
        self.assertIn("NORMAL", result)

    def test_normal_trust_rejects_large_change(self):
        result = self.tools["aio__force_fast_track"](
            reason="Small fix",
            change_description="\n".join([f"line {i}" for i in range(12)]),
        )
        self.assertIn("REJECTED", result)

    def test_low_trust_after_corrections(self):
        """With 3+ recent corrections, threshold drops to 3 lines."""
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        corrections = Path(".ai-operation/docs/project_map/corrections.md")
        corrections.write_text(
            f"# Corrections\n"
            f"---\nDATE: {today}\nLESSON: bug1\nCOUNT: 1\n"
            f"---\nDATE: {today}\nLESSON: bug2\nCOUNT: 1\n"
            f"---\nDATE: {today}\nLESSON: bug3\nCOUNT: 1\n",
            encoding="utf-8",
        )
        result = self.tools["aio__force_fast_track"](
            reason="Small rename",
            change_description="line1\nline2\nline3\nline4",
        )
        self.assertIn("REJECTED", result)
        self.assertIn("LOW", result)

    def test_rejects_empty_reason(self):
        result = self.tools["aio__force_fast_track"](reason="", change_description="fix typo")
        self.assertIn("REJECTED", result)


class TestBootstrapMerge(unittest.TestCase, TestSetup):
    """Test that bootstrap_write merges into templates rather than overwriting."""

    def setUp(self):
        self.create_temp_project()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        mcp = MagicMock()
        mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(mcp)

        # Write a template with placeholders
        template = (
            "# Project Brief\n\n"
            "## 1. Vision\n[待填写：vision]\n\n"
            "## 2. KPIs\n[待填写：kpis]\n"
        )
        Path(".ai-operation/docs/project_map/projectbrief.md").write_text(template, encoding="utf-8")

    def tearDown(self):
        self.cleanup_temp_project()

    def test_skip_leaves_file_untouched(self):
        original = Path(".ai-operation/docs/project_map/projectbrief.md").read_text()
        with patch("subprocess.run"):
            self.tools["aio__force_project_bootstrap_write"](
                projectbrief_content="SKIP",
                systemPatterns_content="SKIP",
                techContext_content="SKIP",
                activeContext_focus="Testing",
                progress_initial="- [ ] Tests",
                user_confirmed=True,
            )
        after = Path(".ai-operation/docs/project_map/projectbrief.md").read_text()
        self.assertEqual(original, after)

    def test_merge_replaces_placeholders(self):
        with patch("subprocess.run"):
            self.tools["aio__force_project_bootstrap_write"](
                projectbrief_content="Our big vision===SECTION===Revenue targets",
                systemPatterns_content="SKIP",
                techContext_content="SKIP",
                activeContext_focus="Testing merge",
                progress_initial="- [ ] Verify merge",
                user_confirmed=True,
            )
        content = Path(".ai-operation/docs/project_map/projectbrief.md").read_text()
        self.assertIn("Our big vision", content)
        self.assertIn("Revenue targets", content)
        self.assertIn("## 1. Vision", content)  # Template structure preserved
        self.assertNotIn("[待填写：vision]", content)

    def test_rejects_without_user_confirmed(self):
        result = self.tools["aio__force_project_bootstrap_write"](
            projectbrief_content="content",
            systemPatterns_content="content",
            techContext_content="content",
            activeContext_focus="focus",
            progress_initial="tasks",
            user_confirmed=False,
        )
        self.assertIn("REJECTED", result)
        self.assertIn("user_confirmed", result)

    def test_rejects_todo_placeholders(self):
        result = self.tools["aio__force_project_bootstrap_write"](
            projectbrief_content="Has [TODO] placeholder",
            systemPatterns_content="content",
            techContext_content="content",
            activeContext_focus="focus",
            progress_initial="tasks",
            user_confirmed=True,
        )
        self.assertIn("REJECTED", result)
        self.assertIn("[TODO]", result)


class TestAuditLog(unittest.TestCase, TestSetup):
    """Test that MCP tool calls are logged to audit.log."""

    def setUp(self):
        self.create_temp_project()

    def tearDown(self):
        self.cleanup_temp_project()

    def test_audit_function_writes_json(self):
        """Simulate the audit function from server.py."""
        import datetime
        import logging

        audit_path = Path(".ai-operation/audit.log")
        logger = logging.getLogger(f"test_audit_{id(self)}")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(str(audit_path), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        entry = {
            "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tool": "aio__force_architect_save",
            "status": "SUCCESS",
            "details": "files=activeContext.md,progress.md",
        }
        logger.info(json.dumps(entry, ensure_ascii=False))
        handler.flush()

        content = audit_path.read_text(encoding="utf-8")
        parsed = json.loads(content.strip())
        self.assertEqual(parsed["tool"], "aio__force_architect_save")
        self.assertEqual(parsed["status"], "SUCCESS")


class TestGitignoreSelfHeal(unittest.TestCase, TestSetup):
    """Fix 5: _check_and_heal_gitignore auto-removes/whitelists offending rules."""

    def setUp(self):
        self.create_temp_project()
        # Init a real git repo so `git check-ignore` works.
        import subprocess
        subprocess.run(["git", "init", "-q"], check=False,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        self.cleanup_temp_project()

    def _gi_heal(self):
        from tools.constants import _check_and_heal_gitignore
        return _check_and_heal_gitignore()

    def test_removes_precise_project_map_rule(self):
        """Precise rule '.ai-operation/docs/project_map/' -> deleted from .gitignore."""
        Path(".gitignore").write_text(
            "# user rules\nnode_modules/\n.ai-operation/docs/project_map/\nvenv/\n",
            encoding="utf-8",
        )
        actions = self._gi_heal()
        self.assertTrue(actions, "expected at least one action when project_map is ignored")
        gi = Path(".gitignore").read_text(encoding="utf-8")
        self.assertNotIn(".ai-operation/docs/project_map/", gi)
        self.assertIn("node_modules/", gi)  # preserved
        self.assertIn("venv/", gi)          # preserved

    def test_removes_precise_rule_without_trailing_slash(self):
        """Precise rule 'project_map' (no slash, no prefix) -> deleted."""
        Path(".gitignore").write_text("project_map\nfoo\n", encoding="utf-8")
        # Git may or may not match this depending on how paths resolve; only
        # assert the heal result is consistent with check-ignore's verdict.
        import subprocess
        probe = subprocess.run(
            ["git", "check-ignore", "-v", ".ai-operation/docs/project_map/activeContext.md"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        actions = self._gi_heal()
        if probe.returncode == 0:
            self.assertTrue(actions)
            gi = Path(".gitignore").read_text(encoding="utf-8")
            self.assertNotIn("project_map\n", gi.split("\nfoo")[0] + "\n")
        # else: no-op is also acceptable

    def test_broad_rule_appends_whitelist_not_removed(self):
        """Broad rule '.ai-operation/*' -> whitelist appended, original preserved."""
        Path(".gitignore").write_text(
            ".ai-operation/*\n",
            encoding="utf-8",
        )
        actions = self._gi_heal()
        self.assertTrue(actions, "broad rule should trigger whitelist append")
        gi = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn(".ai-operation/*", gi)  # preserved
        self.assertIn("!.ai-operation/docs/project_map/", gi)  # whitelist added

    def test_no_gitignore_is_noop(self):
        """No .gitignore file -> returns empty actions, no crash."""
        self.assertFalse(Path(".gitignore").exists())
        actions = self._gi_heal()
        self.assertEqual(actions, [])

    def test_not_ignored_is_noop(self):
        """.gitignore exists but does not block project_map -> empty actions."""
        Path(".gitignore").write_text("node_modules/\n", encoding="utf-8")
        actions = self._gi_heal()
        self.assertEqual(actions, [])

    def test_idempotent_on_second_call(self):
        """Running heal twice should not accumulate changes."""
        Path(".gitignore").write_text(".ai-operation/docs/project_map/\n", encoding="utf-8")
        self._gi_heal()
        first = Path(".gitignore").read_text(encoding="utf-8")
        self._gi_heal()
        second = Path(".gitignore").read_text(encoding="utf-8")
        self.assertEqual(first, second, "second heal must not re-modify .gitignore")


class TestGitCommitHardening(unittest.TestCase, TestSetup):
    """Fix 2 + Fix 6: git add -f, stderr capture, flag transaction."""

    def setUp(self):
        self.create_temp_project()

    def tearDown(self):
        self.cleanup_temp_project()

    def test_git_add_uses_force_flag(self):
        """git_commit_nonblocking must invoke `git add -f` (bypass gitignore)."""
        from tools import constants as C

        captured = {"args": None}

        class FakeProc:
            def __init__(self, *args, **kwargs):
                captured["args"] = list(args[0]) if args else None
                self.returncode = 1  # simulate add failure so we don't proceed to commit

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                pass

        with patch.object(C.subprocess, "Popen", FakeProc):
            C.git_commit_nonblocking(["foo.txt"], "test")

        args = captured["args"]
        self.assertIsNotNone(args)
        self.assertEqual(args[:3], ["git", "add", "-f"],
                         f"expected `git add -f` prefix, got {args[:3]}")

    def test_stderr_captured_on_add_failure(self):
        """Non-zero `git add` rc -> stderr text surfaced in status string + diag."""
        from tools import constants as C

        class FakeProc:
            def __init__(self, cmd, stdin=None, stdout=None, stderr=None):
                self.returncode = 1
                # Write to the tempfile passed as stderr
                if hasattr(stderr, "write"):
                    stderr.write(b"fatal: pathspec 'foo.txt' did not match any files\n")
                    stderr.flush()

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                pass

        with patch.object(C.subprocess, "Popen", FakeProc):
            status, diag = C.git_commit_nonblocking(["foo.txt"], "test")

        self.assertIn("add_stderr", diag)
        self.assertIn("fatal", diag["add_stderr"])
        self.assertIn("fatal", status)
        self.assertIn("rc=1", status)

    def test_flag_preserved_on_failure(self):
        """Fix 6: git add failure -> TASKSPEC_APPROVED_FLAG + FAST_TRACK_FLAG kept."""
        from tools import constants as C

        C.TASKSPEC_APPROVED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        C.TASKSPEC_APPROVED_FLAG.write_text("approved", encoding="utf-8")
        C.FAST_TRACK_FLAG.write_text("fast", encoding="utf-8")

        class FakeProc:
            def __init__(self, *a, **kw):
                self.returncode = 1

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                pass

        with patch.object(C.subprocess, "Popen", FakeProc):
            C.git_commit_nonblocking(["foo.txt"], "test")

        self.assertTrue(C.TASKSPEC_APPROVED_FLAG.exists(),
                        "taskspec_approved must persist when git add fails")
        self.assertTrue(C.FAST_TRACK_FLAG.exists(),
                        "fast_track must persist when git add fails")

    def test_flag_consumed_on_success(self):
        """Fix 6: commit success -> approval flags consumed (old behavior preserved)."""
        from tools import constants as C

        C.TASKSPEC_APPROVED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        C.TASKSPEC_APPROVED_FLAG.write_text("approved", encoding="utf-8")
        C.FAST_TRACK_FLAG.write_text("fast", encoding="utf-8")

        # Both add and commit succeed
        call_idx = {"n": 0}

        class FakeProc:
            def __init__(self, *a, **kw):
                call_idx["n"] += 1
                self.returncode = 0

            def wait(self, timeout=None):
                return self.returncode

            def kill(self):
                pass

        with patch.object(C.subprocess, "Popen", FakeProc):
            status, _diag = C.git_commit_nonblocking(["foo.txt"], "test")

        self.assertEqual(status, "committed")
        self.assertFalse(C.TASKSPEC_APPROVED_FLAG.exists(),
                         "taskspec_approved must be consumed on commit success")
        self.assertFalse(C.FAST_TRACK_FLAG.exists(),
                         "fast_track must be consumed on commit success")


class TestHookBlocksProjectMap(unittest.TestCase, TestSetup):
    """Fix 3: require-context.sh blocks Edit/Write targeting project_map."""

    def setUp(self):
        self.create_temp_project()
        import shutil
        hook_src = REPO_ROOT / ".claude" / "hooks" / "require-context.sh"
        # copy hook and corrections template into temp project
        dst_dir = Path(".claude/hooks")
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hook_src, dst_dir / "require-context.sh")
        # Gate must be uninitialized (no SESSION_KEY) to keep the default allow
        # path for non-project_map edits; the lockdown we test runs BEFORE the
        # session check anyway.

    def tearDown(self):
        self.cleanup_temp_project()

    def _find_bash(self):
        import shutil as _sh
        b = _sh.which("bash")
        if b:
            return b
        for cand in (r"C:\Program Files\Git\bin\bash.exe",
                     r"C:\Program Files\Git\usr\bin\bash.exe",
                     "/usr/bin/bash", "/bin/bash"):
            if Path(cand).exists():
                return cand
        return None

    def _run_hook(self, payload: dict):
        import subprocess as _sp
        bash = self._find_bash()
        if bash is None:
            self.skipTest("bash not available on this platform")
        proc = _sp.run(
            [bash, ".claude/hooks/require-context.sh"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=10,
        )
        return proc

    def test_blocks_edit_on_project_map(self):
        r = self._run_hook({
            "tool_name": "Edit",
            "tool_input": {"file_path": ".ai-operation/docs/project_map/activeContext.md"},
        })
        self.assertEqual(r.returncode, 2, f"expected exit 2, got {r.returncode} stderr={r.stderr}")
        self.assertIn("aio__force_architect_save", r.stderr)

    def test_blocks_write_on_project_map(self):
        r = self._run_hook({
            "tool_name": "Write",
            "tool_input": {"file_path": ".ai-operation/docs/project_map/systemPatterns.md"},
        })
        self.assertEqual(r.returncode, 2)

    def test_allows_edit_on_src_code(self):
        r = self._run_hook({
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/foo.py"},
        })
        self.assertEqual(r.returncode, 0, f"expected exit 0, got {r.returncode} stderr={r.stderr}")

    def test_allows_mcp_tools(self):
        r = self._run_hook({
            "tool_name": "mcp__project_architect__aio__force_architect_save",
            "tool_input": {},
        })
        self.assertEqual(r.returncode, 0)


class TestSnapshotHelpers(unittest.TestCase, TestSetup):
    """Fix C helpers: snapshot / restore / GC over project_map."""

    def setUp(self):
        self.create_temp_project()

    def tearDown(self):
        self.cleanup_temp_project()

    def test_snapshot_copies_all_project_map_md(self):
        from tools.constants import _snapshot_project_map, SAVE_HISTORY_DIR

        pm = Path(".ai-operation/docs/project_map")
        (pm / "details").mkdir(parents=True, exist_ok=True)
        (pm / "details" / "nested.md").write_text("nested content", encoding="utf-8")

        snap = _snapshot_project_map("20260420T120000")
        self.assertTrue(snap.exists())
        self.assertTrue((snap / "activeContext.md").exists())
        self.assertTrue((snap / "details" / "nested.md").exists())
        self.assertEqual(
            (snap / "details" / "nested.md").read_text(encoding="utf-8"),
            "nested content",
        )
        # Snapshot directory is under SAVE_HISTORY_DIR
        self.assertEqual(snap.parent.resolve(), SAVE_HISTORY_DIR.resolve())

    def test_restore_returns_files_and_overwrites(self):
        from tools.constants import _snapshot_project_map, _restore_from_snapshot

        pm = Path(".ai-operation/docs/project_map")
        original = "ORIGINAL\n"
        (pm / "activeContext.md").write_text(original, encoding="utf-8")
        snap = _snapshot_project_map("20260420T120001")
        # Tamper with file, then restore
        (pm / "activeContext.md").write_text("TAMPERED\n", encoding="utf-8")
        restored = _restore_from_snapshot(snap)
        self.assertIn("activeContext.md", restored)
        self.assertEqual(
            (pm / "activeContext.md").read_text(encoding="utf-8"),
            original,
        )

    def test_gc_keeps_latest_n_snapshots(self):
        from tools.constants import SAVE_HISTORY_DIR, _gc_save_history, SNAPSHOT_RETAIN_COUNT
        import time

        SAVE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        # Create 15 fake snapshots with ascending mtimes
        for i in range(15):
            d = SAVE_HISTORY_DIR / f"snap_{i:03d}"
            d.mkdir()
            (d / "mark.md").write_text(str(i), encoding="utf-8")
            # Ensure deterministic ordering by mtime
            ts = time.time() + i
            os.utime(d, (ts, ts))

        deleted = _gc_save_history(retain=SNAPSHOT_RETAIN_COUNT)  # default 10
        self.assertEqual(deleted, 5)

        remaining = sorted(d.name for d in SAVE_HISTORY_DIR.iterdir() if d.is_dir())
        self.assertEqual(len(remaining), 10)
        # The 5 oldest (snap_000..snap_004) should have been deleted
        self.assertNotIn("snap_000", remaining)
        self.assertNotIn("snap_004", remaining)
        self.assertIn("snap_014", remaining)

    def test_gc_noop_when_under_threshold(self):
        from tools.constants import SAVE_HISTORY_DIR, _gc_save_history

        SAVE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            (SAVE_HISTORY_DIR / f"snap_{i}").mkdir()
        deleted = _gc_save_history(retain=10)
        self.assertEqual(deleted, 0)
        self.assertEqual(len([d for d in SAVE_HISTORY_DIR.iterdir()]), 3)


class TestSavePhase2Guards(unittest.TestCase, TestSetup):
    """Fix A + Fix B: zero-match and no-delimiter guards in Phase 2 save."""

    def setUp(self):
        self.create_temp_project()
        # Populate corrections with a valid SESSION_KEY + approved flag so the
        # cognitive gate and taskspec gate don't interfere with these tests.
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n_none_\nSESSION_KEY: testkey\n", encoding="utf-8"
        )
        Path(".ai-operation/.session_confirmed").write_text("0", encoding="utf-8")

        # Replace systemPatterns.md with a real structured file (3 sections)
        (pm / "systemPatterns.md").write_text(
            "# System Patterns\n\n"
            "## 1. 系统定性\n原定性内容\n\n"
            "## 2. 数据流\n原数据流\n\n"
            "## 3. 架构约束\n原约束\n",
            encoding="utf-8",
        )
        # techContext also structured for the "blob on structured file" test
        (pm / "techContext.md").write_text(
            "# Tech Context\n\n"
            "## 1. 核心技术栈\nPython 3.9+\n\n"
            "## 2. 已知坑点\nN/A\n",
            encoding="utf-8",
        )

        # Register tools
        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def _valid_phase1_args(self, **overrides):
        args = dict(
            projectbrief_update="NO_CHANGE_BECAUSE: not relevant for this test",
            systemPatterns_update="NO_CHANGE_BECAUSE: not relevant for this test",
            techContext_update="NO_CHANGE_BECAUSE: not relevant for this test",
            conventions_update="NO_CHANGE_BECAUSE: not relevant for this test",
            activeContext_update=(
                "Current focus: testing Phase 2 guards in tests/test_architect_tools.py. "
                "Just completed: modified .ai-operation/mcp_server/tools/save.py to add "
                "zero-match refuse and no-delimiter refuse guards. "
                "Next step: run pytest to verify all guard paths behave correctly."
            ),
            progress_update=(
                "DONE .ai-operation/mcp_server/tools/save.py: added Phase 2 defensive guards "
                "(zero-match refuse, no-delimiter refuse, FULL_OVERWRITE_CONFIRMED escape, "
                "snapshot+restore on exception)\n"
                "DONE tests/test_architect_tools.py: added 7 new guard tests covering every path\n"
                "DONE .ai-operation/mcp_server/tools/constants.py: snapshot helpers + GC helper\n"
                "TODO: run full pytest suite; then git commit + push"
            ),
            lessons_learned="NONE",
        )
        args.update(overrides)
        return args

    def _run_both_phases(self, **overrides):
        p1 = self.tools["aio__force_architect_save"](**self._valid_phase1_args(**overrides))
        if p1.startswith("REJECTED"):
            return p1
        # Mock git operations in Phase 2
        with patch("tools.constants.subprocess") as mock_sub:
            # simulate git add + commit success
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.wait.return_value = 0
            mock_sub.Popen.return_value = mock_proc
            mock_sub.DEVNULL = -3  # doesn't matter, just needs a value
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            # subprocess.TimeoutExpired referenced — preserve real class
            import subprocess as _sp
            mock_sub.TimeoutExpired = _sp.TimeoutExpired
            p2 = self.tools["aio__force_architect_save_confirm"]()
        return p2

    def test_zero_section_match_rejected_with_diagnostic(self):
        """AI passes ===SECTION=== with wrong titles -> REJECTED, original file unchanged."""
        bad_update = (
            "===SECTION===\n不存在的小节\n"
            "文件 systemPatterns.md 的节点内容占位文字，用于通过 Phase 1 字数校验\n"
            "===SECTION===\n另一个假小节\n"
            "同样是为了通过字数校验的占位内容，涉及 .ai-operation/mcp_server/tools/save.py 的改动\n"
        )
        result = self._run_both_phases(systemPatterns_update=bad_update)

        self.assertIn("REJECTED", result)
        self.assertIn("systemPatterns.md", result)
        # Diagnostic must list actual section titles
        self.assertIn("系统定性", result)
        self.assertIn("数据流", result)
        # And echo the bad keys
        self.assertIn("不存在的小节", result)
        # Original file content preserved
        sp = Path(".ai-operation/docs/project_map/systemPatterns.md").read_text(encoding="utf-8")
        self.assertIn("原定性内容", sp)
        self.assertIn("原数据流", sp)

    def test_section_match_succeeds_with_numeric_prefix_stripped(self):
        """===SECTION===\n系统定性\n... (no '1.') matches '## 1. 系统定性'."""
        good_update = (
            "===SECTION===\n系统定性\n"
            "新定性内容，包含 .ai-operation/mcp_server/tools/save.py 的 Phase 2 guard 说明 "
            "和 constants.py 的 snapshot helper 说明，用于通过 Phase 1 字数校验\n"
        )
        result = self._run_both_phases(systemPatterns_update=good_update)

        self.assertNotIn("REJECTED", result)
        sp = Path(".ai-operation/docs/project_map/systemPatterns.md").read_text(encoding="utf-8")
        self.assertIn("新定性内容", sp)
        # Other sections preserved
        self.assertIn("原数据流", sp)
        self.assertIn("原约束", sp)

    def test_no_delimiter_on_structured_file_rejected(self):
        """Blob content (no ===SECTION===) on a file with existing sections -> REJECTED."""
        blob = (
            "just a bunch of text without any section delimiters whatsoever, "
            "long enough to clear the 100-char minimum for static file updates so "
            "that the Phase 1 validation doesn't reject this for the wrong reason."
        )
        result = self._run_both_phases(systemPatterns_update=blob)

        self.assertIn("REJECTED", result)
        self.assertIn("systemPatterns.md", result)
        self.assertIn("FULL_OVERWRITE_CONFIRMED", result)
        # Original file UNTOUCHED
        sp = Path(".ai-operation/docs/project_map/systemPatterns.md").read_text(encoding="utf-8")
        self.assertIn("原定性内容", sp)
        self.assertIn("原约束", sp)

    def test_full_overwrite_confirmed_prefix_allows_overwrite(self):
        """FULL_OVERWRITE_CONFIRMED: prefix -> full OVERWRITE, guard bypassed."""
        replacement = (
            "FULL_OVERWRITE_CONFIRMED:\n# 完全重写\n"
            "新内容无任何原有 section 结构。这是显式 opt-in 的全替换路径，"
            "用于当 AI 真的想重建整份 systemPatterns.md 时使用。"
            "涉及文件 .ai-operation/mcp_server/tools/save.py Phase 2 判定逻辑。\n"
        )
        result = self._run_both_phases(systemPatterns_update=replacement)

        self.assertNotIn("REJECTED", result)
        self.assertIn("FULL_OVERWRITE", result)
        sp = Path(".ai-operation/docs/project_map/systemPatterns.md").read_text(encoding="utf-8")
        self.assertIn("完全重写", sp)
        self.assertNotIn("原定性内容", sp)  # old content gone

    def test_bootstrap_template_file_still_accepts_blob(self):
        """File with no existing `##` sections (fresh template) -> blob OVERWRITE works."""
        # Replace systemPatterns.md with template-shape (no `##` headers)
        (Path(".ai-operation/docs/project_map/systemPatterns.md")).write_text(
            "# System Patterns\n\n[待填写]\n", encoding="utf-8"
        )
        blob = (
            "# System Patterns\n\nfilled in on first bootstrap. "
            "此文件原本是模板（无 `##` section），因此走 template-shape overwrite 路径。"
            "涉及 .ai-operation/mcp_server/tools/save.py 的 bootstrap 分支 (d)。\n"
        )
        result = self._run_both_phases(systemPatterns_update=blob)

        self.assertNotIn("REJECTED", result)
        sp = Path(".ai-operation/docs/project_map/systemPatterns.md").read_text(encoding="utf-8")
        self.assertIn("filled in on first bootstrap", sp)

    def test_phase2_exception_restores_from_snapshot(self):
        """If Phase 2 raises inside the write loop, snapshot restore kicks in."""
        from pathlib import Path as _P

        # Pre-seed contents that the test will verify are preserved
        sp_path = _P(".ai-operation/docs/project_map/systemPatterns.md")
        original = sp_path.read_text(encoding="utf-8")

        # Phase 1 first (doesn't write project_map)
        p1_args = self._valid_phase1_args(
            systemPatterns_update=(
                "===SECTION===\n系统定性\n"
                "新定性内容，用于测试 Phase 2 异常回滚。涉及 .ai-operation/mcp_server/tools/save.py "
                "的 snapshot + restore 路径，以及 constants.py 的 _snapshot_project_map helper。\n"
            )
        )
        p1 = self.tools["aio__force_architect_save"](**p1_args)
        self.assertFalse(p1.startswith("REJECTED"), f"Phase 1 unexpectedly rejected: {p1[:200]}")

        # Phase 2: patch filepath.write_text on the STATIC file to raise a
        # generic exception AFTER snapshot, simulating e.g. a disk error.
        import tools.save as save_mod
        real_write = _P.write_text

        def flaky_write(self, data, *a, **kw):
            if self.name == "systemPatterns.md":
                raise OSError("simulated disk error")
            return real_write(self, data, *a, **kw)

        with patch.object(_P, "write_text", flaky_write), \
             patch("tools.constants.subprocess") as mock_sub:
            mock_proc = MagicMock(returncode=0)
            mock_proc.wait.return_value = 0
            mock_sub.Popen.return_value = mock_proc
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            import subprocess as _sp
            mock_sub.TimeoutExpired = _sp.TimeoutExpired
            p2 = self.tools["aio__force_architect_save_confirm"]()

        self.assertIn("RESTORED", p2)
        # systemPatterns.md should be back to original (snapshot restored)
        restored_text = sp_path.read_text(encoding="utf-8")
        self.assertEqual(restored_text, original,
                         "systemPatterns.md should be restored to pre-Phase2 content")


class TestInventoryWipeGuard(unittest.TestCase, TestSetup):
    """Fix 1: inventory.md Phase 2 entry-count guard."""

    def setUp(self):
        self.create_temp_project()
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n_none_\nSESSION_KEY: testkey\n", encoding="utf-8"
        )
        Path(".ai-operation/.session_confirmed").write_text("0", encoding="utf-8")
        # Write a rich inventory (10 entries)
        (pm / "inventory.md").write_text(
            "# Project Inventory\n\n"
            + "\n".join(f"- item_{i}" for i in range(10)) + "\n",
            encoding="utf-8",
        )
        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def _valid_phase1_args(self, **overrides):
        args = dict(
            projectbrief_update="NO_CHANGE_BECAUSE: test",
            systemPatterns_update="NO_CHANGE_BECAUSE: test",
            techContext_update="NO_CHANGE_BECAUSE: test",
            conventions_update="NO_CHANGE_BECAUSE: test",
            activeContext_update=(
                "Current focus: testing inventory wipe guard in "
                "tests/test_architect_tools.py. "
                "Just completed: added entry-count guard to "
                ".ai-operation/mcp_server/tools/save.py Phase 2 inventory.md "
                "branch -- raises _SaveAbort when new_count < 50% of old_count "
                "without FULL_OVERWRITE_CONFIRMED prefix. Next step: run pytest."
            ),
            progress_update=(
                "DONE .ai-operation/mcp_server/tools/save.py: "
                "inventory wipe guard -- raises _SaveAbort when new < 50% old "
                "without FULL_OVERWRITE_CONFIRMED prefix.\n"
                "DONE tests/test_architect_tools.py: added inventory guard tests.\n"
            ),
            lessons_learned="NONE",
        )
        args.update(overrides)
        return args

    def _run_both_phases(self, **overrides):
        p1 = self.tools["aio__force_architect_save"](**self._valid_phase1_args(**overrides))
        if p1.startswith("REJECTED"):
            return p1
        with patch("tools.constants.subprocess") as mock_sub:
            mock_proc = MagicMock(returncode=0)
            mock_proc.wait.return_value = 0
            mock_sub.Popen.return_value = mock_proc
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            import subprocess as _sp
            mock_sub.TimeoutExpired = _sp.TimeoutExpired
            return self.tools["aio__force_architect_save_confirm"]()

    def test_partial_inventory_rejected(self):
        """Passing < 50% of existing entries without prefix -> REJECTED."""
        result = self._run_both_phases(inventory_update="- item_0\n- item_1\n")
        self.assertIn("REJECTED", result)
        self.assertIn("wipe guard", result)
        # Original inventory intact
        inv = Path(".ai-operation/docs/project_map/inventory.md").read_text(encoding="utf-8")
        self.assertIn("item_9", inv)

    def test_full_overwrite_confirmed_bypasses_guard(self):
        """FULL_OVERWRITE_CONFIRMED: prefix bypasses entry-count guard."""
        result = self._run_both_phases(
            inventory_update="FULL_OVERWRITE_CONFIRMED:\n- only_item\n"
        )
        self.assertNotIn("REJECTED", result)
        inv = Path(".ai-operation/docs/project_map/inventory.md").read_text(encoding="utf-8")
        self.assertIn("only_item", inv)
        self.assertNotIn("item_9", inv)

    def test_complete_inventory_passes_guard(self):
        """Passing all existing items (>= 50%) passes the guard normally."""
        full_list = "\n".join(f"- item_{i}" for i in range(10)) + "\n- item_new\n"
        result = self._run_both_phases(inventory_update=full_list)
        self.assertNotIn("REJECTED", result)
        inv = Path(".ai-operation/docs/project_map/inventory.md").read_text(encoding="utf-8")
        self.assertIn("item_new", inv)


class TestSaveCancelTool(unittest.TestCase, TestSetup):
    """Fix 2: aio__force_architect_save_cancel aborts a pending Phase 1."""

    def setUp(self):
        self.create_temp_project()
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n_none_\nSESSION_KEY: testkey\n", encoding="utf-8"
        )
        Path(".ai-operation/.session_confirmed").write_text("0", encoding="utf-8")
        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def _phase1_args(self):
        return dict(
            projectbrief_update="NO_CHANGE_BECAUSE: test",
            systemPatterns_update="NO_CHANGE_BECAUSE: test",
            techContext_update="NO_CHANGE_BECAUSE: test",
            conventions_update="NO_CHANGE_BECAUSE: test",
            activeContext_update=(
                "Current focus: testing save_cancel in tests/test_architect_tools.py. "
                "Completed: save_cancel tool added to save.py; "
                "uses clear_save_pending + SAVE_STAGING_FILE.unlink. "
                "Next step: verify cancel unblocks re-submit."
            ),
            progress_update=(
                "DONE .ai-operation/mcp_server/tools/save.py: "
                "aio__force_architect_save_cancel tool added.\n"
                "DONE tests/test_architect_tools.py: cancel tool tests added.\n"
            ),
            lessons_learned="NONE",
        )

    def test_cancel_removes_staging_and_unlocks(self):
        """After Phase 1, cancel clears staging; confirm then returns REJECTED."""
        p1 = self.tools["aio__force_architect_save"](**self._phase1_args())
        self.assertIn("PENDING_REVIEW", p1)

        cancel_result = self.tools["aio__force_architect_save_cancel"]()
        self.assertIn("SUCCESS", cancel_result)

        # Now confirm should say nothing is staged
        confirm_result = self.tools["aio__force_architect_save_confirm"]()
        self.assertIn("REJECTED", confirm_result)
        self.assertIn("aio__force_architect_save", confirm_result)

    def test_cancel_noop_when_nothing_pending(self):
        """Calling cancel with no pending save returns NOOP."""
        result = self.tools["aio__force_architect_save_cancel"]()
        self.assertIn("NOOP", result)

    def test_can_resubmit_after_cancel(self):
        """After cancel, a second Phase 1 call is accepted."""
        self.tools["aio__force_architect_save"](**self._phase1_args())
        self.tools["aio__force_architect_save_cancel"]()
        p1_again = self.tools["aio__force_architect_save"](**self._phase1_args())
        self.assertIn("PENDING_REVIEW", p1_again)
        # Cleanup pending state
        self.tools["aio__force_architect_save_cancel"]()


class TestRestoreLastTool(unittest.TestCase, TestSetup):
    """Fix 3: aio__force_architect_restore_last lists and restores snapshots."""

    def setUp(self):
        self.create_temp_project()
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n_none_\nSESSION_KEY: testkey\n", encoding="utf-8"
        )
        Path(".ai-operation/.session_confirmed").write_text("0", encoding="utf-8")
        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def _make_snapshot(self, label="20260420T000000"):
        from tools.constants import _snapshot_project_map
        return _snapshot_project_map(label)

    def test_dry_run_lists_files_without_writing(self):
        """confirm=False (default) lists snapshot files, does not write."""
        pm = Path(".ai-operation/docs/project_map")
        original = (pm / "activeContext.md").read_text(encoding="utf-8")
        self._make_snapshot()
        # Tamper with file
        (pm / "activeContext.md").write_text("TAMPERED", encoding="utf-8")

        result = self.tools["aio__force_architect_restore_last"](confirm=False)
        self.assertIn("activeContext.md", result)
        self.assertNotIn("SUCCESS", result)
        # File should still be tampered (dry run)
        self.assertEqual(
            (pm / "activeContext.md").read_text(encoding="utf-8"), "TAMPERED"
        )

    def test_confirm_true_restores_files(self):
        """confirm=True actually writes snapshot files back to project_map."""
        pm = Path(".ai-operation/docs/project_map")
        original = (pm / "activeContext.md").read_text(encoding="utf-8")
        self._make_snapshot()
        (pm / "activeContext.md").write_text("CORRUPTED", encoding="utf-8")

        result = self.tools["aio__force_architect_restore_last"](confirm=True)
        self.assertIn("SUCCESS", result)
        self.assertEqual(
            (pm / "activeContext.md").read_text(encoding="utf-8"), original
        )

    def test_no_snapshots_returns_info(self):
        """When SAVE_HISTORY_DIR is empty, returns informative message."""
        result = self.tools["aio__force_architect_restore_last"](confirm=False)
        self.assertIn("No snapshot", result)


class TestEnforceFileSizeLimit(unittest.TestCase, TestSetup):
    """Fix: _enforce_file_size_limit should do adaptive semantic splits first,
    and only fall back to newline-aligned char slice for section-less blobs."""

    def setUp(self):
        self.create_temp_project()

    def tearDown(self):
        self.cleanup_temp_project()

    def test_adaptive_split_prefers_section_boundaries(self):
        """File with many <8KB sections summing to >16KB -> adaptive split moves
        the biggest section(s) to details/ rather than char-slicing."""
        from tools.constants import _enforce_file_size_limit, PROJECT_MAP_DIR
        pm = PROJECT_MAP_DIR
        pm.mkdir(parents=True, exist_ok=True)
        fp = pm / "testfile.md"
        # Build a >16KB file with 6 sections of ~3.5KB each (none > 8KB)
        chunks = []
        chunks.append("# Test File\n\n")
        for i in range(6):
            chunks.append(f"## Section {i} \u6807\u9898\n\n")
            chunks.append(("\u4e2d\u6587\u5185\u5bb9 filler line.\n" * 150))
            chunks.append("\n")
        fp.write_text("".join(chunks), encoding="utf-8")
        assert len(fp.read_text(encoding="utf-8").encode("utf-8")) > 16_000

        result = _enforce_file_size_limit(fp)
        self.assertIn("adaptive semantic split", result)
        # File is now under limit
        self.assertLessEqual(
            len(fp.read_text(encoding="utf-8").encode("utf-8")), 16_000
        )
        # At least one details/ file was created
        details_files = list((pm / "details").glob("testfile__*.md"))
        self.assertGreater(len(details_files), 0)

    def test_last_resort_cut_aligns_to_newline(self):
        """Section-less blob file -> last-resort cut, but at newline boundary."""
        from tools.constants import _enforce_file_size_limit, PROJECT_MAP_DIR
        pm = PROJECT_MAP_DIR
        pm.mkdir(parents=True, exist_ok=True)
        fp = pm / "blob.md"
        # 20KB blob with newlines but no ## headers
        lines = []
        for i in range(400):
            # Mix Chinese + English to ensure cut doesn't split a UTF-8 char
            lines.append(f"line {i} \u4e2d\u6587\u5185\u5bb9 product_appearance_extractor value")
        fp.write_text("\n".join(lines), encoding="utf-8")
        assert len(fp.read_text(encoding="utf-8").encode("utf-8")) > 16_000

        result = _enforce_file_size_limit(fp)
        self.assertIn("last-resort char slice", result)
        summary = fp.read_text(encoding="utf-8")
        # Summary must end at a newline (before the overflow pointer block)
        summary_before_pointer = summary.split("\n\n> ->")[0]
        self.assertTrue(
            summary_before_pointer.endswith("\n") or
            "\n" in summary_before_pointer[-50:],
            "cut must align to newline, not mid-line"
        )
        # And must not end mid-word like "produc"
        last_line = summary_before_pointer.rstrip("\n").rsplit("\n", 1)[-1]
        self.assertFalse(
            last_line.endswith("produc"),
            f"cut split a word: ...{last_line[-30:]!r}"
        )

    def test_under_limit_is_noop(self):
        from tools.constants import _enforce_file_size_limit, PROJECT_MAP_DIR
        fp = PROJECT_MAP_DIR / "small.md"
        fp.write_text("tiny file", encoding="utf-8")
        self.assertEqual(_enforce_file_size_limit(fp), "")


class TestOrphanRegex(unittest.TestCase, TestSetup):
    """Fix: orphan detector regex must not match .js inside state.json,
    and must find files under .ai-operation/docs/project_map/details/."""

    def setUp(self):
        self.create_temp_project()

    def tearDown(self):
        self.cleanup_temp_project()

    def test_json_not_misparsed_as_js(self):
        import re as _re
        pattern = r'([\w./\-]+\.(?:json|yaml|py|ts|js|go|rs|sh|yml|md))(?!\w)'
        matches = _re.findall(pattern, "See state.json for config")
        self.assertIn("state.json", matches)
        self.assertNotIn("state.js", matches)

    def test_yaml_not_misparsed_as_yml(self):
        import re as _re
        pattern = r'([\w./\-]+\.(?:json|yaml|py|ts|js|go|rs|sh|yml|md))(?!\w)'
        matches = _re.findall(pattern, "See config.yaml")
        self.assertIn("config.yaml", matches)
        self.assertNotIn("config.yml", matches)

    def test_details_path_not_reported_as_orphan(self):
        """A ref like 'details/foo.md' should resolve to project_map/details/foo.md."""
        pm_root = Path(".ai-operation/docs/project_map")
        (pm_root / "details").mkdir(parents=True, exist_ok=True)
        (pm_root / "details" / "foo.md").write_text("content", encoding="utf-8")
        ref_path = "details/foo.md"
        # Mirror the fixed lookup
        exists = (
            Path(ref_path).exists()
            or Path(".ai-operation", ref_path).exists()
            or (pm_root / ref_path).exists()
        )
        self.assertTrue(exists, "details/foo.md should be found under project_map/")


class TestSaveOverflowWarning(unittest.TestCase, TestSetup):
    """Fix: Phase 1 warns when main file has a dangling overflow pointer."""

    def setUp(self):
        self.create_temp_project()
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n_none_\nSESSION_KEY: testkey\n", encoding="utf-8"
        )
        Path(".ai-operation/.session_confirmed").write_text("0", encoding="utf-8")
        # Main file with overflow pointer baked in
        (pm / "systemPatterns.md").write_text(
            "# System Patterns\n\n"
            "## 1. \u7cfb\u7edf\u5b9a\u6027\n"
            "some content\n\n"
            "> -> [\u5269\u4f59\u5185\u5bb9: details/systemPatterns__overflow_20260417_0945.md] (9364 chars)\n",
            encoding="utf-8",
        )
        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def test_phase1_warns_about_stale_overflow(self):
        p1 = self.tools["aio__force_architect_save"](
            projectbrief_update="NO_CHANGE_BECAUSE: test",
            systemPatterns_update=(
                "===SECTION===\n\u7cfb\u7edf\u5b9a\u6027\n"
                "new content referencing .ai-operation/mcp_server/tools/save.py "
                "long enough to clear the 100 char static file minimum requirement "
                "for Phase 1 validation.\n"
            ),
            techContext_update="NO_CHANGE_BECAUSE: test",
            conventions_update="NO_CHANGE_BECAUSE: test",
            activeContext_update=(
                "Current focus: testing overflow warning in "
                "tests/test_architect_tools.py. Completed: added stale-overflow "
                "detection in .ai-operation/mcp_server/tools/save.py Phase 1 "
                "diff preview. Next step: verify warning surfaces correctly."
            ),
            progress_update=(
                "DONE .ai-operation/mcp_server/tools/save.py: "
                "added overflow-pointer detection in Phase 1 warnings block.\n"
                "DONE tests/test_architect_tools.py: added overflow warning test.\n"
            ),
            lessons_learned="NONE",
        )
        self.assertIn("PENDING_REVIEW", p1)
        self.assertIn("overflow", p1.lower())
        self.assertIn("systemPatterns__overflow", p1)
        # Cleanup pending
        self.tools["aio__force_architect_save_cancel"]()


class TestExtractTaskspecFiles(unittest.TestCase, TestSetup):
    """Helper that parses taskSpec.md section 3 to return dirty code paths."""

    def setUp(self):
        self.create_temp_project()

    def tearDown(self):
        self.cleanup_temp_project()

    def _write_taskspec(self, body: str):
        from tools.constants import TASKSPEC_FILE
        TASKSPEC_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKSPEC_FILE.write_text(body, encoding="utf-8")

    def test_missing_taskspec_returns_empty(self):
        from tools.constants import _extract_taskspec_files
        self.assertEqual(_extract_taskspec_files(), [])

    def test_existing_project_paths_included(self):
        from tools.constants import _extract_taskspec_files
        Path("src").mkdir()
        Path("src/foo.py").write_text("x", encoding="utf-8")
        self._write_taskspec(
            "## 1. Task Goal\nTest\n\n"
            "## 3. Files to Modify\n- src/foo.py: edit\n\n"
            "## 4. Constraints\nnone\n"
        )
        result = _extract_taskspec_files()
        self.assertIn("src/foo.py", result)

    def test_nonexistent_paths_silently_skipped(self):
        from tools.constants import _extract_taskspec_files
        self._write_taskspec(
            "## 1. Task Goal\nTest\n\n"
            "## 3. Files to Modify\n- src/missing.py: edit\n"
        )
        self.assertEqual(_extract_taskspec_files(), [])

    def test_framework_paths_excluded(self):
        from tools.constants import _extract_taskspec_files
        # .ai-operation already exists from scaffold
        Path(".ai-operation/mcp_server").mkdir(parents=True, exist_ok=True)
        Path(".ai-operation/mcp_server/foo.py").write_text("x", encoding="utf-8")
        self._write_taskspec(
            "## 3. Files to Modify\n- .ai-operation/mcp_server/foo.py: edit\n"
        )
        self.assertEqual(_extract_taskspec_files(), [])


class TestSaveClosesTaskSpec(unittest.TestCase, TestSetup):
    """Fix: save must commit taskSpec's dirty code files atomically with memory."""

    def setUp(self):
        self.create_temp_project()
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n_none_\nSESSION_KEY: testkey\n", encoding="utf-8"
        )
        Path(".ai-operation/.session_confirmed").write_text("0", encoding="utf-8")

        # Create a fake code file the taskSpec will reference
        Path("src").mkdir()
        Path("src/foo.py").write_text("initial", encoding="utf-8")

        # Approved taskSpec that references src/foo.py
        from tools.constants import TASKSPEC_FILE, TASKSPEC_APPROVED_FLAG
        TASKSPEC_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKSPEC_FILE.write_text(
            "## 1. Task Goal\nEdit foo for testing\n\n"
            "## 3. Files to Modify\n- src/foo.py: add hello\n",
            encoding="utf-8",
        )
        TASKSPEC_APPROVED_FLAG.write_text("approved", encoding="utf-8")

        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def _args(self):
        return dict(
            projectbrief_update="NO_CHANGE_BECAUSE: test",
            systemPatterns_update="NO_CHANGE_BECAUSE: test",
            techContext_update="NO_CHANGE_BECAUSE: test",
            conventions_update="NO_CHANGE_BECAUSE: test",
            activeContext_update=(
                "Current focus: testing save-closes-taskSpec in "
                "tests/test_architect_tools.py. Just completed: added "
                "_extract_taskspec_files and _git_dirty_files to "
                ".ai-operation/mcp_server/tools/constants.py; wired them into "
                "save.py Phase 2 git block. Next step: verify behavior."
            ),
            progress_update=(
                "DONE .ai-operation/mcp_server/tools/constants.py: added "
                "_extract_taskspec_files + _git_dirty_files helpers.\n"
                "DONE .ai-operation/mcp_server/tools/save.py: include dirty "
                "taskSpec code files in Phase 2 commit.\n"
            ),
            lessons_learned="NONE",
        )

    def _run_both_phases(self, dirty_files_override=None, **overrides):
        """Run Phase 1 + Phase 2, mocking subprocess. Returns (result, captured_add_args)."""
        args = self._args()
        args.update(overrides)
        p1 = self.tools["aio__force_architect_save"](**args)
        if p1.startswith("REJECTED"):
            return p1, None

        captured = {"add_args": None}

        with patch("tools.constants.subprocess") as mock_sub:
            # git status --porcelain: return our override, or default to dirty src/foo.py
            if dirty_files_override is None:
                porcelain = " M src/foo.py\n"
            else:
                porcelain = dirty_files_override

            # Popen needs to behave differently per call (status / add / commit)
            call_counter = {"n": 0}

            def popen_side_effect(cmd, **kw):
                proc = MagicMock()
                proc.returncode = 0
                proc.wait.return_value = 0
                # If this is the git status call, write porcelain to stdout tempfile
                if "status" in cmd:
                    out_f = kw.get("stdout")
                    if out_f is not None and hasattr(out_f, "write"):
                        out_f.write(porcelain.encode("utf-8"))
                elif "add" in cmd:
                    captured["add_args"] = list(cmd)
                return proc

            mock_sub.Popen.side_effect = popen_side_effect
            mock_sub.DEVNULL = -3
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            import subprocess as _sp
            mock_sub.TimeoutExpired = _sp.TimeoutExpired

            result = self.tools["aio__force_architect_save_confirm"]()

        return result, captured["add_args"]

    def test_dirty_taskspec_code_included_in_commit(self):
        result, add_args = self._run_both_phases()
        self.assertIn("SUCCESS", result)
        self.assertIn("src/foo.py", result)
        self.assertIn("Closed taskSpec", result)
        # The git add invocation must include src/foo.py
        self.assertIsNotNone(add_args)
        self.assertIn("src/foo.py", add_args)

    def test_approval_flag_cleared_after_combined_commit(self):
        from tools.constants import TASKSPEC_APPROVED_FLAG
        self.assertTrue(TASKSPEC_APPROVED_FLAG.exists())
        self._run_both_phases()
        self.assertFalse(
            TASKSPEC_APPROVED_FLAG.exists(),
            "approval flag should be cleared after successful combined commit",
        )

    def test_no_taskspec_falls_back_to_memory_only(self):
        from tools.constants import TASKSPEC_FILE, TASKSPEC_APPROVED_FLAG
        TASKSPEC_FILE.unlink()
        TASKSPEC_APPROVED_FLAG.unlink()
        # With no taskSpec, porcelain call shouldn't happen; add_args only has memory files.
        result, add_args = self._run_both_phases(dirty_files_override="")
        self.assertIn("SUCCESS", result)
        self.assertNotIn("Closed taskSpec", result)
        self.assertIsNotNone(add_args)
        self.assertNotIn("src/foo.py", add_args)

    def test_missing_paths_silently_skipped(self):
        # Rewrite taskSpec to reference a nonexistent file
        from tools.constants import TASKSPEC_FILE
        TASKSPEC_FILE.write_text(
            "## 1. Task Goal\nTest\n\n"
            "## 3. Files to Modify\n- src/does_not_exist.py: edit\n",
            encoding="utf-8",
        )
        result, add_args = self._run_both_phases(dirty_files_override="")
        self.assertIn("SUCCESS", result)
        self.assertNotIn("Closed taskSpec", result)
        # Save still succeeds with just memory files
        self.assertIsNotNone(add_args)


class TestCognitiveGateKeyParsing(unittest.TestCase, TestSetup):
    """Fix 4: aio__confirm_read only treats slug-shaped lines as keys."""

    def setUp(self):
        self.create_temp_project()
        # Write corrections.md with a mix of real keys and sentence bullets
        pm = Path(".ai-operation/docs/project_map")
        (pm / "corrections.md").write_text(
            "# Corrections\n\n"
            "- fileops\n"
            "- git\n"
            "- Blast radius / impact analysis\n"
            "- This is a full sentence that should NOT be a key\n"
            "- valid_key\n"
            "\nSESSION_KEY: slugtest\n",
            encoding="utf-8",
        )
        self.mcp = MagicMock()
        self.tools = {}

        def capture_tool():
            def decorator(fn):
                self.tools[fn.__name__] = fn
                return fn
            return decorator

        self.mcp.tool = capture_tool
        from tools.architect import register_architect_tools
        register_architect_tools(self.mcp)

    def tearDown(self):
        self.cleanup_temp_project()

    def test_slug_lines_are_parsed_as_keys(self):
        """Lines like '- fileops' and '- valid_key' appear in the key list."""
        result = self.tools["aio__confirm_read"](session_key="slugtest")
        self.assertIn("SUCCESS", result)
        self.assertIn("fileops", result)
        self.assertIn("valid_key", result)

    def test_sentence_bullets_not_parsed_as_keys(self):
        """Full-sentence bullets like '- Blast radius / impact analysis' are skipped."""
        result = self.tools["aio__confirm_read"](session_key="slugtest")
        self.assertIn("SUCCESS", result)
        # These should NOT appear as keys in the output
        self.assertNotIn("Blast radius", result)
        self.assertNotIn("full sentence", result)

    def test_no_false_no_file_entries_for_sentences(self):
        """Sentence bullets don't produce spurious '(no file)' entries."""
        result = self.tools["aio__confirm_read"](session_key="slugtest")
        # Count '(no file)' entries -- should only be for real keys without files
        # 'fileops', 'git', 'valid_key' have no .md files in temp dir
        lines_with_no_file = [l for l in result.split("\n") if "(no file)" in l]
        # Sentence bullets must not generate entries -- so at most 3 (fileops, git, valid_key)
        self.assertLessEqual(len(lines_with_no_file), 3)


if __name__ == "__main__":
    unittest.main()
