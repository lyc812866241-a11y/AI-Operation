"""
Cleanup tools -- garbage collection and git health.
Contains: aio__force_garbage_collection
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


def register_cleanup_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register cleanup-related tools onto the MCP server instance."""

    @mcp.tool()
    def aio__force_garbage_collection(confirm: bool = False) -> str:
        """
        [ENFORCEMENT TOOL] Scan for temp files AND git health issues.

        This tool MUST be called when the user issues the [清理] command.
        Set confirm=True only after the user has reviewed the list and approved cleanup.

        Scans for:
        1. Temporary/trash files (patch_*, test_*, temp_*, debug_*, *.temp)
        2. Git health: files that are gitignored but still tracked by git
           (e.g., .sqlite committed before being added to .gitignore)
        3. Git health: large untracked files that should be in .gitignore

        Args:
            confirm: If False, only lists issues. If True, cleans them up.
        """
        import glob
        import os

        report_sections = []
        actions = []  # (action_type, description, command_or_path)

        # -- Section 1: Temp files ---------------------------------
        patterns = [
            "patch_*.py", "test_*.py", "temp_*.py",
            "*.temp", "debug_*.py", "fix_*.py",
            "scripts/patch_*.py", "scripts/test_*.py",
        ]

        temp_files = []
        for pattern in patterns:
            temp_files.extend(glob.glob(pattern))
            temp_files.extend(glob.glob(f"**/{pattern}", recursive=True))
        temp_files = list(set(temp_files))

        if temp_files:
            report_sections.append(
                f"## Temp Files ({len(temp_files)} found)\n" +
                "\n".join(f"  - {f}" for f in sorted(temp_files))
            )
            for f in temp_files:
                actions.append(("delete", f, f))

        # -- Section 2: Git-tracked but gitignored files -----------
        tracked_ignored = []
        try:
            result = subprocess.run(
                ["git", "ls-files", "--ignored", "--exclude-standard", "-z"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout:
                tracked_ignored = [f for f in result.stdout.split("\0") if f.strip()]
        except Exception:
            pass

        if tracked_ignored:
            report_sections.append(
                f"## Git-Tracked but Gitignored ({len(tracked_ignored)} files)\n"
                f"These files are in .gitignore but still tracked by git.\n"
                f"They slow down every git operation.\n" +
                "\n".join(f"  - {f}" for f in sorted(tracked_ignored)[:30])
            )
            if len(tracked_ignored) > 30:
                report_sections.append(f"  ... and {len(tracked_ignored) - 30} more")
            for f in tracked_ignored:
                actions.append(("git_rm_cached", f, f))

        # -- Section 3: Large untracked files not in .gitignore ----
        large_untracked = []
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for f in result.stdout.strip().split("\n"):
                    f = f.strip()
                    if not f:
                        continue
                    try:
                        size = os.path.getsize(f)
                        if size > 1_000_000:  # > 1MB
                            large_untracked.append((f, size))
                    except OSError:
                        pass
        except Exception:
            pass

        if large_untracked:
            report_sections.append(
                f"## Large Untracked Files ({len(large_untracked)} > 1MB)\n"
                f"Consider adding these to .gitignore:\n" +
                "\n".join(f"  - {f} ({s // 1_000_000}MB)" for f, s in sorted(large_untracked, key=lambda x: -x[1]))
            )

        # -- Section 4: Git repo health ----------------------------
        git_size = 0
        try:
            for root, dirs, files in os.walk(".git"):
                for f in files:
                    git_size += os.path.getsize(os.path.join(root, f))
        except Exception:
            pass

        if git_size > 100_000_000:  # > 100MB
            report_sections.append(
                f"## Git Repo Size: {git_size // 1_000_000}MB\n"
                f"Consider running: git gc --aggressive\n"
                f"If .git was bloated by large files committed in the past,\n"
                f"consider: git filter-branch or BFG Repo-Cleaner to purge them."
            )

        # -- Build response ----------------------------------------
        if not report_sections:
            return "CLEAN: No issues found. Temp files clean, git healthy."

        if not confirm:
            return (
                f"PENDING CONFIRMATION -- Found {len(actions)} cleanable items\n\n" +
                "\n\n".join(report_sections) + "\n\n"
                f"Call this tool again with confirm=True to clean up.\n"
                f"(Git-tracked files will be untracked with 'git rm --cached', not deleted from disk.)"
            )

        # -- Execute cleanup ---------------------------------------
        results = []
        deleted_count = 0
        untracked_count = 0

        for action_type, desc, target in actions:
            try:
                if action_type == "delete":
                    os.remove(target)
                    deleted_count += 1
                elif action_type == "git_rm_cached":
                    subprocess.run(
                        ["git", "rm", "--cached", "-f", target],
                        capture_output=True, timeout=5
                    )
                    untracked_count += 1
            except Exception:
                pass

        # Auto-commit the git rm --cached changes
        if untracked_count > 0:
            try:
                _set_mcp_flag()
                subprocess.run(
                    ["git", "commit", "--no-verify", "--no-status", "-m",
                     f"chore: untrack {untracked_count} gitignored files for git performance"],
                    capture_output=True, text=True, timeout=30
                )
            except Exception:
                pass
            finally:
                _clear_mcp_flag()

        # -- Snapshot directory GC (save_history) -----------------
        # Keep the SNAPSHOT_RETAIN_COUNT most recent Phase 2 snapshots so
        # rollback remains available for recent saves, but old snapshots
        # don't accumulate forever.
        snapshots_deleted = _gc_save_history()

        _audit("aio__force_garbage_collection", "SUCCESS",
               f"deleted={deleted_count}, untracked={untracked_count}, snapshots={snapshots_deleted}")
        return (
            f"CLEANUP COMPLETE\n"
            f"Temp files deleted: {deleted_count}\n"
            f"Git-tracked files untracked: {untracked_count}\n"
            f"Old save snapshots purged: {snapshots_deleted}\n"
            f"{'Run `git gc` to reclaim .git disk space.' if git_size > 100_000_000 else ''}"
        )
