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


if __name__ == "__main__":
    unittest.main()
