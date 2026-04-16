"""
Shared constants, paths, and utility functions for all MCP tools.
"""

import subprocess
from pathlib import Path

__all__ = [
    # Paths
    "PROJECT_MAP_DIR", "DETAILS_DIR", "MCP_COMMIT_FLAG",
    "TASKSPEC_DIR", "TASKSPEC_FILE", "TASKSPEC_APPROVED_FLAG",
    "FAST_TRACK_FLAG", "SAVE_STAGING_FILE", "BYPASS_DIR",
    # Size limits
    "MAX_FILE_CHARS", "MAX_TOTAL_CHARS", "SECTION_SIZE_THRESHOLD",
    "CORRECTIONS_MAX_BYTES", "MAX_TOOL_RESULT_BYTES",
    # Required files
    "REQUIRED_FILES",
    # Utility functions
    "_set_mcp_flag", "_clear_mcp_flag", "_section_merge",
    "_generate_toc", "_auto_split_oversized_sections",
    "_enforce_file_size_limit", "_compact_corrections",
    "_compact_dynamic_file", "git_commit_nonblocking",
    "_budget_truncate",
    "_parse_skill_frontmatter", "_discover_skills",
]

# Project map directory - relative to project root
PROJECT_MAP_DIR = Path(".ai-operation/docs/project_map")
DETAILS_DIR = PROJECT_MAP_DIR / "details"

# Flag files
MCP_COMMIT_FLAG = Path(".ai-operation/.mcp_commit_flag")
TASKSPEC_DIR = Path(".ai-operation/docs")
TASKSPEC_FILE = TASKSPEC_DIR / "taskSpec.md"
TASKSPEC_APPROVED_FLAG = Path(".ai-operation/.taskspec_approved")
FAST_TRACK_FLAG = Path(".ai-operation/.fast_track")
SAVE_STAGING_FILE = Path(".ai-operation/.save_staging.json")
BYPASS_DIR = Path(".ai-operation/.bypasses")  # Per-rule bypass flags

# Size limits
MAX_FILE_CHARS = 16_000      # 16KB per file
MAX_TOTAL_CHARS = 50_000     # 50KB total (~12K tokens)
SECTION_SIZE_THRESHOLD = 8_000  # 8KB -- split section to subfile
CORRECTIONS_MAX_BYTES = 10_000  # 10KB -- archive old lessons
MAX_TOOL_RESULT_BYTES = 12_000  # 12KB -- truncate any MCP tool return exceeding this

# Required project_map files
REQUIRED_FILES = {
    "projectbrief": "projectbrief.md",
    "systemPatterns": "systemPatterns.md",
    "techContext": "techContext.md",
    "conventions": "conventions.md",
    "activeContext": "activeContext.md",
    "progress": "progress.md",
    "inventory": "inventory.md",
}


def _set_mcp_flag():
    """Create flag file so git pre-commit hook allows project_map commits."""
    MCP_COMMIT_FLAG.parent.mkdir(parents=True, exist_ok=True)
    MCP_COMMIT_FLAG.write_text("mcp_tool_commit", encoding="utf-8")


def _clear_mcp_flag():
    """Remove flag file after commit."""
    if MCP_COMMIT_FLAG.exists():
        MCP_COMMIT_FLAG.unlink()


def _section_merge(existing_content: str, section_updates: dict) -> tuple:
    """Merge updates into specific sections of a markdown file."""
    import re

    lines = existing_content.split("\n")
    sections = {}
    current_section = None
    current_start = 0

    for i, line in enumerate(lines):
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = (current_start, i, lines[current_start:i])
            raw_title = line[3:].strip()
            clean_title = re.sub(r'^\d+\.\s*', '', raw_title)
            current_section = clean_title
            current_start = i

    if current_section is not None:
        sections[current_section] = (current_start, len(lines), lines[current_start:])

    if not sections:
        return existing_content, []

    changed = []
    result_lines = []
    last_end = 0

    sorted_sections = sorted(sections.items(), key=lambda x: x[1][0])

    for title, (start, end, original_lines) in sorted_sections:
        if start > last_end:
            result_lines.extend(lines[last_end:start])

        matched_update = None
        for update_key, update_val in section_updates.items():
            if (update_key in title or title in update_key or
                    update_key.lower() in title.lower() or title.lower() in update_key.lower()):
                matched_update = update_val
                break

        if matched_update and matched_update.strip().upper() != "SKIP":
            result_lines.append(original_lines[0])
            result_lines.append("")
            result_lines.append(matched_update.strip())
            result_lines.append("")
            changed.append(title)
        else:
            result_lines.extend(original_lines)

        last_end = end

    if last_end < len(lines):
        result_lines.extend(lines[last_end:])

    return "\n".join(result_lines), changed


def _generate_toc(content: str, filename: str) -> str:
    """Generate table-of-contents summary for budget-tight mode."""
    lines = content.split("\n")
    toc_lines = [f"[TOC mode -- budget tight, use aio__detail_read('{filename}') for full content]\n"]

    for line in lines:
        if line.startswith("## "):
            toc_lines.append(f"  {line.strip()}")
        elif line.startswith("# "):
            toc_lines.append(line.strip())

    toc_lines.append(f"\n({len(content)} chars, {content.count(chr(10))} lines)")
    return "\n".join(toc_lines)


def _auto_split_oversized_sections(filepath: Path, depth: int = 0, _file_counter: list = None) -> list:
    """Recursively split oversized sections into detail subfiles."""
    import re

    MAX_TOTAL_FILES = 200
    if _file_counter is None:
        _file_counter = [0]
    if _file_counter[0] >= MAX_TOTAL_FILES or not filepath.exists():
        return []

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    parent_name = filepath.stem

    header_prefix = "#" * (2 + depth) + " "

    sections = []
    current_title = None
    current_header_idx = None

    for i, line in enumerate(lines):
        if line.startswith(header_prefix) and not line.startswith(header_prefix + "#"):
            if current_title is not None:
                sections.append((current_title, current_header_idx, current_header_idx + 1, i))
            raw = line[len(header_prefix):].strip()
            current_title = re.sub(r'^\d+\.\s*', '', raw)
            current_header_idx = i

    if current_title is not None:
        sections.append((current_title, current_header_idx, current_header_idx + 1, len(lines)))

    if not sections:
        return []

    if depth == 0:
        out_dir = DETAILS_DIR
    else:
        out_dir = DETAILS_DIR / f"L{depth}"
    out_dir.mkdir(parents=True, exist_ok=True)

    split_sections = []
    new_lines = list(lines)
    offset = 0

    for title, header_idx, body_start, body_end in sections:
        body = "\n".join(lines[body_start:body_end]).strip()

        if "-> [详见" in body:
            continue

        if len(body) > SECTION_SIZE_THRESHOLD:
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]', '_', title).strip('_')
            detail_filename = f"{parent_name}__{safe_title}.md"
            detail_path = out_dir / detail_filename
            rel_path = detail_path.relative_to(PROJECT_MAP_DIR)
            detail_content = f"{header_prefix}{title}\n\n> 拆分自 {filepath.name}，depth={depth}。\n\n{body}\n"
            detail_path.write_text(detail_content, encoding="utf-8")

            pointer = f"\n> {'->' * (depth + 1)} [详见 {rel_path}]\n"
            adj_start = body_start + offset
            adj_end = body_end + offset
            new_lines[adj_start:adj_end] = [pointer]
            offset -= (body_end - body_start - 1)

            _file_counter[0] += 1
            split_sections.append(
                f"{'  ' * depth}L{depth}: {title} -> {rel_path} ({len(body)} chars)"
            )

            child_splits = _auto_split_oversized_sections(detail_path, depth + 1, _file_counter)
            split_sections.extend(child_splits)

    if split_sections:
        filepath.write_text("\n".join(new_lines), encoding="utf-8")

    return split_sections


def _enforce_file_size_limit(filepath: Path) -> str:
    """Universal fallback: force-split any file exceeding MAX_FILE_CHARS."""
    if not filepath.exists():
        return ""

    content = filepath.read_text(encoding="utf-8")
    byte_size = len(content.encode("utf-8"))
    if byte_size <= MAX_FILE_CHARS:
        return ""

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    parent_name = filepath.stem

    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    overflow_name = f"{parent_name}__overflow_{timestamp}.md"
    overflow_path = DETAILS_DIR / overflow_name

    keep_chars = 2000
    summary = content[:keep_chars]
    overflow = content[keep_chars:]

    overflow_content = (
        f"# Overflow: {filepath.name}\n\n"
        f"> Auto-split on {timestamp} because file exceeded {MAX_FILE_CHARS} chars.\n\n"
        f"{overflow}\n"
    )
    overflow_path.write_text(overflow_content, encoding="utf-8")

    pointer = f"\n\n> -> [剩余内容: details/{overflow_name}] ({len(overflow)} chars)\n"
    filepath.write_text(summary + pointer, encoding="utf-8")

    return f"{filepath.name}: overflow split -> details/{overflow_name} ({len(overflow)} chars moved)"


def _compact_corrections(filepath: Path) -> str:
    """Compact corrections.md when it exceeds threshold."""
    if not filepath.exists():
        return ""

    content = filepath.read_text(encoding="utf-8")
    if len(content.encode("utf-8")) <= CORRECTIONS_MAX_BYTES:
        return ""

    import re
    import datetime

    parts = content.split("\n---\n")

    header_parts = []
    entry_parts = []
    for part in parts:
        if "DATE:" in part and "LESSON:" in part:
            entry_parts.append(part)
        else:
            header_parts.append(part)

    if len(entry_parts) <= 5:
        slim_header = "# Bootstrap Corrections Log\n\n> 经验库。COUNT >= 3 自动升级到 conventions.md 成为项目契约。\n"
        rebuilt = slim_header + "\n---\n".join(entry_parts)
        filepath.write_text(rebuilt, encoding="utf-8")
        new_size = len(rebuilt.encode("utf-8"))
        if new_size <= CORRECTIONS_MAX_BYTES:
            return f"corrections.md: header trimmed ({len(content.encode('utf-8'))} -> {new_size} bytes)"
        content = rebuilt
        header_parts = [slim_header]

    to_archive = entry_parts[:-5] if len(entry_parts) > 5 else []
    to_keep = entry_parts[-5:] if len(entry_parts) > 5 else entry_parts

    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    archive_name = f"corrections__archive_{timestamp}.md"
    archive_path = DETAILS_DIR / archive_name

    archive_content = (
        f"# Corrections Archive ({len(to_archive)} entries)\n\n"
        f"> Archived from corrections.md on {timestamp}\n\n"
    )
    archive_content += "\n---\n".join(to_archive)
    archive_path.write_text(archive_content, encoding="utf-8")

    pointer = (
        f"\n> -> [旧经验归档: {len(to_archive)} 条已移至 details/{archive_name}]\n"
    )

    rebuilt = "\n---\n".join(header_parts)
    rebuilt += f"\n---\n{pointer}\n---\n"
    rebuilt += "\n---\n".join(to_keep)

    filepath.write_text(rebuilt, encoding="utf-8")
    return f"corrections.md: archived {len(to_archive)} old entries -> details/{archive_name}"


def _compact_dynamic_file(content: str, filename: str) -> str:
    """Compact a dynamic file that has grown too large. Keep header + last entry only."""
    sections = content.split("\n---\n")

    if len(sections) <= 2:
        return content

    header = sections[0]
    latest = sections[-1]
    compacted_count = len(sections) - 2

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    compact_notice = (
        f"\n### [Auto-Compacted -- {timestamp}]\n"
        f"{compacted_count} older entries compacted. History in git log."
    )

    result_parts = [header, compact_notice, latest]
    return "\n---\n".join(result_parts)


def _parse_skill_frontmatter(skill_path: Path) -> dict:
    """Parse YAML frontmatter from a SKILL.md file.

    Returns dict with keys: name, description, when, paths, tools.
    Returns empty dict if no frontmatter found.
    """
    if not skill_path.exists():
        return {}

    content = skill_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {}

    # Find closing ---
    end = content.find("---", 3)
    if end == -1:
        return {}

    frontmatter_text = content[3:end].strip()
    result = {}

    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()

        # Parse list values: ["a", "b", "c"]
        if val.startswith("[") and val.endswith("]"):
            items = val[1:-1]
            result[key] = [
                item.strip().strip('"').strip("'")
                for item in items.split(",")
                if item.strip()
            ]
        else:
            result[key] = val.strip('"').strip("'")

    return result


def _discover_skills(skills_dir: Path = None) -> list:
    """Discover all skills with parsed frontmatter.

    Returns list of dicts: {name, description, when, paths, tools, skill_dir}.
    """
    if skills_dir is None:
        skills_dir = Path(".ai-operation/skills")

    if not skills_dir.exists():
        return []

    skills = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        meta = _parse_skill_frontmatter(skill_md)
        if meta:
            meta["skill_dir"] = str(skill_md.parent)
            skills.append(meta)
        else:
            # Skill without frontmatter -- include with basic info
            skills.append({
                "name": skill_md.parent.name,
                "description": "(no frontmatter)",
                "when": [],
                "paths": [],
                "tools": [],
                "skill_dir": str(skill_md.parent),
            })

    return skills


def _budget_truncate(result: str, max_bytes: int = MAX_TOOL_RESULT_BYTES) -> str:
    """Truncate tool result to budget. Prevents context window overflow.

    Uses character-level truncation to avoid cutting multi-byte UTF-8
    characters (Chinese chars = 3 bytes, emoji = 4 bytes).
    """
    encoded = result.encode("utf-8")
    if len(encoded) <= max_bytes:
        return result
    # Walk back from max_bytes to find a safe character boundary
    truncated = encoded[:max_bytes]
    # Remove trailing incomplete UTF-8 sequence (1-3 bytes max)
    while truncated and truncated[-1] & 0xC0 == 0x80:
        truncated = truncated[:-1]
    if truncated and truncated[-1] & 0x80:
        # Last byte is a lead byte without continuation -- remove it too
        truncated = truncated[:-1]
    safe_str = truncated.decode("utf-8")
    return (
        f"{safe_str}\n\n"
        f"[TRUNCATED: showing {len(truncated):,} of {len(encoded):,} bytes. "
        f"Use aio__detail_read for full content.]"
    )


def git_commit_nonblocking(files_to_add: list, commit_msg: str, _audit_fn=None) -> tuple:
    """Non-blocking git add + commit. Returns (git_status, git_diag).

    Uses Popen + stdin=DEVNULL to avoid Windows stdio deadlocks.
    """
    import shutil
    import time

    git_status = "not attempted"
    git_diag = {}

    try:
        _set_mcp_flag()

        git_diag["cwd"] = str(Path.cwd())
        git_diag["project_map_dir"] = str(PROJECT_MAP_DIR.resolve()) if PROJECT_MAP_DIR.exists() else "MISSING"
        git_diag["git_path"] = shutil.which("git") or "NOT FOUND"
        git_diag["files_to_add_count"] = len(files_to_add)

        if files_to_add:
            t0 = time.time()
            add_proc = subprocess.Popen(
                ["git", "add"] + files_to_add,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            try:
                add_proc.wait(timeout=60)
                git_diag["add_time"] = f"{time.time() - t0:.1f}s"
                git_diag["add_rc"] = add_proc.returncode
            except subprocess.TimeoutExpired:
                add_proc.kill()
                add_proc.wait()
                git_diag["add_time"] = f"{time.time() - t0:.1f}s (TIMEOUT)"
                git_status = "git add timed out"

            if add_proc.returncode == 0:
                t1 = time.time()
                commit_proc = subprocess.Popen(
                    ["git", "commit", "--no-verify", "--no-status", "-m", commit_msg, "--"] + files_to_add,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                try:
                    commit_proc.wait(timeout=30)
                    git_diag["commit_time"] = f"{time.time() - t1:.1f}s"
                    git_diag["commit_rc"] = commit_proc.returncode
                    if commit_proc.returncode == 0:
                        git_status = "committed"
                    else:
                        git_status = f"commit exited {commit_proc.returncode}"
                except subprocess.TimeoutExpired:
                    commit_proc.kill()
                    commit_proc.wait()
                    git_diag["commit_time"] = f"{time.time() - t1:.1f}s (TIMEOUT)"
                    git_status = "commit timed out -- run manually"
    except Exception as e:
        git_status = f"error: {str(e)[:100]}"
    finally:
        _clear_mcp_flag()
        if TASKSPEC_APPROVED_FLAG.exists():
            TASKSPEC_APPROVED_FLAG.unlink()
        if FAST_TRACK_FLAG.exists():
            FAST_TRACK_FLAG.unlink()

    return git_status, git_diag
