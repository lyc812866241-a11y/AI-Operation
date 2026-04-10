"""
Cognitive Gate — forces AI to read project context before any file operation.

Contains: aio__confirm_read, aio__load_experience

Key-Value File Pattern:
  corrections.md = keys only (fileops, git, save, analysis...)
  corrections/*.md = values (actual experience details)
  AI sees keys on boot, loads values on demand via aio__load_experience.
  This minimizes context consumption while ensuring relevant experience
  is loaded precisely when needed.

Flow:
  1. [存档] writes a random SESSION_KEY to corrections.md
  2. New session: AI reads corrections.md, sees keys + SESSION_KEY
  3. AI calls aio__confirm_read(session_key=xxx)
  4. Tool verifies key matches → writes .session_confirmed (with counter=0)
  5. AI about to do file ops → calls aio__load_experience(key="fileops")
  6. Tool returns experience content from corrections/fileops.md
  7. Hook checks .session_confirmed exists + counter < 30 → allows tool use
"""

from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


SESSION_CONFIRMED_FLAG = Path(".ai-operation/.session_confirmed")


def register_cognitive_gate_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register cognitive gate tools."""

    @mcp.tool()
    def aio__confirm_read(session_key: str) -> str:
        """
        [COGNITIVE GATE] Confirm that you have read corrections.md and conventions.md.

        You MUST call this tool at the start of every session, BEFORE making any
        file changes. Without this, all Edit/Write/Bash tools will be BLOCKED.

        How to get the session_key:
        1. Read .ai-operation/docs/project_map/corrections.md
        2. Find the SESSION_KEY line at the bottom
        3. Pass that value here

        This tool also resets the operation counter. After 30 file operations,
        you must re-read corrections.md and call this again.

        Args:
            session_key: The SESSION_KEY value from corrections.md
        """
        _audit("aio__confirm_read", "CALLED", session_key[:20] if session_key else "")

        # Read the actual key from corrections.md
        corrections_path = PROJECT_MAP_DIR / "corrections.md"
        if not corrections_path.exists():
            _audit("aio__confirm_read", "REJECTED", "corrections.md not found")
            return (
                "REJECTED: corrections.md not found.\n"
                "Run [初始化项目] first."
            )

        content = corrections_path.read_text(encoding="utf-8")

        # Extract SESSION_KEY from file
        actual_key = None
        for line in content.split("\n"):
            if line.startswith("SESSION_KEY:"):
                actual_key = line.split(":", 1)[1].strip()
                break

        if not actual_key:
            # No key in file yet — accept any key and write it
            # This handles first-time setup
            import secrets
            actual_key = secrets.token_hex(4)
            with open(corrections_path, "a", encoding="utf-8") as f:
                f.write(f"\n\nSESSION_KEY: {actual_key}\n")
            _audit("aio__confirm_read", "INITIALIZED", f"new key={actual_key}")

        if session_key.strip() != actual_key:
            _audit("aio__confirm_read", "REJECTED", f"key mismatch: got={session_key[:10]} expected={actual_key[:10]}")
            return (
                f"REJECTED: session_key does not match.\n"
                f"Re-read corrections.md and find the current SESSION_KEY value.\n"
                f"You may have read an outdated version."
            )

        # Write confirmed flag with counter=0
        SESSION_CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        SESSION_CONFIRMED_FLAG.write_text("0", encoding="utf-8")

        # Read available keys from corrections.md to show AI what's available
        keys = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ") and not line.startswith("- ["):
                keys.append(line[2:].strip())

        _audit("aio__confirm_read", "SUCCESS", f"key={actual_key},experience_keys={','.join(keys)}")

        keys_list = "\n".join(f"  - {k}" for k in keys) if keys else "  (none)"
        return (
            "SUCCESS: Context confirmed. You may now use Edit/Write/Bash tools.\n"
            "After 30 file operations, you will need to re-read and re-confirm.\n\n"
            f"Available experience keys (call aio__load_experience before related work):\n{keys_list}"
        )

    @mcp.tool()
    def aio__load_experience(key: str) -> str:
        """
        [COGNITIVE GATE] Load project-specific experience by key.

        Before doing work related to a specific area, call this tool to load
        the relevant experience/lessons. Keys are listed in corrections.md.

        Example keys: fileops, git, save, api, naming, deploy
        The key maps to a file in .ai-operation/docs/corrections/{key}.md

        Args:
            key: The experience category key from corrections.md
        """
        _audit("aio__load_experience", "CALLED", key)

        corrections_dir = PROJECT_MAP_DIR.parent / "corrections"
        experience_file = corrections_dir / f"{key}.md"

        if not experience_file.exists():
            # List available keys
            available = []
            if corrections_dir.exists():
                available = [f.stem for f in corrections_dir.glob("*.md")]
            _audit("aio__load_experience", "NOT_FOUND", f"key={key}")
            return (
                f"No experience found for key '{key}'.\n"
                f"Available keys: {', '.join(available) if available else '(none)'}\n"
                f"To add new experience, create .ai-operation/docs/corrections/{key}.md during [整理]."
            )

        content = experience_file.read_text(encoding="utf-8")
        _audit("aio__load_experience", "SUCCESS", f"key={key}, size={len(content)}")
        return content
