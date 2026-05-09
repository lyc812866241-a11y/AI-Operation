"""
Claude Code adapter — installs a UserPromptSubmit hook into ~/.claude/settings.json.

When the user submits a prompt, Claude Code runs the hook. The hook script
spawns the framework's `cli inject claude_code` command, which prints the
rule paper to stdout. Claude Code then injects that stdout content as
"additionalContext" in front of the user's prompt before sending it to the AI.

The hook entry is identified by a marker so install/uninstall can find
exactly the framework-managed entry without touching user customizations.
"""

import json
import os
import sys
from pathlib import Path

from ..base import EditorAdapter, AdapterError, INJECTION_MARKER
from ..engine import build_paper, list_rules, PAPER_FORMAT_VERSION


def _user_claude_settings_path() -> Path:
    """Where Claude Code reads user-level settings (cross-platform).

    Default: ~/.claude/settings.json.
    Allow override via $CLAUDE_CODE_SETTINGS for testing.
    """
    override = os.environ.get("CLAUDE_CODE_SETTINGS")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "settings.json"


def _hook_command_for_this_install() -> str:
    """The shell command Claude Code will run on UserPromptSubmit.

    We invoke cli.py by absolute path. This avoids PYTHONPATH/cwd wrestling
    across editor host environments. cli.py self-bootstraps sys.path to
    find the rule_injection package.

    Quoting strategy: wrap both python and script in double quotes so paths
    with spaces (e.g. C:\\Users\\My Name\\...) survive the shell parser.
    """
    cli_script = Path(__file__).resolve().parent.parent / "cli.py"
    python_exe = sys.executable
    return f'"{python_exe}" "{cli_script}" inject claude_code'


def _framework_pythonpath() -> str:
    """Path to .ai-operation/ for the marker (audit trail / version check)."""
    return str(Path(__file__).resolve().parents[2])  # .ai-operation/


class ClaudeCodeAdapter(EditorAdapter):
    name = "claude_code"

    # ---- helpers --------------------------------------------------------

    def _load_settings(self, path: Path) -> dict:
        """Read settings.json or return empty dict if missing."""
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise AdapterError(
                f"Cannot parse Claude settings at {path}: {e}"
            ) from e

    def _save_settings(self, path: Path, data: dict) -> None:
        """Write settings.json (creates parent dir if missing)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _find_our_hook_entry(self, settings: dict) -> tuple:
        """Locate the AI-Operation-managed hook entry.

        Returns (hooks_list, entry_index) or (None, None) if not found.
        Claude Code hook layout (verified shape):
            { "hooks": { "UserPromptSubmit": [
                { "matcher": "...", "hooks": [
                    { "type": "command", "command": "..." }
                ]}
            ]}}
        Our entries carry our marker in the matcher field.
        """
        hooks_root = settings.get("hooks", {})
        ups_list = hooks_root.get("UserPromptSubmit", [])
        if not isinstance(ups_list, list):
            return None, None
        for i, entry in enumerate(ups_list):
            if not isinstance(entry, dict):
                continue
            if entry.get("matcher") == INJECTION_MARKER:
                return ups_list, i
        return None, None

    def _build_hook_entry(self) -> dict:
        """The settings.json fragment we inject."""
        return {
            "matcher": INJECTION_MARKER,
            "_aio_version": PAPER_FORMAT_VERSION,
            "_aio_pythonpath": _framework_pythonpath(),
            "hooks": [
                {
                    "type": "command",
                    "command": _hook_command_for_this_install(),
                    "timeout": 10,
                }
            ],
        }

    # ---- contract methods -----------------------------------------------

    def install(self, dry_run: bool = False) -> dict:
        path = _user_claude_settings_path()
        settings = self._load_settings(path)

        hooks_list, idx = self._find_our_hook_entry(settings)

        # Already installed -- check version, decide whether to refresh
        if hooks_list is not None and idx is not None:
            existing = hooks_list[idx]
            existing_ver = existing.get("_aio_version")
            if existing_ver == PAPER_FORMAT_VERSION and not dry_run:
                return {
                    "status": "already_installed",
                    "config_path": str(path),
                    "marker": INJECTION_MARKER,
                    "version": existing_ver,
                }
            if dry_run:
                return {
                    "status": "would_install",
                    "config_path": str(path),
                    "marker": INJECTION_MARKER,
                    "note": "would refresh existing entry"
                            if existing_ver != PAPER_FORMAT_VERSION
                            else "already at current version",
                }
            # Different version -- refresh
            hooks_list[idx] = self._build_hook_entry()
            self._save_settings(path, settings)
            return {
                "status": "installed",
                "config_path": str(path),
                "marker": INJECTION_MARKER,
                "version": PAPER_FORMAT_VERSION,
                "note": f"refreshed from version {existing_ver}",
            }

        # Fresh install
        if dry_run:
            return {
                "status": "would_install",
                "config_path": str(path),
                "marker": INJECTION_MARKER,
                "note": "fresh install",
            }

        hooks_root = settings.setdefault("hooks", {})
        ups_list = hooks_root.setdefault("UserPromptSubmit", [])
        if not isinstance(ups_list, list):
            raise AdapterError(
                f"Existing hooks.UserPromptSubmit is not a list at {path}"
            )
        ups_list.append(self._build_hook_entry())
        self._save_settings(path, settings)
        return {
            "status": "installed",
            "config_path": str(path),
            "marker": INJECTION_MARKER,
            "version": PAPER_FORMAT_VERSION,
            "note": "fresh install",
        }

    def uninstall(self, dry_run: bool = False) -> dict:
        path = _user_claude_settings_path()
        settings = self._load_settings(path)
        hooks_list, idx = self._find_our_hook_entry(settings)

        if hooks_list is None or idx is None:
            return {
                "status": "not_installed",
                "config_path": str(path),
            }

        if dry_run:
            return {
                "status": "would_uninstall",
                "config_path": str(path),
            }

        del hooks_list[idx]
        # Tidy up empty containers
        if not hooks_list:
            settings.get("hooks", {}).pop("UserPromptSubmit", None)
        if not settings.get("hooks"):
            settings.pop("hooks", None)
        self._save_settings(path, settings)
        return {
            "status": "uninstalled",
            "config_path": str(path),
        }

    def inject(self) -> str:
        """Build the rule paper. Called by the hook command at every user
        prompt. Returns the paper as a string (printed to stdout by the CLI).
        """
        return build_paper()

    def status(self) -> dict:
        path = _user_claude_settings_path()
        issues = []
        installed = False
        version = None
        try:
            settings = self._load_settings(path)
            hooks_list, idx = self._find_our_hook_entry(settings)
            if hooks_list is not None and idx is not None:
                installed = True
                version = hooks_list[idx].get("_aio_version")
        except AdapterError as e:
            issues.append(str(e))

        rules = list_rules()
        paper = build_paper() if rules or installed else None
        if not rules:
            issues.append(
                "No rules found in container; injection will produce an "
                "empty paper. Add rule files under rule_injection/container/."
            )

        return {
            "installed": installed,
            "config_path": str(path),
            "version": version,
            "paper_preview": (paper[:200] + "...")
                             if paper and len(paper) > 200 else paper,
            "rule_count": len(rules),
            "issues": issues,
        }
