"""
Windsurf adapter — placeholder.

Same shape as the Cursor placeholder: shell + engine work, only the
editor-specific install/uninstall hook awaits implementation.
"""

from ..base import EditorAdapter, AdapterError, INJECTION_MARKER
from ..engine import build_paper, list_rules


class WindsurfAdapter(EditorAdapter):
    name = "windsurf"

    def install(self, dry_run: bool = False) -> dict:
        raise AdapterError(
            "Windsurf adapter is not yet implemented. The injection shell "
            "is ready -- only the editor-specific install hook is missing. "
            "Stay tuned or contribute the install/uninstall pair."
        )

    def uninstall(self, dry_run: bool = False) -> dict:
        return {
            "status": "not_installed",
            "config_path": "(windsurf adapter pending implementation)",
        }

    def inject(self) -> str:
        return build_paper()

    def status(self) -> dict:
        return {
            "installed": False,
            "config_path": "(pending implementation)",
            "version": None,
            "paper_preview": None,
            "rule_count": len(list_rules()),
            "issues": [
                "Windsurf adapter pending: install hook not yet wired.",
            ],
        }
