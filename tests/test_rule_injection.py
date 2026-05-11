"""
Tests for AI-Operation Framework — Rule Injection Pipeline (议题 #014 v3.5)
============================================================================
Tests:
  - Engine: rule listing, paper assembly, framing block invariants
  - Adapter contract: every registered adapter implements the four methods
  - Claude Code adapter: install/uninstall idempotence, marker isolation,
    config preservation, version refresh, status reporting
  - Stub adapters (Cursor/Windsurf): install raises, inject still works,
    proving the shell hosts multiple editors via one contract

Run: python -m pytest tests/test_rule_injection.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add framework dir to sys.path so `import rule_injection` works
REPO_ROOT = Path(__file__).parent.parent
FRAMEWORK_DIR = REPO_ROOT / ".ai-operation"
sys.path.insert(0, str(FRAMEWORK_DIR))

from rule_injection.base import (  # noqa: E402
    EditorAdapter, AdapterError, INJECTION_MARKER,
)
from rule_injection.engine import (  # noqa: E402
    build_paper, list_rules, RULE_CONTAINER_DIR, PAPER_FORMAT_VERSION,
)
from rule_injection.adapters import (  # noqa: E402
    REGISTRY, get_adapter,
)
from rule_injection.adapters.claude_code import ClaudeCodeAdapter  # noqa: E402
from rule_injection.adapters.cursor import CursorAdapter  # noqa: E402
from rule_injection.adapters.windsurf import WindsurfAdapter  # noqa: E402


# ============================================================
# Engine tests
# ============================================================

class TestEngine(unittest.TestCase):
    """Rule container loading + paper assembly."""

    def test_list_rules_returns_md_files(self):
        rules = list_rules()
        # We shipped at least one rule
        self.assertGreaterEqual(len(rules), 1)
        for r in rules:
            self.assertTrue(r.suffix == ".md", f"non-md file in container: {r}")
            self.assertFalse(r.name.startswith("."),
                             f"hidden file leaked into container: {r}")

    def test_paper_has_framing_block(self):
        paper = build_paper()
        self.assertIn("AI-Operation Rule Injection", paper)
        self.assertIn(f"v{PAPER_FORMAT_VERSION}", paper)
        self.assertIn("End AI-Operation Rule Injection", paper)

    def test_paper_includes_each_rule_by_id(self):
        paper = build_paper()
        for rule_file in list_rules():
            self.assertIn(f"### Rule: {rule_file.stem}", paper)

    def test_paper_is_deterministic(self):
        """Two calls give the same paper (no time-based or random content)."""
        self.assertEqual(build_paper(), build_paper())


# ============================================================
# Adapter contract tests (议题 #003 multi-editor shell proof)
# ============================================================

class TestAdapterContract(unittest.TestCase):
    """Every registered adapter satisfies the same contract."""

    def test_registry_lists_all_three(self):
        self.assertIn("claude_code", REGISTRY)
        self.assertIn("cursor", REGISTRY)
        self.assertIn("windsurf", REGISTRY)

    def test_get_adapter_returns_instance(self):
        for name in REGISTRY:
            ad = get_adapter(name)
            self.assertIsInstance(ad, EditorAdapter)
            self.assertEqual(ad.name, name)

    def test_get_adapter_raises_on_unknown(self):
        with self.assertRaises(KeyError):
            get_adapter("not_an_editor")

    def test_inject_works_on_every_adapter(self):
        """Even stub adapters share the engine -- inject() returns the paper."""
        for name in REGISTRY:
            ad = get_adapter(name)
            paper = ad.inject()
            self.assertIn("AI-Operation Rule Injection", paper)


# ============================================================
# Claude Code adapter tests (with mock settings file)
# ============================================================

class TestNoBomOnWrite(unittest.TestCase):
    """议题 #021: framework writes must NEVER emit a UTF-8 BOM.

    Why: PowerShell 5.1's default `Set-Content -Encoding UTF8` adds a BOM,
    which strict JSON parsers in MCP hosts reject; on Chinese paths it
    also unmasks code-page mangling. Our Python adapters write via
    pathlib `write_text(..., encoding='utf-8')` which is BOM-free, but
    test it explicitly so a future regression (e.g. someone passing
    `encoding='utf-8-sig'`) gets caught immediately.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aio_bom_test_")
        self.mock_settings = Path(self.tmpdir) / "settings.json"
        self._old_env = os.environ.get("CLAUDE_CODE_SETTINGS")
        os.environ["CLAUDE_CODE_SETTINGS"] = str(self.mock_settings)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        if self._old_env is not None:
            os.environ["CLAUDE_CODE_SETTINGS"] = self._old_env
        else:
            os.environ.pop("CLAUDE_CODE_SETTINGS", None)

    @staticmethod
    def _has_bom(path):
        b = Path(path).read_bytes()
        return len(b) >= 3 and b[0] == 0xEF and b[1] == 0xBB and b[2] == 0xBF

    def test_claude_adapter_install_writes_no_bom(self):
        from rule_injection.adapters.claude_code import ClaudeCodeAdapter
        ClaudeCodeAdapter().install()
        self.assertTrue(self.mock_settings.exists())
        self.assertFalse(
            self._has_bom(self.mock_settings),
            f"settings.json written with BOM -- 议题 #021 regression"
        )

    def test_claude_adapter_install_chinese_path_writes_no_bom(self):
        """Same check but with Chinese characters in the parent dir name."""
        import shutil
        chinese_dir = Path(self.tmpdir) / "测试目录"
        chinese_dir.mkdir()
        chinese_settings = chinese_dir / "settings.json"
        os.environ["CLAUDE_CODE_SETTINGS"] = str(chinese_settings)
        try:
            from rule_injection.adapters.claude_code import ClaudeCodeAdapter
            ClaudeCodeAdapter().install()
            self.assertTrue(chinese_settings.exists())
            self.assertFalse(
                self._has_bom(chinese_settings),
                f"settings.json under Chinese path written with BOM -- 议题 #021 regression"
            )
            # Verify the JSON is also re-parseable (no encoding mangling)
            data = json.loads(chinese_settings.read_text(encoding="utf-8"))
            self.assertIn("hooks", data)
        finally:
            os.environ["CLAUDE_CODE_SETTINGS"] = str(self.mock_settings)
            shutil.rmtree(chinese_dir, ignore_errors=True)

    def test_propose_flag_file_writes_no_bom(self):
        """taskspec_proposed flag is JSON and gets read by submit gate."""
        from tools.constants import TASKSPEC_PROPOSED_FLAG
        # Simulate a propose-flag write (mimicking workflow.py's path).
        proj = Path(self.tmpdir) / "proj"
        proj.mkdir()
        flag_dir = proj / ".ai-operation"
        flag_dir.mkdir()
        flag = flag_dir / ".taskspec_proposed"
        flag.write_text(
            json.dumps({"x": "测试中文", "proposal_ids": ["A", "B"]}, ensure_ascii=False),
            encoding="utf-8"
        )
        self.assertFalse(
            self._has_bom(flag),
            "propose flag emitted with BOM -- 议题 #021 regression"
        )

    def test_taskspec_md_writes_no_bom(self):
        """taskSpec.md gets written by submit and consumed by the hook gate."""
        proj = Path(self.tmpdir) / "proj2"
        proj.mkdir()
        spec_dir = proj / ".ai-operation" / "docs"
        spec_dir.mkdir(parents=True)
        spec = spec_dir / "taskSpec.md"
        spec.write_text("# Task Specification\n\n## 1. 目标\n测试中文\n",
                        encoding="utf-8")
        self.assertFalse(
            self._has_bom(spec),
            "taskSpec.md emitted with BOM -- 议题 #021 regression"
        )


class TestClaudeCodeAdapter(unittest.TestCase):
    """install/uninstall lifecycle against an isolated mock settings.json."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="aio_ri_test_")
        self.mock_settings = Path(self.tmpdir) / "settings.json"
        self._old_env = os.environ.get("CLAUDE_CODE_SETTINGS")
        os.environ["CLAUDE_CODE_SETTINGS"] = str(self.mock_settings)
        self.adapter = ClaudeCodeAdapter()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        if self._old_env is not None:
            os.environ["CLAUDE_CODE_SETTINGS"] = self._old_env
        else:
            os.environ.pop("CLAUDE_CODE_SETTINGS", None)

    def test_fresh_install_creates_settings(self):
        result = self.adapter.install()
        self.assertEqual(result["status"], "installed")
        self.assertTrue(self.mock_settings.exists())
        data = json.loads(self.mock_settings.read_text(encoding="utf-8"))
        self.assertIn("hooks", data)
        self.assertIn("UserPromptSubmit", data["hooks"])
        self.assertEqual(len(data["hooks"]["UserPromptSubmit"]), 1)
        entry = data["hooks"]["UserPromptSubmit"][0]
        self.assertEqual(entry["matcher"], INJECTION_MARKER)
        self.assertEqual(entry["_aio_version"], PAPER_FORMAT_VERSION)

    def test_install_is_idempotent_at_same_version(self):
        self.adapter.install()
        result2 = self.adapter.install()
        self.assertEqual(result2["status"], "already_installed")
        # Still exactly one entry (no duplicates)
        data = json.loads(self.mock_settings.read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["UserPromptSubmit"]), 1)

    def test_install_refreshes_old_version(self):
        # Pre-seed with an old version
        self.mock_settings.write_text(json.dumps({
            "hooks": {"UserPromptSubmit": [{
                "matcher": INJECTION_MARKER,
                "_aio_version": "0.0",
                "hooks": [{"type": "command", "command": "old"}],
            }]}
        }), encoding="utf-8")
        result = self.adapter.install()
        self.assertEqual(result["status"], "installed")
        self.assertIn("refreshed", result.get("note", ""))
        data = json.loads(self.mock_settings.read_text(encoding="utf-8"))
        entry = data["hooks"]["UserPromptSubmit"][0]
        self.assertEqual(entry["_aio_version"], PAPER_FORMAT_VERSION)

    def test_install_preserves_other_user_hooks(self):
        """Don't trample user's own UserPromptSubmit entries."""
        user_entry = {
            "matcher": "user_custom_thing",
            "hooks": [{"type": "command", "command": "echo user"}],
        }
        self.mock_settings.write_text(json.dumps({
            "hooks": {"UserPromptSubmit": [user_entry]}
        }), encoding="utf-8")
        self.adapter.install()
        data = json.loads(self.mock_settings.read_text(encoding="utf-8"))
        entries = data["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(entries), 2)
        # User entry unchanged at index 0
        self.assertEqual(entries[0]["matcher"], "user_custom_thing")
        self.assertEqual(entries[0]["hooks"][0]["command"], "echo user")

    def test_uninstall_removes_only_our_entry(self):
        """Uninstall touches our marker, leaves user entries alone."""
        user_entry = {
            "matcher": "user_custom",
            "hooks": [{"type": "command", "command": "echo user"}],
        }
        self.mock_settings.write_text(json.dumps({
            "hooks": {"UserPromptSubmit": [user_entry]}
        }), encoding="utf-8")
        self.adapter.install()
        self.adapter.uninstall()
        data = json.loads(self.mock_settings.read_text(encoding="utf-8"))
        # User entry survives, our entry gone
        entries = data["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "user_custom")

    def test_uninstall_when_not_installed(self):
        result = self.adapter.uninstall()
        self.assertEqual(result["status"], "not_installed")

    def test_full_uninstall_cleans_empty_containers(self):
        """If we were the only entry, the empty hooks dict gets cleaned up."""
        self.adapter.install()
        self.adapter.uninstall()
        data = json.loads(self.mock_settings.read_text(encoding="utf-8"))
        # No empty hooks/UserPromptSubmit left behind
        self.assertNotIn("hooks", data)

    def test_dry_run_install_does_not_write(self):
        result = self.adapter.install(dry_run=True)
        self.assertEqual(result["status"], "would_install")
        self.assertFalse(self.mock_settings.exists())

    def test_status_reports_installed(self):
        self.adapter.install()
        s = self.adapter.status()
        self.assertTrue(s["installed"])
        self.assertEqual(s["version"], PAPER_FORMAT_VERSION)
        self.assertEqual(s["issues"], [])
        self.assertGreater(s["rule_count"], 0)
        self.assertIsNotNone(s["paper_preview"])

    def test_status_reports_not_installed(self):
        s = self.adapter.status()
        self.assertFalse(s["installed"])

    def test_inject_returns_paper(self):
        paper = self.adapter.inject()
        self.assertIn("AI-Operation Rule Injection", paper)
        # First rule body should be embedded
        rules = list_rules()
        if rules:
            self.assertIn(f"### Rule: {rules[0].stem}", paper)


# ============================================================
# Stub adapter tests (multi-editor shell proof)
# ============================================================

class TestStubAdapters(unittest.TestCase):
    """Cursor/Windsurf placeholders prove the shell is editor-agnostic."""

    def test_cursor_install_raises(self):
        adapter = CursorAdapter()
        with self.assertRaises(AdapterError) as ctx:
            adapter.install()
        self.assertIn("not yet implemented", str(ctx.exception))

    def test_windsurf_install_raises(self):
        adapter = WindsurfAdapter()
        with self.assertRaises(AdapterError) as ctx:
            adapter.install()
        self.assertIn("not yet implemented", str(ctx.exception))

    def test_stub_inject_still_works(self):
        """Even though install isn't implemented, inject shares the engine."""
        for adapter in (CursorAdapter(), WindsurfAdapter()):
            paper = adapter.inject()
            self.assertIn("AI-Operation Rule Injection", paper)

    def test_stub_uninstall_idempotent(self):
        for adapter in (CursorAdapter(), WindsurfAdapter()):
            result = adapter.uninstall()
            self.assertEqual(result["status"], "not_installed")

    def test_stub_status_flags_pending(self):
        for adapter in (CursorAdapter(), WindsurfAdapter()):
            s = adapter.status()
            self.assertFalse(s["installed"])
            self.assertTrue(any("pending" in i for i in s["issues"]))


if __name__ == "__main__":
    unittest.main()
