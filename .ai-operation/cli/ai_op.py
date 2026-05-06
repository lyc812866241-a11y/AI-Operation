#!/usr/bin/env python3
"""
AI-Operation Framework — CLI Tool (ai-op)
==========================================
Use MCP enforcement tools from the command line, without any IDE.

Usage:
    python .ai-operation/cli/ai_op.py <command> [args]

Commands:
    read                   - [读档] Read all 5 project map files
    report                 - [汇报] Generate architect report (interactive)
    save                   - [存档] Save project state (interactive)
    clean                  - [清理] Scan and delete temp files
    test <target> <cmd>    - [执行测试] Run isolated tests
    sync                   - Sync .clinerules to other IDE rule files
    status                 - Quick status overview (non-interactive)
    dashboard              - Launch web dashboard

Examples:
    python .ai-operation/cli/ai_op.py read
    python .ai-operation/cli/ai_op.py save
    python .ai-operation/cli/ai_op.py test "IngestNode" "python -m pytest tests/test_ingest.py"
    python .ai-operation/cli/ai_op.py clean
    python .ai-operation/cli/ai_op.py dashboard
"""

import sys
import os
import subprocess
from pathlib import Path

# Add mcp_server to path so we can import tools directly
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MCP_SERVER_DIR = SCRIPT_DIR.parent / "mcp_server"
sys.path.insert(0, str(MCP_SERVER_DIR))

PROJECT_MAP_DIR = PROJECT_ROOT / ".ai-operation" / "docs" / "project_map"

REQUIRED_FILES = {
    # 议题 #010: projectbrief 已删除,vision 在 design.md
    # 议题 #011: progress 已删除,历史归 git log
    "systemPatterns": "systemPatterns.md",
    "techContext": "techContext.md",
    "activeContext": "activeContext.md",
}


def cmd_read():
    """[读档] Read all 5 project map files."""
    print("=" * 60)
    print("  PROJECT MAP — Full State Report")
    print("=" * 60)

    for label, filename in REQUIRED_FILES.items():
        filepath = PROJECT_MAP_DIR / filename
        print(f"\n{'─' * 60}")
        print(f"  [{label}] {filename}")
        print(f"{'─' * 60}")
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            # Show first 50 lines
            lines = content.split("\n")
            for line in lines[:50]:
                print(f"  {line}")
            if len(lines) > 50:
                print(f"  ... ({len(lines) - 50} more lines)")
        else:
            print(f"  WARNING: File not found")

    print(f"\n{'=' * 60}")


def cmd_status():
    """Quick status overview."""
    print("\n  AI-Operation Framework Status")
    print("  " + "─" * 40)

    # Check active context
    active = PROJECT_MAP_DIR / "activeContext.md"
    if active.exists():
        content = active.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "当前焦点" in line or "Current Focus" in line:
                next_line_idx = content.split("\n").index(line) + 1
                if next_line_idx < len(content.split("\n")):
                    focus = content.split("\n")[next_line_idx].strip()
                    if focus and not focus.startswith(">") and not focus.startswith("#"):
                        print(f"  Focus: {focus[:80]}")
                break
    else:
        print("  Focus: [NOT INITIALIZED — run [初始化项目]]")

    # 议题 #011: progress 已删除,Tasks 改从当前 taskSpec 读取
    taskspec = PROJECT_MAP_DIR.parent / "taskSpec.md"
    if taskspec.exists():
        content = taskspec.read_text(encoding="utf-8")
        todo_count = content.count("- [ ]")
        done_count = content.count("- [x]")
        print(f"  Tasks: {done_count} done, {todo_count} pending")

    # Check rule files
    rule_files = [".clinerules", "CLAUDE.md", ".cursorrules", ".windsurfrules"]
    present = sum(1 for rf in rule_files if (PROJECT_ROOT / rf).exists())
    print(f"  IDE rules: {present}/4 present")

    # Check MCP configs
    mcp_configs = [".roo/mcp.json", ".cursor/mcp.json", ".windsurf/mcp.json", ".mcp.json"]
    mcp_present = sum(1 for mc in mcp_configs if (PROJECT_ROOT / mc).exists())
    print(f"  MCP configs: {mcp_present}/4 present")

    # Check git hooks
    hook = PROJECT_ROOT / ".git" / "hooks" / "pre-commit"
    print(f"  Git hook: {'installed' if hook.exists() else 'NOT installed'}")

    print()


def cmd_save():
    """[存档] Interactive save — prompts for updates."""
    print("\n  [存档] Interactive Save")
    print("  " + "─" * 40)

    print("\n  For each file, enter your update (or 'NO_CHANGE'):")
    print("  activeContext is REQUIRED.\n")

    updates = {}
    for label, filename in REQUIRED_FILES.items():
        required = label == "activeContext"
        tag = " [REQUIRED]" if required else " [NO_CHANGE ok]"
        print(f"  {label}{tag}:")
        lines = []
        print("  (type your update, empty line to finish)")
        while True:
            line = input("  > ")
            if line == "":
                break
            lines.append(line)
        updates[filename] = "\n".join(lines) if lines else "NO_CHANGE"

    # Validate
    if updates.get("activeContext.md", "").strip() == "NO_CHANGE":
        print("\n  ERROR: activeContext cannot be NO_CHANGE.")
        return

    # Apply updates
    changed = []
    for filename, content in updates.items():
        if content.strip() != "NO_CHANGE":
            filepath = PROJECT_MAP_DIR / filename
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n### [CLI Auto-Archive]\n{content.strip()}\n")
            changed.append(filename)

    if not changed:
        print("\n  No files updated.")
        return

    # Git commit with MCP flag
    flag = PROJECT_ROOT / ".ai-operation" / ".mcp_commit_flag"
    try:
        flag.write_text("cli_tool_commit", encoding="utf-8")
        subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True, cwd=str(PROJECT_ROOT))
        msg = f"chore: cli save [{', '.join(changed)}]"
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            check=True, capture_output=True, text=True, cwd=str(PROJECT_ROOT)
        )
        print(f"\n  SUCCESS: Updated {', '.join(changed)}")
        print(f"  Git: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"\n  Files updated but git commit failed: {e.stderr if e.stderr else e}")
    finally:
        if flag.exists():
            flag.unlink()


def cmd_clean():
    """[清理] Scan and delete temp files."""
    import glob

    patterns = [
        "patch_*.py", "test_*.py", "temp_*.py",
        "*.temp", "debug_*.py", "fix_*.py",
    ]

    found = set()
    for pattern in patterns:
        found.update(glob.glob(pattern))
        found.update(glob.glob(f"**/{pattern}", recursive=True))

    if not found:
        print("\n  CLEAN: No temporary files found.")
        return

    print(f"\n  Found {len(found)} temp files:")
    for f in sorted(found):
        print(f"    - {f}")

    answer = input("\n  Delete these files? [y/N] ")
    if answer.lower() == "y":
        deleted = 0
        for f in found:
            try:
                os.remove(f)
                deleted += 1
            except OSError:
                pass
        print(f"  Deleted {deleted} files.")
    else:
        print("  Cancelled.")


def cmd_test(target, command):
    """[执行测试] Run isolated tests."""
    # Check for pipeline keywords
    for kw in ["--all", "full_pipeline", "run_all"]:
        if kw in command.lower():
            print(f"\n  REJECTED: Full pipeline testing forbidden (detected '{kw}').")
            return

    print(f"\n  Running tests for: {target}")
    print(f"  Command: {command}")
    print("  " + "─" * 40)

    try:
        result = subprocess.run(
            command.split(),
            capture_output=False,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        status = "PASSED" if result.returncode == 0 else "FAILED"
        print(f"\n  Result: {status} (exit code {result.returncode})")
    except subprocess.TimeoutExpired:
        print("\n  FAILED: Test timed out after 300 seconds.")


def cmd_sync():
    """Sync .clinerules to other IDE rule files."""
    sync_script = SCRIPT_DIR.parent / "scripts" / "sync-rules.sh"
    if sys.platform == "win32":
        sync_script = SCRIPT_DIR.parent / "scripts" / "sync-rules.ps1"
        subprocess.run(["powershell", str(sync_script)], cwd=str(PROJECT_ROOT))
    else:
        subprocess.run(["bash", str(sync_script)], cwd=str(PROJECT_ROOT))


def cmd_dashboard():
    """Launch the web dashboard."""
    dashboard_script = SCRIPT_DIR / "dashboard.py"
    if not dashboard_script.exists():
        print("\n  ERROR: dashboard.py not found.")
        return
    subprocess.run([sys.executable, str(dashboard_script)], cwd=str(PROJECT_ROOT))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "read":
        cmd_read()
    elif cmd == "status":
        cmd_status()
    elif cmd == "save":
        cmd_save()
    elif cmd == "clean":
        cmd_clean()
    elif cmd == "test":
        if len(sys.argv) < 4:
            print("  Usage: ai_op.py test <target> <command>")
            return
        cmd_test(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "sync":
        cmd_sync()
    elif cmd == "dashboard":
        cmd_dashboard()
    elif cmd == "report":
        # Simple version — just calls read + status
        cmd_status()
        cmd_read()
    else:
        print(f"  Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
