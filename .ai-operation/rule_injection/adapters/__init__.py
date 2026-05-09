"""
Editor adapters for rule injection.

Each editor has its own adapter (claude_code, cursor, windsurf). They all
implement the EditorAdapter contract from `..base`. The shell selects an
adapter by name; adding a new editor = new file here, no shell changes.
"""

from .claude_code import ClaudeCodeAdapter
from .cursor import CursorAdapter
from .windsurf import WindsurfAdapter

REGISTRY = {
    "claude_code": ClaudeCodeAdapter,
    "cursor": CursorAdapter,
    "windsurf": WindsurfAdapter,
}


def get_adapter(name: str):
    """Look up an adapter class by name. Raises KeyError if unknown."""
    if name not in REGISTRY:
        raise KeyError(
            f"Unknown editor adapter: {name!r}. "
            f"Known: {sorted(REGISTRY.keys())}"
        )
    return REGISTRY[name]()


__all__ = ["REGISTRY", "get_adapter", "ClaudeCodeAdapter",
           "CursorAdapter", "WindsurfAdapter"]
