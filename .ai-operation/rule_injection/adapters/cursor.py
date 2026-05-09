"""
Cursor adapter — placeholder.

Proves the shell can host multiple editor adapters with a single contract.
The inject() method works (shares the engine with Claude Code), so once
Cursor's hook mechanism is wired in install(), this adapter becomes live.

Contributing notes for whoever implements this:
  - Cursor's prompt-time hook mechanism (TBD as of writing) lives in user
    settings, similar to Claude's ~/.claude/settings.json.
  - Reuse engine.build_paper() so the same rules apply across editors.
  - Stamp INJECTION_MARKER into Cursor's config so install/uninstall can
    identify framework-managed entries (议题 #016 audit-friendly).
"""

from ..base import EditorAdapter, AdapterError, INJECTION_MARKER
from ..engine import build_paper, list_rules


class CursorAdapter(EditorAdapter):
    name = "cursor"

    def install(self, dry_run: bool = False) -> dict:
        raise AdapterError(
            "Cursor adapter is not yet implemented. The injection shell is "
            "ready -- only the editor-specific install hook is missing. "
            "Stay tuned or contribute the install/uninstall pair."
        )

    def uninstall(self, dry_run: bool = False) -> dict:
        # Uninstall on a never-installed adapter is a no-op success
        return {
            "status": "not_installed",
            "config_path": "(cursor adapter pending implementation)",
        }

    def inject(self) -> str:
        # Engine works editor-agnostically -- the paper is the same.
        return build_paper()

    def status(self) -> dict:
        return {
            "installed": False,
            "config_path": "(pending implementation)",
            "version": None,
            "paper_preview": None,
            "rule_count": len(list_rules()),
            "issues": [
                "Cursor adapter pending: install hook not yet wired.",
            ],
        }
