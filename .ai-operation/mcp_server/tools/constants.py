"""
Shared constants, paths, and utility functions for all MCP tools.
"""

import subprocess
from pathlib import Path

__all__ = [
    # Paths
    "PROJECT_MAP_DIR", "FRAMEWORK_DIR", "WISDOM_FILE", "DETAILS_DIR", "MCP_COMMIT_FLAG",
    "TASKSPEC_DIR", "TASKSPEC_FILE", "TASKSPEC_APPROVED_FLAG",
    "FAST_TRACK_FLAG", "SAVE_STAGING_FILE", "BYPASS_DIR",
    "SAVE_HISTORY_DIR", "SNAPSHOT_RETAIN_COUNT",
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
    "_check_and_heal_gitignore",
    "_snapshot_project_map", "_restore_from_snapshot", "_gc_save_history",
    "_extract_section_titles",
    "_extract_taskspec_files", "_git_dirty_files",
    "_budget_truncate",
    "_parse_skill_frontmatter", "_discover_skills",
]

# Project map directory - relative to project root (项目级 一阶)
PROJECT_MAP_DIR = Path(".ai-operation/docs/project_map")
DETAILS_DIR = PROJECT_MAP_DIR / "details"

# Framework directory + cross-project wisdom file (跨项目级 二阶, 议题 #009)
FRAMEWORK_DIR = Path(".ai-operation")
WISDOM_FILE = FRAMEWORK_DIR / "wisdom.md"

# Flag files
MCP_COMMIT_FLAG = Path(".ai-operation/.mcp_commit_flag")
TASKSPEC_DIR = Path(".ai-operation/docs")
TASKSPEC_FILE = TASKSPEC_DIR / "taskSpec.md"
TASKSPEC_APPROVED_FLAG = Path(".ai-operation/.taskspec_approved")
FAST_TRACK_FLAG = Path(".ai-operation/.fast_track")
SAVE_STAGING_FILE = Path(".ai-operation/.save_staging.json")
BYPASS_DIR = Path(".ai-operation/.bypasses")  # Per-rule bypass flags
SAVE_HISTORY_DIR = Path(".ai-operation/.save_history")  # Phase 2 snapshots for rollback
SNAPSHOT_RETAIN_COUNT = 10  # gc keeps this many latest snapshots

# Size limits
MAX_FILE_CHARS = 16_000      # 16KB per file
MAX_TOTAL_CHARS = 50_000     # 50KB total (~12K tokens)
SECTION_SIZE_THRESHOLD = 8_000  # 8KB -- split section to subfile
CORRECTIONS_MAX_BYTES = 10_000  # 10KB -- archive old lessons
MAX_TOOL_RESULT_BYTES = 200_000  # 200KB -- no practical truncation (Claude handles large returns)

# Required project_map files
# 议题 #009 重组:conventions 删除,并入 corrections(scope=单项目)
# 议题 #010 重组:projectbrief 删除,vision/negative_scope 由 design.md 接管(单一来源)
# 议题 #011 重组:progress 删除,职责被 activeContext / techContext / corrections / git log 分流接管
#                同时删除 session_compaction 僵尸 feature
# 跨项目智慧 → wisdom.md(框架级,见 WISDOM_FILE)
REQUIRED_FILES = {
    "systemPatterns": "systemPatterns.md",
    "techContext": "techContext.md",
    "activeContext": "activeContext.md",
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


def _auto_split_oversized_sections(filepath: Path, depth: int = 0, _file_counter: list = None, threshold: int = None) -> list:
    """Recursively split oversized sections into detail subfiles.

    threshold: override SECTION_SIZE_THRESHOLD. _enforce_file_size_limit uses
    this to progressively lower the bar (4K -> 2K -> 1K) when a file exceeds
    MAX_FILE_CHARS but no single section is > SECTION_SIZE_THRESHOLD.
    """
    import re

    MAX_TOTAL_FILES = 200
    if _file_counter is None:
        _file_counter = [0]
    if threshold is None:
        threshold = SECTION_SIZE_THRESHOLD
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

        if len(body) > threshold:
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
    """Universal fallback: force-split any file exceeding MAX_FILE_CHARS.

    Strategy (two-tier):
      1. Adaptive semantic split -- call _auto_split_oversized_sections with
         progressively lower thresholds (4K -> 2K -> 1K). This keeps splits
         aligned to section headers so every overflow fragment is a complete
         semantic unit, never a mid-word / mid-character chop.
      2. Newline-aligned char slice -- only if the file has zero `##` sections
         (pure blob) so adaptive splits can't bite. Safety net.
    """
    if not filepath.exists():
        return ""

    def _byte_size() -> int:
        return len(filepath.read_text(encoding="utf-8").encode("utf-8"))

    if _byte_size() <= MAX_FILE_CHARS:
        return ""

    # -- Tier 1: adaptive semantic split -------------------------
    split_log = []
    for threshold in (4_000, 2_000, 1_000):
        splits = _auto_split_oversized_sections(filepath, threshold=threshold)
        split_log.extend(splits)
        if _byte_size() <= MAX_FILE_CHARS:
            return (
                f"{filepath.name}: adaptive semantic split (threshold={threshold}) "
                f"-> {len(split_log)} section(s) moved to details/"
            )

    # -- Tier 2: last-resort newline-aligned char slice ----------
    # Reached only if file has no ## sections at all (extremely rare)
    content = filepath.read_text(encoding="utf-8")
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    parent_name = filepath.stem

    DETAILS_DIR.mkdir(parents=True, exist_ok=True)
    overflow_name = f"{parent_name}__overflow_{timestamp}.md"
    overflow_path = DETAILS_DIR / overflow_name

    keep_chars = 2000
    # Align cut to nearest newline so we don't chop a UTF-8 character or a
    # word in half (the 火火兔 bug: `produc` + `t_appearance_extractor`).
    cut = content.rfind("\n", 0, keep_chars)
    if cut <= 0:
        cut = keep_chars
    else:
        cut += 1  # include the newline in summary
    summary = content[:cut]
    overflow = content[cut:]

    overflow_content = (
        f"# Overflow: {filepath.name}\n\n"
        f"> Auto-split on {timestamp} because file exceeded {MAX_FILE_CHARS} chars.\n\n"
        f"{overflow}\n"
    )
    overflow_path.write_text(overflow_content, encoding="utf-8")

    pointer = f"\n\n> -> [剩余内容: details/{overflow_name}] ({len(overflow)} chars)\n"
    filepath.write_text(summary + pointer, encoding="utf-8")

    return (
        f"{filepath.name}: no sections to split -- last-resort char slice "
        f"at newline -> details/{overflow_name} ({len(overflow)} chars moved)"
    )


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
        slim_header = "# Bootstrap Corrections Log\n\n> 经验库。议题 #009 重组后:同 scope 内由人主动判断是否提炼;不再有自动升级。\n"
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


def _extract_section_titles(content: str) -> list:
    """Return the list of `## ` section titles in a markdown file, with
    leading numeric prefixes stripped (mirrors _section_merge matching).

    Used by save.py to produce diagnostic messages when AI-supplied
    ===SECTION=== keys fail to match.
    """
    import re
    titles = []
    for line in content.split("\n"):
        if line.startswith("## "):
            raw = line[3:].strip()
            clean = re.sub(r"^\d+\.\s*", "", raw)
            titles.append(clean)
    return titles


def _extract_taskspec_files() -> list:
    """Parse the active taskSpec.md and return existing project code paths
    referenced under '## 3. Files to Modify'.

    Only paths that:
      - match r'[\\w./-]+\\.\\w{1,5}' (simple path + extension, no spaces)
      - are NOT under .ai-operation/ (framework-managed)
      - are NOT absolute paths
      - actually exist on disk
    are returned. Missing paths are silently skipped (tolerate spec typos).
    """
    import re

    if not TASKSPEC_FILE.exists():
        return []

    try:
        content = TASKSPEC_FILE.read_text(encoding="utf-8")
    except Exception:
        return []

    # Carve out section 3 (from "## 3." up to next "## " or EOF)
    m = re.search(
        r"##\s*3\.[^\n]*\n(.*?)(?=\n##\s|\Z)",
        content,
        re.DOTALL,
    )
    if not m:
        return []

    section = m.group(1)
    candidates = re.findall(r"[\w./-]+\.\w{1,5}", section)

    results = []
    seen = set()
    for c in candidates:
        c = c.strip().lstrip("./")
        if not c or c in seen:
            continue
        seen.add(c)
        if c.startswith(".ai-operation/") or c.startswith(".ai-operation\\"):
            continue
        p = Path(c)
        if p.is_absolute():
            continue
        if not p.exists():
            continue
        results.append(c)
    return results


def _git_dirty_files(paths: list) -> list:
    """Return the subset of `paths` that show up as dirty (modified, added,
    or untracked) in `git status --porcelain`. Uses Popen + DEVNULL to avoid
    Windows PIPE deadlock.
    """
    import tempfile

    if not paths:
        return []

    try:
        with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
            proc = subprocess.Popen(
                ["git", "status", "--porcelain", "--"] + paths,
                stdin=subprocess.DEVNULL,
                stdout=out_f,
                stderr=err_f,
            )
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                return []
            if proc.returncode != 0:
                return []
            out_f.seek(0)
            raw = out_f.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    dirty = []
    path_set = set(p.replace("\\", "/") for p in paths)
    for line in raw.split("\n"):
        if len(line) < 4:
            continue
        # porcelain format: "XY path" or "XY orig -> new" (rename)
        tail = line[3:].strip()
        if "->" in tail:
            tail = tail.split("->", 1)[1].strip()
        tail = tail.strip('"').replace("\\", "/")
        if tail in path_set:
            dirty.append(tail)
    # Preserve input order
    return [p for p in paths if p.replace("\\", "/") in set(dirty)]


def _snapshot_project_map(ts: str) -> "Path":
    """Copy every .md file under project_map (including details/) into
    SAVE_HISTORY_DIR/<ts>/ so Phase 2 can roll back on exception.

    Returns the snapshot directory path. Non-existent project_map yields
    an empty snapshot dir (still created so the restore path is uniform).
    """
    import shutil

    snapshot = SAVE_HISTORY_DIR / ts
    snapshot.mkdir(parents=True, exist_ok=True)

    if not PROJECT_MAP_DIR.exists():
        return snapshot

    for md in PROJECT_MAP_DIR.rglob("*.md"):
        try:
            rel = md.relative_to(PROJECT_MAP_DIR)
        except ValueError:
            continue
        dst = snapshot / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(md, dst)
        except Exception:
            # Best-effort snapshot; a single unreadable file should not
            # block the save flow.
            continue

    return snapshot


def _restore_from_snapshot(snapshot_dir: "Path") -> list:
    """Restore every .md under snapshot_dir back into PROJECT_MAP_DIR.

    Returns the list of restored relative paths. Missing snapshot or
    filesystem errors produce an empty list rather than raising, so the
    save tool can surface a PARTIAL status instead of exploding.
    """
    import shutil

    if not snapshot_dir or not snapshot_dir.exists():
        return []

    restored = []
    PROJECT_MAP_DIR.mkdir(parents=True, exist_ok=True)
    for md in snapshot_dir.rglob("*.md"):
        try:
            rel = md.relative_to(snapshot_dir)
        except ValueError:
            continue
        dst = PROJECT_MAP_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(md, dst)
            restored.append(str(rel))
        except Exception:
            continue
    return restored


def _gc_save_history(retain: int = SNAPSHOT_RETAIN_COUNT) -> int:
    """Delete snapshot directories under SAVE_HISTORY_DIR beyond `retain`.

    Keeps the `retain` most-recently-modified subdirs. Returns the number
    of directories deleted. Silent on missing SAVE_HISTORY_DIR.
    """
    import shutil

    if not SAVE_HISTORY_DIR.exists():
        return 0

    dirs = [d for d in SAVE_HISTORY_DIR.iterdir() if d.is_dir()]
    if len(dirs) <= retain:
        return 0

    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    deleted = 0
    for old in dirs[retain:]:
        try:
            shutil.rmtree(old)
            deleted += 1
        except Exception:
            continue
    return deleted


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


def _check_and_heal_gitignore(audit_fn=None) -> list:
    """Detect if project_map is gitignored and auto-heal .gitignore.

    Strategy:
      - Precise rule containing "project_map" substring -> remove the line.
      - Broad rule (e.g. .ai-operation/*) -> append whitelist exception
        `!.ai-operation/docs/project_map/` instead of removing.

    Returns list of action strings describing what was changed. Empty list
    means no change (either not ignored, or nothing safe to touch).
    """
    import tempfile

    gitignore = Path(".gitignore")
    if not gitignore.exists():
        return []

    probe = PROJECT_MAP_DIR / "activeContext.md"
    if not probe.exists():
        # Nothing to probe with -- cannot determine ignore state.
        return []

    # Probe: is project_map currently ignored?
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-v", str(probe)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            text=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []  # not ignored

    # Parse `git check-ignore -v` output.
    # Format: <source>:<lineno>:<pattern><TAB><pathname>
    first_line = result.stdout.strip().split("\n")[0]
    tab_parts = first_line.split("\t")
    if not tab_parts:
        return []
    left = tab_parts[0]
    src_parts = left.split(":", 2)
    if len(src_parts) < 3:
        return []
    pattern = src_parts[2].strip()
    if not pattern:
        return []

    lines = gitignore.read_text(encoding="utf-8").splitlines()
    actions = []
    is_precise = "project_map" in pattern

    if is_precise:
        # Remove matching line(s). Compare with trailing-slash normalization.
        key = pattern.rstrip("/")
        new_lines = []
        removed = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and stripped.rstrip("/") == key:
                removed.append(line)
                continue
            new_lines.append(line)
        if removed:
            gitignore.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            for r in removed:
                actions.append(f"removed '{r}'")
                if audit_fn:
                    audit_fn(
                        "aio__auto_fix_gitignore", "SUCCESS",
                        f"removed line '{r}' reason=blocking_project_map",
                    )
    else:
        # Broad rule -- preserve it, add whitelist exception.
        whitelist = "!.ai-operation/docs/project_map/"
        whitelist_glob = "!.ai-operation/docs/project_map/**"
        already = any(l.strip() in (whitelist, whitelist_glob) for l in lines)
        if not already:
            # Ensure trailing newline discipline, then append.
            new_lines = list(lines) + [whitelist]
            gitignore.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            actions.append(
                f"appended '{whitelist}' (broad rule '{pattern}' preserved)"
            )
            if audit_fn:
                audit_fn(
                    "aio__auto_fix_gitignore", "SUCCESS",
                    f"appended whitelist '{whitelist}' reason=broad_rule={pattern}",
                )

    # Stage the modified .gitignore so the next commit can include it.
    if actions:
        try:
            subprocess.run(
                ["git", "add", "-f", ".gitignore"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except Exception:
            pass  # non-fatal; next commit will pick it up when files_to_add includes .gitignore

    return actions


def git_commit_nonblocking(files_to_add: list, commit_msg: str, _audit_fn=None) -> tuple:
    """Non-blocking git add + commit. Returns (git_status, git_diag).

    Hardening:
      - Uses `git add -f` so framework-managed project_map files bypass any
        user-side .gitignore rule.
      - Captures stderr to a TemporaryFile (avoids the Windows PIPE deadlock
        that subprocess.run+capture_output triggers while still preserving
        error diagnostics on non-zero rc).
      - Only consumes TASKSPEC_APPROVED_FLAG / FAST_TRACK_FLAG on commit
        SUCCESS. On failure the flags stay, so a retry does not require
        re-approval (flag transaction).
    """
    import shutil
    import tempfile
    import time

    git_status = "not attempted"
    git_diag = {}
    commit_succeeded = False
    add_rc = None

    try:
        _set_mcp_flag()

        git_diag["cwd"] = str(Path.cwd())
        git_diag["project_map_dir"] = str(PROJECT_MAP_DIR.resolve()) if PROJECT_MAP_DIR.exists() else "MISSING"
        git_diag["git_path"] = shutil.which("git") or "NOT FOUND"
        git_diag["files_to_add_count"] = len(files_to_add)

        if files_to_add:
            t0 = time.time()
            with tempfile.TemporaryFile() as add_err_f:
                add_proc = subprocess.Popen(
                    ["git", "add", "-f"] + files_to_add,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=add_err_f,
                )
                try:
                    add_proc.wait(timeout=60)
                    git_diag["add_time"] = f"{time.time() - t0:.1f}s"
                    add_rc = add_proc.returncode
                    git_diag["add_rc"] = add_rc
                except subprocess.TimeoutExpired:
                    add_proc.kill()
                    add_proc.wait()
                    git_diag["add_time"] = f"{time.time() - t0:.1f}s (TIMEOUT)"
                    git_status = "git add timed out"

                if add_rc is not None and add_rc != 0:
                    add_err_f.seek(0)
                    err_bytes = add_err_f.read()
                    err_text = err_bytes.decode("utf-8", errors="replace").strip()
                    git_diag["add_stderr"] = err_text[:500] if err_text else "(no stderr output)"
                    git_status = f"git add failed (rc={add_rc}): {err_text[:200] or '(empty)'}"

            if add_rc == 0:
                t1 = time.time()
                with tempfile.TemporaryFile() as commit_err_f:
                    commit_proc = subprocess.Popen(
                        ["git", "commit", "--no-verify", "--no-status", "-m", commit_msg, "--"] + files_to_add,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=commit_err_f,
                    )
                    try:
                        commit_proc.wait(timeout=30)
                        git_diag["commit_time"] = f"{time.time() - t1:.1f}s"
                        git_diag["commit_rc"] = commit_proc.returncode
                        if commit_proc.returncode == 0:
                            git_status = "committed"
                            commit_succeeded = True
                        else:
                            commit_err_f.seek(0)
                            err_text = commit_err_f.read().decode("utf-8", errors="replace").strip()
                            git_diag["commit_stderr"] = err_text[:500] if err_text else "(no stderr output)"
                            git_status = f"commit exited {commit_proc.returncode}: {err_text[:200] or '(empty)'}"
                    except subprocess.TimeoutExpired:
                        commit_proc.kill()
                        commit_proc.wait()
                        git_diag["commit_time"] = f"{time.time() - t1:.1f}s (TIMEOUT)"
                        git_status = "commit timed out -- run manually"
    except Exception as e:
        git_status = f"error: {str(e)[:100]}"
    finally:
        _clear_mcp_flag()
        # Flag transaction: only consume approval flags when the commit
        # actually landed. Keeping them on failure lets the user retry
        # the save without re-submitting a taskSpec.
        if commit_succeeded:
            if TASKSPEC_APPROVED_FLAG.exists():
                TASKSPEC_APPROVED_FLAG.unlink()
            if FAST_TRACK_FLAG.exists():
                FAST_TRACK_FLAG.unlink()

    return git_status, git_diag
