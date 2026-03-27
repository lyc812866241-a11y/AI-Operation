"""
Architect Enforcement Tools
============================
This module contains MCP tools that enforce Level 4 Architect protocols.
These tools are called by the AI agent when the user issues system commands
like [存档], [读档], [清理].

The AI cannot bypass these tools. It MUST call them to complete the operation.
This is the "AI creates its own shackles and wears them" mechanism.
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Project map directory - relative to project root
PROJECT_MAP_DIR = Path("docs/project_map")

# The 5 canonical files defined in .clinerules
REQUIRED_FILES = {
    "projectbrief": "projectbrief.md",
    "systemPatterns": "systemPatterns.md",
    "techContext": "techContext.md",
    "activeContext": "activeContext.md",
    "progress": "progress.md",
}


def register_architect_tools(mcp: FastMCP):
    """Register all architect enforcement tools onto the MCP server instance."""

    @mcp.tool()
    def force_architect_save(
        projectbrief_update: str,
        systemPatterns_update: str,
        techContext_update: str,
        activeContext_update: str,
        progress_update: str,
    ) -> str:
        """
        [CRITICAL ENFORCEMENT TOOL] Execute the Level 4 Architect Save Protocol.

        This tool MUST be called when the user issues the [存档] command.
        The AI agent MUST NOT manually edit docs/project_map/ files or run git commands directly.
        All 5 parameters are REQUIRED. Use "NO_CHANGE" only if that file truly has no updates.

        Protocol reference: skills/mcp_protocols/SAVE_PROTOCOL.md

        Args:
            projectbrief_update: Updates to core vision or business goals. "NO_CHANGE" if none.
            systemPatterns_update: New architectural rules, pipeline nodes, or tool contracts discovered. "NO_CHANGE" if none.
            techContext_update: New tech stack constraints or dependencies discovered. "NO_CHANGE" if none.
            activeContext_update: REQUIRED. Current focus, what was just done, immediate next steps.
            progress_update: REQUIRED. Tasks completed this session, updated TODO items.

        Returns:
            Execution report with files updated and git commit status.
        """
        updates = {
            "projectbrief.md": projectbrief_update,
            "systemPatterns.md": systemPatterns_update,
            "techContext.md": techContext_update,
            "activeContext.md": activeContext_update,
            "progress.md": progress_update,
        }

        # Validate: activeContext and progress must never be NO_CHANGE
        if activeContext_update.strip() == "NO_CHANGE":
            return "REJECTED: activeContext_update cannot be NO_CHANGE. You must always update the current focus."
        if progress_update.strip() == "NO_CHANGE":
            return "REJECTED: progress_update cannot be NO_CHANGE. You must always record what was done this session."

        # Apply surgical updates (append-only to preserve history)
        changed_files = []
        for filename, content in updates.items():
            if content.strip() != "NO_CHANGE":
                filepath = PROJECT_MAP_DIR / filename
                if not filepath.parent.exists():
                    return f"FAILED: Directory {PROJECT_MAP_DIR} does not exist. Is this the correct project root?"
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(f"\n\n---\n### [MCP Auto-Archive]\n{content.strip()}\n")
                changed_files.append(filename)

        if not changed_files:
            return "WARNING: No files were updated. Verify nothing was missed this session."

        # Execute git commit
        try:
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            commit_msg = f"chore: architect save [{', '.join(changed_files)}]"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                check=True, capture_output=True, text=True
            )
            return (
                f"SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Git commit: {result.stdout.strip()}"
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            return (
                f"PARTIAL SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Git commit FAILED: {stderr}\n"
                f"Manual commit required."
            )

    @mcp.tool()
    def force_architect_read() -> str:
        """
        [ENFORCEMENT TOOL] Force a full read of all 5 project map files.

        This tool MUST be called when the user issues the [读档] command.
        Returns the full content of all 5 files as a structured context report.
        """
        report = ["# Project Map Full State Report\n"]
        for label, filename in REQUIRED_FILES.items():
            filepath = PROJECT_MAP_DIR / filename
            report.append(f"\n## [{label}] {filename}")
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                report.append(content)
            else:
                report.append(f"WARNING: File not found at {filepath}")
        return "\n".join(report)

    @mcp.tool()
    def force_garbage_collection(confirm: bool = False) -> str:
        """
        [ENFORCEMENT TOOL] Scan and list temporary/trash files for cleanup.

        This tool MUST be called when the user issues the [清理] command.
        Set confirm=True only after the user has reviewed the list and approved deletion.

        Args:
            confirm: If False, only lists files. If True, deletes them.
        """
        import glob
        import os

        patterns = [
            "patch_*.py", "test_*.py", "temp_*.py",
            "*.temp", "debug_*.py", "fix_*.py",
            "scripts/patch_*.py", "scripts/test_*.py",
        ]

        found_files = []
        for pattern in patterns:
            found_files.extend(glob.glob(pattern))
            found_files.extend(glob.glob(f"**/{pattern}", recursive=True))

        found_files = list(set(found_files))

        if not found_files:
            return "CLEAN: No temporary or trash files found."

        if not confirm:
            file_list = "\n".join(f"  - {f}" for f in sorted(found_files))
            return (
                f"PENDING CONFIRMATION\n"
                f"Found {len(found_files)} files to delete:\n{file_list}\n\n"
                f"Call this tool again with confirm=True to proceed with deletion."
            )

        deleted = []
        for f in found_files:
            try:
                os.remove(f)
                deleted.append(f)
            except OSError as e:
                pass

        return f"DELETED: {len(deleted)} files removed.\n" + "\n".join(f"  - {f}" for f in sorted(deleted))
