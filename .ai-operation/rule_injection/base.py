"""
Adapter base contract.
======================

Every editor adapter (Claude Code, Cursor, Windsurf, ...) must implement
the three actions below. The shell talks to adapters only through this
contract -- adding a new editor = adding a new adapter file, not changing
the shell.
"""

from abc import ABC, abstractmethod
from pathlib import Path


# Marker stamped into editor config so install/uninstall can identify
# AI-Operation-managed entries vs user-customized entries.
INJECTION_MARKER = "AI_OPERATION_RULE_INJECTION"


class AdapterError(Exception):
    """Adapter operation failed in a way the user should see."""


class EditorAdapter(ABC):
    """Contract every editor adapter must satisfy."""

    name: str = ""  # short id, e.g. "claude_code"

    @abstractmethod
    def install(self, dry_run: bool = False) -> dict:
        """Wire the rule injection hook into this editor's user-level config.

        Returns a dict with keys:
          - status: "installed" | "already_installed" | "would_install" (dry-run)
          - config_path: path to the editor config that was touched
          - marker: INJECTION_MARKER (for verification)
        Raises AdapterError on unrecoverable failure.
        """

    @abstractmethod
    def uninstall(self, dry_run: bool = False) -> dict:
        """Reverse install: remove the injection hook entry from editor config.

        Returns dict with keys:
          - status: "uninstalled" | "not_installed" | "would_uninstall"
          - config_path: path to the editor config that was touched
        """

    @abstractmethod
    def inject(self) -> str:
        """Build and return the rule paper text to inject.

        This is what the editor's hook script ultimately calls. The returned
        string is what gets glued onto the user's prompt before the AI sees it.
        """

    @abstractmethod
    def status(self) -> dict:
        """Self-check: report whether the adapter is currently installed and
        whether the rule paper can be assembled.

        Returns dict with keys:
          - installed: bool
          - config_path: path to editor config
          - paper_preview: first ~200 chars of the assembled paper, or None
          - issues: list of human-readable problems (empty if healthy)
        """
