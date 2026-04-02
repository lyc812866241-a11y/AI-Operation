"""
Architect Enforcement Tools (AI-Operation Framework)
=====================================================
MCP tools that enforce Level 4 Architect protocols.
All tool names use the `aio__` namespace prefix to avoid conflicts
with user project MCP tools.

The AI cannot bypass these tools. It MUST call them to complete the operation.
This is the "AI creates its own shackles and wears them" mechanism.
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Project map directory - relative to project root
PROJECT_MAP_DIR = Path(".ai-operation/docs/project_map")

# Flag file used to signal pre-commit hook that MCP tool is making the commit
MCP_COMMIT_FLAG = Path(".ai-operation/.mcp_commit_flag")

# Prompt budget limits (inspired by Claude Code internals)
MAX_FILE_CHARS = 4_000       # Max chars per project_map file injected into prompt
MAX_TOTAL_CHARS = 12_000     # Max total chars across all files

# TaskSpec workflow enforcement
TASKSPEC_DIR = Path(".ai-operation/docs")
TASKSPEC_FILE = TASKSPEC_DIR / "taskSpec.md"
TASKSPEC_APPROVED_FLAG = Path(".ai-operation/.taskspec_approved")
FAST_TRACK_FLAG = Path(".ai-operation/.fast_track")

# Two-phase save: prepare writes to staging, confirm writes to actual files
SAVE_STAGING_FILE = Path(".ai-operation/.save_staging.json")


def _set_mcp_flag():
    """Create flag file so git pre-commit hook allows project_map commits."""
    MCP_COMMIT_FLAG.parent.mkdir(parents=True, exist_ok=True)
    MCP_COMMIT_FLAG.write_text("mcp_tool_commit", encoding="utf-8")


def _clear_mcp_flag():
    """Remove flag file after commit."""
    if MCP_COMMIT_FLAG.exists():
        MCP_COMMIT_FLAG.unlink()


def _section_merge(existing_content: str, section_updates: dict) -> tuple:
    """Merge updates into specific sections of a markdown file.

    Reads the file, splits by ## headers, updates only the sections that
    have new content, leaves others untouched.

    Args:
        existing_content: Current file content
        section_updates: Dict of {section_title: new_content_or_SKIP}
            Example: {"可用单元清单": "new table row", "系统定性": "SKIP"}

    Returns:
        (merged_content, list_of_changed_sections)
    """
    import re

    lines = existing_content.split("\n")
    sections = {}  # title → (start_line, end_line, content_lines)
    current_section = None
    current_start = 0

    # Parse file into sections by ## headers
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = (current_start, i, lines[current_start:i])
            # Extract section title (strip ## and numbering like "## 3. ")
            raw_title = line[3:].strip()
            # Remove leading number+dot: "3. 可用单元清单" → "可用单元清单"
            clean_title = re.sub(r'^\d+\.\s*', '', raw_title)
            current_section = clean_title
            current_start = i

    # Last section
    if current_section is not None:
        sections[current_section] = (current_start, len(lines), lines[current_start:])

    if not sections:
        # File has no ## sections — fall back to append
        return existing_content, []

    changed = []
    result_lines = []
    last_end = 0

    # Rebuild file, replacing matched sections
    sorted_sections = sorted(sections.items(), key=lambda x: x[1][0])

    for title, (start, end, original_lines) in sorted_sections:
        # Add any lines between sections (e.g., file header before first ##)
        if start > last_end:
            result_lines.extend(lines[last_end:start])

        # Check if this section has an update
        matched_update = None
        for update_key, update_val in section_updates.items():
            # Fuzzy match: update key is a substring of section title or vice versa
            if (update_key in title or title in update_key or
                    update_key.lower() in title.lower() or title.lower() in update_key.lower()):
                matched_update = update_val
                break

        if matched_update and matched_update.strip().upper() != "SKIP":
            # Keep the ## header line, replace the body
            result_lines.append(original_lines[0])  # ## header
            result_lines.append("")
            result_lines.append(matched_update.strip())
            result_lines.append("")
            changed.append(title)
        else:
            # Keep original section unchanged
            result_lines.extend(original_lines)

        last_end = end

    # Add any trailing content after last section
    if last_end < len(lines):
        result_lines.extend(lines[last_end:])

    return "\n".join(result_lines), changed


DETAILS_DIR = PROJECT_MAP_DIR / "details"
SECTION_SIZE_THRESHOLD = 1500  # chars — split section to subfile if exceeds this


def _auto_split_oversized_sections(filepath: Path, depth: int = 0) -> list:
    """Recursively split oversized ## sections into detail subfiles.

    Level 0: project_map/*.md → details/*.md (## sections)
    Level 1: details/*.md → details/sub/*.md (### sub-sections)
    Level N: keeps splitting as long as sections exceed threshold

    Max depth: 3 (prevents infinite recursion on pathological content).

    Replaces the section body with a pointer: → [详见 details/FILENAME__SECTION.md]
    Writes the full content to the detail subfile.

    Returns: list of sections that were split (with depth indicator).
    """
    import re

    MAX_DEPTH = 3
    if depth > MAX_DEPTH or not filepath.exists():
        return []

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    parent_name = filepath.stem  # e.g. "systemPatterns" or "systemPatterns__可用单元清单"

    # Detect header level based on depth: ## at level 0, ### at level 1, etc.
    header_prefix = "#" * (2 + depth) + " "

    # Parse sections at this header level
    sections = []  # (title, header_line_idx, body_start_idx, body_end_idx)
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

    # Determine output directory based on depth
    if depth == 0:
        out_dir = DETAILS_DIR
    else:
        out_dir = filepath.parent / "sub"
    out_dir.mkdir(parents=True, exist_ok=True)

    split_sections = []
    new_lines = list(lines)
    offset = 0

    for title, header_idx, body_start, body_end in sections:
        body = "\n".join(lines[body_start:body_end]).strip()

        # Skip if already a pointer
        if "→ [详见" in body:
            continue

        if len(body) > SECTION_SIZE_THRESHOLD:
            # Write full content to detail file
            safe_title = re.sub(r'[^\w\u4e00-\u9fff]', '_', title).strip('_')
            detail_filename = f"{parent_name}__{safe_title}.md"
            detail_path = out_dir / detail_filename
            rel_path = detail_path.relative_to(PROJECT_MAP_DIR)
            detail_content = f"{header_prefix}{title}\n\n> 拆分自 {filepath.name}，depth={depth}。\n\n{body}\n"
            detail_path.write_text(detail_content, encoding="utf-8")

            # Replace body in parent with pointer
            pointer = f"\n> {'→' * (depth + 1)} [详见 {rel_path}]\n"
            adj_start = body_start + offset
            adj_end = body_end + offset
            new_lines[adj_start:adj_end] = [pointer]
            offset -= (body_end - body_start - 1)

            split_sections.append(
                f"{'  ' * depth}L{depth}: {title} → {rel_path} ({len(body)} chars)"
            )

            # Recurse: check if the detail file itself has oversized sub-sections
            child_splits = _auto_split_oversized_sections(detail_path, depth + 1)
            split_sections.extend(child_splits)

    if split_sections:
        filepath.write_text("\n".join(new_lines), encoding="utf-8")

    return split_sections


def _compact_dynamic_file(content: str, filename: str) -> str:
    """Compact a dynamic file (activeContext/progress) that has grown too large.

    Strategy: Split by '---' archive entries, keep the file header + last 2 entries,
    replace everything in between with a one-line summary of how many entries were compacted.
    """
    sections = content.split("\n---\n")

    if len(sections) <= 3:
        # Not enough sections to compact
        return content

    # First section is usually the file header (title, instructions)
    header = sections[0]

    # Last 2 sections are the most recent archives
    recent = sections[-2:]

    # Middle sections get compacted
    compacted_count = len(sections) - 3  # -1 header, -2 recent

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    compact_notice = (
        f"\n### [Auto-Compacted — {timestamp}]\n"
        f"{compacted_count} older archive entries were compacted to stay within prompt budget.\n"
        f"Full history is preserved in git log."
    )

    result_parts = [header, compact_notice] + recent
    return "\n---\n".join(result_parts)

# The 6 canonical files in project_map
REQUIRED_FILES = {
    "projectbrief": "projectbrief.md",
    "systemPatterns": "systemPatterns.md",
    "techContext": "techContext.md",
    "activeContext": "activeContext.md",
    "progress": "progress.md",
    "inventory": "inventory.md",
}


def register_architect_tools(mcp: FastMCP, audit_fn=None):
    """Register all architect enforcement tools onto the MCP server instance."""

    def _audit(tool_name: str, status: str, details: str = ""):
        """Log tool call if audit function is provided."""
        if audit_fn:
            audit_fn(tool_name, status, details)

    @mcp.tool()
    def aio__force_architect_save(
        projectbrief_update: str,
        systemPatterns_update: str,
        techContext_update: str,
        activeContext_update: str,
        progress_update: str,
        lessons_learned: str,
        inventory_update: str = "",
        session_compaction: str = "",
    ) -> str:
        """
        [CRITICAL ENFORCEMENT TOOL] Execute the Level 4 Architect Save Protocol.

        This tool MUST be called when the user issues the [存档] command.
        The AI agent MUST NOT manually edit project_map files or run git commands directly.

        CRITICAL: For ALL 5 file parameters, you must EITHER:
          - Provide update content (see format below)
          - Write "NO_CHANGE_BECAUSE: [specific reason]" explaining WHY no update is needed

        Simply writing "NO_CHANGE" is REJECTED. You must justify why each file doesn't need updating.

        SECTION-AWARE MERGE (for static files: projectbrief, systemPatterns, techContext):
        Instead of dumping all content as one blob, use ===SECTION=== delimiters to target
        specific sections. The tool will update ONLY those sections, leaving others untouched.

        Format:
          "可用单元清单\nnew table content here\n===SECTION===\n架构约束\nnew constraint here"

        Each block: first line = section title to match, rest = new content for that section.
        Sections not mentioned are left unchanged. Use SKIP as content to explicitly skip a section.
        If no ===SECTION=== delimiters found, falls back to append mode (backward compatible).

        Args:
            projectbrief_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            systemPatterns_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            techContext_update: Section updates OR "NO_CHANGE_BECAUSE: [reason]"
            activeContext_update: REQUIRED. Current focus + what was done + next steps. Cannot be NO_CHANGE.
            progress_update: REQUIRED. Tasks completed + new TODOs. Cannot be NO_CHANGE.
            lessons_learned: REQUIRED. Lessons from this session. "NONE" only if truly nothing learned.
            inventory_update: Optional but CRITICAL for list data. If this session created, discovered,
                or modified a list of items (skills, modules, APIs, models), provide the COMPLETE LIST
                here. This is FULL OVERWRITE, not append — if you list 40 skills, the file will have
                exactly 40 skills. Always read inventory.md first and merge, don't rely on memory alone.
            session_compaction: Optional. Compressed summary of conversation for context overflow recovery.

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

        _audit("aio__force_architect_save", "CALLED")

        # ── Pre-save sanity check: read current file state ──────────
        # Show AI the current file sizes so it can detect if its update
        # is suspiciously smaller than what's already there
        pre_save_state = {}
        for fn in REQUIRED_FILES.values():
            fp = PROJECT_MAP_DIR / fn
            if fp.exists():
                pre_save_state[fn] = len(fp.read_text(encoding="utf-8"))
            else:
                pre_save_state[fn] = 0

        # Check for suspicious data loss: if an update is content (not NO_CHANGE)
        # but much shorter than a previous update to the same file, warn
        for fn, new_content in updates.items():
            stripped = new_content.strip()
            if stripped.upper().startswith("NO_CHANGE"):
                continue
            old_size = pre_save_state.get(fn, 0)
            new_size = len(stripped)
            # If old file has substantial content and new update is tiny, warn
            if old_size > 500 and new_size < old_size * 0.3:
                _audit("aio__force_architect_save", "WARNING",
                       f"{fn} update ({new_size} chars) much smaller than existing ({old_size} chars)")

        # Validate: NO bare "NO_CHANGE" allowed — must provide reason
        for filename, content in {
            "projectbrief_update": projectbrief_update,
            "systemPatterns_update": systemPatterns_update,
            "techContext_update": techContext_update,
        }.items():
            stripped = content.strip()
            if stripped == "NO_CHANGE":
                _audit("aio__force_architect_save", "REJECTED", f"{filename} bare NO_CHANGE")
                return (
                    f"REJECTED: {filename} cannot be bare 'NO_CHANGE'.\n"
                    f"You must write 'NO_CHANGE_BECAUSE: [reason]' explaining why this file "
                    f"does not need updating based on what happened in this session.\n"
                    f"This forces you to actually review whether the file needs an update.\n\n"
                    f"Examples:\n"
                    f"  NO_CHANGE_BECAUSE: This session only fixed a UI bug, no vision change\n"
                    f"  NO_CHANGE_BECAUSE: No new modules added, only modified existing IngestNode internals\n"
                    f"  NO_CHANGE_BECAUSE: No new dependencies or tech constraints discovered"
                )

        # Validate: activeContext and progress must never be NO_CHANGE at all
        if "NO_CHANGE" in activeContext_update.strip().upper() and "BECAUSE" not in activeContext_update.upper():
            _audit("aio__force_architect_save", "REJECTED", "activeContext was NO_CHANGE")
            return "REJECTED: activeContext_update cannot be NO_CHANGE. You must always update the current focus."
        if "NO_CHANGE" in progress_update.strip().upper() and "BECAUSE" not in progress_update.upper():
            return "REJECTED: progress_update cannot be NO_CHANGE. You must always record what was done this session."
        if not lessons_learned or not lessons_learned.strip():
            return (
                "REJECTED: lessons_learned cannot be empty.\n"
                "Reflect on this session: any bugs hit, user corrections, gotchas discovered, "
                "or preferences expressed? Use 'NONE' only if truly nothing was learned."
            )

        # ══════════════════════════════════════════════════════════
        # PHASE 1: PREPARE — generate diff preview, stage to file
        # Do NOT write to project_map yet. Let AI review first.
        # ══════════════════════════════════════════════════════════
        import json
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        diff_preview = []
        warnings = []
        staged_updates = {}
        skipped_files = []

        for filename, content in updates.items():
            stripped = content.strip()

            if stripped.upper().startswith("NO_CHANGE_BECAUSE:"):
                reason = stripped.split(":", 1)[1].strip() if ":" in stripped else "unspecified"
                skipped_files.append(f"{filename}: {reason[:80]}")
                continue

            filepath = PROJECT_MAP_DIR / filename
            old_content = filepath.read_text(encoding="utf-8") if filepath.exists() else "[file does not exist]"
            old_size = len(old_content)
            new_size = len(stripped)

            # Detect suspicious shrinkage
            if old_size > 500 and new_size < old_size * 0.3:
                warnings.append(
                    f"⚠️ {filename}: new update ({new_size} chars) is much smaller than "
                    f"existing content ({old_size} chars). Possible data loss?"
                )

            # Build diff preview
            diff_preview.append(f"### {filename}")
            diff_preview.append(f"  Current size: {old_size} chars")
            diff_preview.append(f"  Update size:  {new_size} chars")
            diff_preview.append(f"  Update preview: {stripped[:200]}{'...' if len(stripped) > 200 else ''}")
            diff_preview.append("")

            staged_updates[filename] = stripped

        # Stage inventory if provided
        if inventory_update and inventory_update.strip() and inventory_update.strip().upper() != "SKIP":
            inv_path = PROJECT_MAP_DIR / "inventory.md"
            old_inv = inv_path.read_text(encoding="utf-8") if inv_path.exists() else ""
            old_count = old_inv.count("- [") if old_inv else 0
            new_count = inventory_update.count("- ") + inventory_update.count("- [")
            if old_count > 0 and new_count < old_count * 0.5:
                warnings.append(
                    f"⚠️ inventory.md: new list has ~{new_count} items but existing has "
                    f"~{old_count} items. Significant reduction — did you read inventory.md first?"
                )
            staged_updates["inventory.md"] = inventory_update.strip()
            diff_preview.append(f"### inventory.md (OVERWRITE)")
            diff_preview.append(f"  Old items: ~{old_count}")
            diff_preview.append(f"  New items: ~{new_count}")
            diff_preview.append("")

        # Stage lessons
        staged_lessons = lessons_learned.strip()

        # Stage compaction
        staged_compaction = session_compaction.strip() if session_compaction else ""

        # Write staging file
        staging_data = {
            "timestamp": timestamp,
            "updates": staged_updates,
            "skipped": skipped_files,
            "lessons": staged_lessons,
            "compaction": staged_compaction,
        }
        SAVE_STAGING_FILE.parent.mkdir(parents=True, exist_ok=True)
        SAVE_STAGING_FILE.write_text(json.dumps(staging_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Build the review report
        report = ["PENDING_REVIEW: Save prepared but NOT yet written.\n"]
        report.append("## Diff Preview\n")
        report.extend(diff_preview)

        if skipped_files:
            report.append("## Skipped (NO_CHANGE_BECAUSE)\n")
            for s in skipped_files:
                report.append(f"  - {s}")
            report.append("")

        if warnings:
            report.append("## ⚠️ SIZE WARNINGS\n")
            for w in warnings:
                report.append(f"  {w}")
            report.append("")

        report.append(f"## Lessons: {staged_lessons[:150]}")
        report.append("")

        # ── Self-Audit Checklist (forced reflection) ─────────────
        # The AI must answer each question before calling confirm.
        # This uses the current AI's own reasoning — no external API needed.
        report.append("## ⚡ MANDATORY SELF-AUDIT (answer before confirming)\n")
        report.append("You MUST think through each question below. If ANY answer is 'no',")
        report.append("call aio__force_architect_save again with corrected content.\n")

        # Build specific audit questions based on what changed
        audit_questions = []

        # Q1: Data completeness
        for fn, content in staged_updates.items():
            old_size = pre_save_state.get(fn, 0)
            new_size = len(content)
            if old_size > 300 and new_size < old_size * 0.5:
                audit_questions.append(
                    f"⚠️ {fn} is shrinking from {old_size} to {new_size} chars. "
                    f"Did you read the current {fn} before writing? Is anything lost?"
                )

        # Q2: Inventory consistency
        inv_path = PROJECT_MAP_DIR / "inventory.md"
        if inv_path.exists():
            inv_content = inv_path.read_text(encoding="utf-8")
            inv_count = inv_content.count("- [")
            if inv_count > 0:
                audit_questions.append(
                    f"inventory.md currently has {inv_count} items. "
                    f"Did this session discover/create any new items that should be added?"
                )

        # Q3: Skipped file justification
        for s in skipped_files:
            audit_questions.append(
                f"You skipped {s}. Given what happened in this session, "
                f"is this truly unchanged?"
            )

        # Q4: Active context accuracy
        audit_questions.append(
            "Does your activeContext_update accurately describe what JUST happened "
            "and what the IMMEDIATE next step is? Compare it against what you actually "
            "did in this conversation."
        )

        # Q5: Progress accuracy
        audit_questions.append(
            "Does your progress_update list ALL tasks completed this session? "
            "Check: did you create files, modify functions, add dependencies, "
            "or make decisions that aren't reflected?"
        )

        for i, q in enumerate(audit_questions, 1):
            report.append(f"{i}. {q}")
        report.append("")

        report.append(
            "───────────────────────────────────────────\n"
            "After reviewing each question above:\n"
            "  ✅ All correct → call aio__force_architect_save_confirm\n"
            "  ❌ Something wrong → call aio__force_architect_save with fixes"
        )

        _audit("aio__force_architect_save", "PREPARED",
               f"staged={len(staged_updates)}, audit_questions={len(audit_questions)}")
        return "\n".join(report)

    @mcp.tool()
    def aio__force_architect_save_confirm() -> str:
        """
        [PHASE 2: COMMIT] Execute the staged save after AI self-review.

        This tool MUST be called after aio__force_architect_save returns PENDING_REVIEW.
        It reads the staging file, applies all updates, writes lessons, and commits.

        The two-phase save ensures AI reviews the diff before writing:
        Phase 1 (save): validate + generate diff → PENDING_REVIEW
        Phase 2 (confirm): apply writes + git commit → SUCCESS

        Returns:
            Execution report with files updated and git commit status.
        """
        import json
        import datetime

        _audit("aio__force_architect_save_confirm", "CALLED")

        # Read staging file
        if not SAVE_STAGING_FILE.exists():
            return (
                "REJECTED: No staged save found.\n"
                "You must call aio__force_architect_save first to prepare the save."
            )

        staging_data = json.loads(SAVE_STAGING_FILE.read_text(encoding="utf-8"))
        timestamp = staging_data["timestamp"]
        staged_updates = staging_data["updates"]
        staged_lessons = staging_data["lessons"]
        staged_compaction = staging_data.get("compaction", "")

        DYNAMIC_FILE_MAX_BYTES = 3_000
        STATIC_FILES = {"projectbrief.md", "systemPatterns.md", "techContext.md"}
        changed_files = []
        merge_report = []

        for filename, content in staged_updates.items():
            filepath = PROJECT_MAP_DIR / filename

            if filename == "inventory.md":
                # Inventory: full overwrite
                inv_content = (
                    f"# Project Inventory (资产清单)\n\n"
                    f"> 上次更新：{timestamp}\n\n---\n\n"
                    f"{content}\n"
                )
                filepath.write_text(inv_content, encoding="utf-8")
                merge_report.append(f"  {filename}: OVERWRITE")

            elif filename in STATIC_FILES:
                # Static files: section-aware merge
                # AI passes content as "section_title: content" pairs separated by ===SECTION===
                # Or as a single block (falls back to append)
                if filepath.exists() and "===SECTION===" in content:
                    existing = filepath.read_text(encoding="utf-8")
                    # Parse section updates from AI content
                    section_updates = {}
                    for section_block in content.split("===SECTION==="):
                        section_block = section_block.strip()
                        if not section_block:
                            continue
                        # First line is the section title hint
                        lines = section_block.split("\n", 1)
                        if len(lines) == 2:
                            section_updates[lines[0].strip()] = lines[1].strip()
                        else:
                            section_updates[lines[0].strip()] = ""

                    merged, changed_sections = _section_merge(existing, section_updates)
                    filepath.write_text(merged, encoding="utf-8")
                    merge_report.append(
                        f"  {filename}: SECTION MERGE ({len(changed_sections)} sections updated: "
                        f"{', '.join(changed_sections) if changed_sections else 'none'})"
                    )
                elif filepath.exists():
                    # No ===SECTION=== delimiter — append as before (backward compatible)
                    with open(filepath, "a", encoding="utf-8") as f:
                        f.write(f"\n\n---\n### [MCP Auto-Archive]\n{content}\n")
                    merge_report.append(f"  {filename}: APPEND (no section delimiters)")
                else:
                    filepath.write_text(content, encoding="utf-8")
                    merge_report.append(f"  {filename}: CREATED")

            else:
                # Dynamic files (activeContext, progress): compact + append
                if filename in ("activeContext.md", "progress.md") and filepath.exists():
                    existing = filepath.read_text(encoding="utf-8")
                    if len(existing.encode("utf-8")) > DYNAMIC_FILE_MAX_BYTES:
                        compacted = _compact_dynamic_file(existing, filename)
                        filepath.write_text(compacted, encoding="utf-8")

                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(f"\n\n---\n### [MCP Auto-Archive]\n{content}\n")
                merge_report.append(f"  {filename}: APPEND")

            changed_files.append(filename)

        # Auto-split oversized sections to detail subfiles
        split_report = []
        for fn in ["projectbrief.md", "systemPatterns.md", "techContext.md"]:
            fp = PROJECT_MAP_DIR / fn
            splits = _auto_split_oversized_sections(fp)
            if splits:
                split_report.extend(splits)
                if fn not in changed_files:
                    changed_files.append(fn)
        if split_report:
            merge_report.append("  Auto-split oversized sections:")
            for s in split_report:
                merge_report.append(f"    - {s}")

        # Write lessons to corrections.md
        if staged_lessons and staged_lessons.upper() != "NONE":
            corrections_path = PROJECT_MAP_DIR / "corrections.md"
            existing_corrections = corrections_path.read_text(encoding="utf-8") if corrections_path.exists() else ""
            lessons_lines = [l.strip() for l in staged_lessons.split("\n") if l.strip()]

            with open(corrections_path, "a", encoding="utf-8") as f:
                for lesson in lessons_lines:
                    lesson_text = lesson.lstrip("- ").strip()
                    if lesson_text and lesson_text not in existing_corrections:
                        f.write(
                            f"\n---\n"
                            f"DATE: {timestamp}\n"
                            f"CONTEXT: [存档] during development session\n"
                            f"LESSON: {lesson_text}\n"
                            f"COUNT: 1\n"
                        )
            if "corrections.md" not in changed_files:
                changed_files.append("corrections.md")

        # Write compaction summary
        if staged_compaction:
            compaction_path = PROJECT_MAP_DIR / "activeContext.md"
            with open(compaction_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n### [Session Compaction — {timestamp}]\n{staged_compaction}\n")
            if "activeContext.md" not in changed_files:
                changed_files.append("activeContext.md")

        # Clean up staging file
        SAVE_STAGING_FILE.unlink()

        # Git commit
        try:
            _set_mcp_flag()
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            commit_msg = f"chore: architect save [{', '.join(changed_files)}]"
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                check=True, capture_output=True, text=True
            )
            if TASKSPEC_APPROVED_FLAG.exists():
                TASKSPEC_APPROVED_FLAG.unlink()
            if FAST_TRACK_FLAG.exists():
                FAST_TRACK_FLAG.unlink()

            _audit("aio__force_architect_save_confirm", "SUCCESS", f"files={','.join(changed_files)}")
            return (
                f"SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Merge details:\n" + "\n".join(merge_report) + "\n\n"
                f"Git commit: {result.stdout.strip()}\n"
                f"TaskSpec approval cleared — next code change requires new approval."
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, 'stderr') and e.stderr else str(e)
            return (
                f"PARTIAL SUCCESS\n"
                f"Files updated: {', '.join(changed_files)}\n"
                f"Git commit FAILED: {stderr}\n"
                f"Manual commit required."
            )
        finally:
            _clear_mcp_flag()

    @mcp.tool()
    def aio__force_architect_read() -> str:
        """
        [ENFORCEMENT TOOL] Force a full read of all 5 project map files.

        This tool MUST be called when the user issues the [读档] command.
        Returns the full content of all 5 files as a structured context report.
        Applies prompt budget: max 4KB per file, 12KB total to prevent token overflow.
        """
        report = ["# Project Map Full State Report\n"]
        total_chars = 0

        for label, filename in REQUIRED_FILES.items():
            filepath = PROJECT_MAP_DIR / filename
            report.append(f"\n## [{label}] {filename}")
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                # Apply per-file budget
                if len(content) > MAX_FILE_CHARS:
                    content = content[:MAX_FILE_CHARS] + "\n\n[truncated — exceeded 4KB per-file budget]"
                # Check total budget
                if total_chars + len(content) > MAX_TOTAL_CHARS:
                    remaining = MAX_TOTAL_CHARS - total_chars
                    if remaining > 200:
                        content = content[:remaining] + "\n\n[truncated — total 12KB prompt budget reached]"
                    else:
                        content = "[omitted — prompt budget exhausted]"
                total_chars += len(content)
                report.append(content)
            else:
                report.append(f"WARNING: File not found at {filepath}")

        # Discover and append sub-directory rules (rules.d/)
        rules_dir = Path(".ai-operation/rules.d")
        if rules_dir.exists():
            rule_files = sorted(rules_dir.glob("*.md"))
            rule_files = [f for f in rule_files if f.name != "README.md"]
            if rule_files:
                report.append("\n## [Sub-Directory Rules]")
                for rf in rule_files:
                    content = rf.read_text(encoding="utf-8")
                    if len(content) > MAX_FILE_CHARS:
                        content = content[:MAX_FILE_CHARS] + "\n\n[truncated]"
                    if total_chars + len(content) > MAX_TOTAL_CHARS:
                        remaining = MAX_TOTAL_CHARS - total_chars
                        if remaining > 200:
                            content = content[:remaining] + "\n\n[truncated — budget reached]"
                        else:
                            report.append(f"\n### {rf.name}\n[omitted — budget exhausted]")
                            continue
                    total_chars += len(content)
                    report.append(f"\n### {rf.name}\n{content}")

        # ── Auto-Save Reminder ────────────────────────────────────
        # Estimate total project_map size. If growing large, recommend [存档].
        total_map_size = 0
        for filename in REQUIRED_FILES.values():
            fp = PROJECT_MAP_DIR / filename
            if fp.exists():
                total_map_size += fp.stat().st_size

        budget_pct = int(total_chars / MAX_TOTAL_CHARS * 100)
        report.append(f"\n---\nPrompt budget: {total_chars}/{MAX_TOTAL_CHARS} chars ({budget_pct}% used)")
        report.append(f"Project map total size: {total_map_size:,} bytes")

        if budget_pct >= 70:
            report.append(
                f"\n⚠️ WARNING: Prompt budget at {budget_pct}%. "
                f"activeContext.md may be growing too large. "
                f"Consider running [存档] with session_compaction to compress older entries, "
                f"or manually trim activeContext.md via [清理]."
            )
        if total_map_size > 50_000:
            report.append(
                f"\n⚠️ WARNING: Project map total size ({total_map_size:,} bytes) exceeds 50KB. "
                f"Some content may be truncated during [读档]. "
                f"Consider archiving older entries in activeContext.md and progress.md."
            )

        _audit("aio__force_architect_read", "SUCCESS", f"budget={budget_pct}%,size={total_map_size}")
        return "\n".join(report)

    @mcp.tool()
    def aio__force_garbage_collection(confirm: bool = False) -> str:
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

    @mcp.tool()
    def aio__force_project_bootstrap_write(
        projectbrief_content: str,
        systemPatterns_content: str,
        techContext_content: str,
        activeContext_focus: str,
        progress_initial: str,
        user_confirmed: bool,
    ) -> str:
        """
        [BOOTSTRAP ENFORCEMENT TOOL] Merge AI-generated content into project_map templates.

        This tool MUST be called at Phase 4 of the project-bootstrap skill.
        It CANNOT be called unless user_confirmed=True.

        MERGE BEHAVIOR (not overwrite):
        - For the 3 static files (projectbrief, systemPatterns, techContext):
          Reads the existing template, finds [待填写...] placeholders, and replaces
          them with AI-generated content. Template structure (headers, fill instructions,
          examples) is PRESERVED. Unfilled sections keep their [待填写] placeholder.
        - For the 2 dynamic files (activeContext, progress):
          Generated fresh each time (they are session-specific).

        Use "SKIP" for any static file to leave it entirely untouched.
        This enables incremental initialization for large projects.

        Protocol reference: skills/project-bootstrap/SKILL.md (Phase 4)

        Args:
            projectbrief_content: Section fills for projectbrief.md, separated by
                "===SECTION===" delimiter (one fill per [待填写] placeholder, in order).
                Use "SKIP" to leave a section unfilled. Use "SKIP" for the entire param
                to skip this file completely.
            systemPatterns_content: Same format for systemPatterns.md.
            techContext_content: Same format for techContext.md.
            activeContext_focus: Current focus statement for activeContext.md.
            progress_initial: Initial milestone entry for progress.md.
            user_confirmed: MUST be True.

        Returns:
            Execution report with merge results and git commit status.
        """
        import re
        import datetime

        # Gate 1: Enforce user confirmation
        if not user_confirmed:
            return (
                "REJECTED: user_confirmed must be True.\n"
                "You MUST complete Phase 3 (calibration dialogue) and receive explicit user approval "
                "before calling this tool. Do NOT skip the calibration dialogue."
            )

        # Gate 2: Reject [TODO] (but allow SKIP and [待确认])
        for field_name, content in {
            "projectbrief_content": projectbrief_content,
            "systemPatterns_content": systemPatterns_content,
            "techContext_content": techContext_content,
            "activeContext_focus": activeContext_focus,
            "progress_initial": progress_initial,
        }.items():
            if "[TODO]" in content:
                return (
                    f"REJECTED: {field_name} still contains [TODO] placeholders.\n"
                    f"Use [待确认] for uncertain items, or SKIP to leave unfilled."
                )

        # Gate 3: Verify directory exists
        if not PROJECT_MAP_DIR.exists():
            return (
                f"FAILED: Directory {PROJECT_MAP_DIR} does not exist.\n"
                f"Ensure the framework scaffold has been copied into this project correctly."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        merge_report = []

        # ── Merge static files (preserve template structure) ──────────
        def merge_into_template(filepath, ai_content):
            """Replace [待填写...] placeholders in template, preserve everything else."""
            if ai_content.strip().upper() == "SKIP":
                return "SKIPPED"

            if not filepath.exists():
                # No template to merge into — write directly
                filepath.write_text(ai_content.strip(), encoding="utf-8")
                return "WRITTEN (no template found)"

            template = filepath.read_text(encoding="utf-8")

            # Find all [待填写...] placeholders in template
            placeholder_pattern = r'\[待填写[^\]]*\]'
            placeholders = list(re.finditer(placeholder_pattern, template))

            if not placeholders:
                # Template has no placeholders left — full overwrite (re-initialization)
                filepath.write_text(ai_content.strip(), encoding="utf-8")
                return "OVERWRITTEN (no placeholders in template)"

            # Split AI content by section delimiter
            sections = re.split(r'===SECTION===', ai_content)

            # Replace placeholders one-by-one, in order
            result = template
            filled_count = 0
            skipped_count = 0

            for i, match in enumerate(placeholders):
                if i < len(sections):
                    section_content = sections[i].strip()
                    if section_content.upper() == "SKIP" or not section_content:
                        skipped_count += 1
                        continue
                    # Replace this specific placeholder with AI content
                    result = result.replace(match.group(), section_content, 1)
                    filled_count += 1
                else:
                    skipped_count += 1

            # Update timestamp
            result = re.sub(
                r'\[由 `\[初始化项目\]` 写入日期\]',
                timestamp,
                result
            )
            result = re.sub(
                r'\[由 `\[存档\]` 写入日期和变更摘要\]',
                f"{timestamp} — bootstrap merge",
                result
            )

            filepath.write_text(result, encoding="utf-8")
            return f"MERGED ({filled_count} filled, {skipped_count} kept as template)"

        static_files = {
            "projectbrief.md": projectbrief_content,
            "systemPatterns.md": systemPatterns_content,
            "techContext.md": techContext_content,
        }

        written_files = []
        for filename, content in static_files.items():
            filepath = PROJECT_MAP_DIR / filename
            try:
                status = merge_into_template(filepath, content)
                merge_report.append(f"  {filename}: {status}")
                if status != "SKIPPED":
                    written_files.append(filename)
            except Exception as e:
                return f"FAILED: Could not process {filename}: {e}"

        # ── Generate dynamic files (always fresh) ─────────────────────
        if activeContext_focus.strip().upper() != "SKIP":
            active_path = PROJECT_MAP_DIR / "activeContext.md"
            active_path.write_text(
                f"# 当前工作焦点 (Active Context)\n\n"
                f"> 由 project-bootstrap 技能初始化于 {timestamp}\n\n"
                f"## 1. 当前焦点 (Current Focus)\n\n{activeContext_focus.strip()}\n\n"
                f"## 2. 正在处理的问题 (Active Issues)\n\n- 无\n\n"
                f"## 3. 即将执行的下一步 (Immediate Next Steps)\n\n"
                f"1. 检查所有 [待确认] 标注的字段，逐一确认或修正\n"
                f"2. 与用户确认第一个 taskSpec.md 的范围\n\n"
                f"> 上次更新时间：{timestamp}",
                encoding="utf-8"
            )
            written_files.append("activeContext.md")
            merge_report.append("  activeContext.md: GENERATED")
        else:
            merge_report.append("  activeContext.md: SKIPPED")

        if progress_initial.strip().upper() != "SKIP":
            progress_path = PROJECT_MAP_DIR / "progress.md"
            progress_path.write_text(
                f"# 进度与里程碑 (Progress)\n\n"
                f"> 由 project-bootstrap 技能初始化于 {timestamp}\n\n"
                f"## 已完成里程碑\n\n"
                f"- [{timestamp}] 项目接管完成，project_map 初始化\n\n"
                f"## 当前待办\n\n{progress_initial.strip()}\n\n"
                f"## 已知风险\n\n- 无",
                encoding="utf-8"
            )
            written_files.append("progress.md")
            merge_report.append("  progress.md: GENERATED")
        else:
            merge_report.append("  progress.md: SKIPPED")

        if not written_files:
            return "WARNING: All files were SKIPPED. No changes made."

        # ── Count remaining placeholders ──────────────────────────────
        remaining = 0
        for filename in ["projectbrief.md", "systemPatterns.md", "techContext.md"]:
            filepath = PROJECT_MAP_DIR / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                remaining += len(re.findall(r'\[待填写[^\]]*\]', content))

        # ── Git commit ────────────────────────────────────────────────
        try:
            _set_mcp_flag()
            subprocess.run(["git", "add", str(PROJECT_MAP_DIR)], check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"chore: bootstrap project map [{timestamp}]"],
                check=True, capture_output=True, text=True
            )
            return (
                f"SUCCESS: Project bootstrap merge complete.\n\n"
                f"Merge report:\n" + "\n".join(merge_report) + "\n\n"
                f"Remaining [待填写] placeholders: {remaining}\n"
                f"{'Re-run [初始化项目] to fill remaining sections.' if remaining > 0 else 'All sections filled!'}\n\n"
                f"Git commit: {result.stdout.strip()}\n\n"
                f"Next step: Run [读档] to verify the initialized state."
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            return (
                f"PARTIAL SUCCESS: Files merged but git commit failed.\n\n"
                f"Merge report:\n" + "\n".join(merge_report) + "\n\n"
                f"Remaining [待填写] placeholders: {remaining}\n"
                f"Git error: {stderr}\n"
                f"Manual commit required."
            )
        finally:
            _clear_mcp_flag()

    @mcp.tool()
    def aio__force_architect_report(
        files_modified: str,
        why: str,
        architecture_impact: str,
        next_steps: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Generate a structured Architect report.

        This tool MUST be called when the user issues the [汇报] command.
        The AI MUST NOT provide a free-form report — it must fill all 4 sections.

        Args:
            files_modified: List of files modified in this session (one per line).
            why: Explanation of why these changes were made.
            architecture_impact: How these changes affect the system architecture.
            next_steps: Exact next steps to take.

        Returns:
            Formatted architect report.
        """
        # Validate: no empty fields
        for field_name, value in {
            "files_modified": files_modified,
            "why": why,
            "architecture_impact": architecture_impact,
            "next_steps": next_steps,
        }.items():
            if not value or not value.strip():
                return f"REJECTED: {field_name} cannot be empty. All 4 report sections are mandatory."

        # Read current project state for context
        state_summary = ""
        active_ctx = PROJECT_MAP_DIR / "activeContext.md"
        if active_ctx.exists():
            state_summary = active_ctx.read_text(encoding="utf-8")[:500]

        report = (
            f"# Architect Report\n\n"
            f"## 1. Files Modified\n{files_modified.strip()}\n\n"
            f"## 2. Why\n{why.strip()}\n\n"
            f"## 3. Architecture Impact\n{architecture_impact.strip()}\n\n"
            f"## 4. Next Steps\n{next_steps.strip()}\n\n"
            f"---\n"
            f"### Current Context (from activeContext.md)\n{state_summary}\n"
        )

        return f"SUCCESS\n\n{report}"

    @mcp.tool()
    def aio__force_test_runner(
        test_target: str,
        test_command: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Run isolated module tests with mandatory pre-cleanup.

        This tool MUST be called when the user issues the [执行测试] command.
        It enforces:
        1. Automatic cleanup of dirty data and temp files BEFORE testing
        2. Tests run in isolation (single module/node, not full pipeline)
        3. Results are captured and returned as structured output

        Args:
            test_target: Which module or node to test (e.g., "IngestNode", "tests/test_ingest.py").
            test_command: The exact command to run (e.g., "python -m pytest tests/test_ingest.py -v").

        Returns:
            Test execution report with pre-cleanup results and test output.
        """
        import glob
        import os

        if not test_target or not test_target.strip():
            return "REJECTED: test_target cannot be empty. Specify which module to test."
        if not test_command or not test_command.strip():
            return "REJECTED: test_command cannot be empty. Specify the exact test command."

        # Gate: Reject full pipeline commands
        pipeline_keywords = ["--all", "full_pipeline", "run_all", "test_everything"]
        for kw in pipeline_keywords:
            if kw in test_command.lower():
                return (
                    f"REJECTED: Full pipeline testing is forbidden. "
                    f"Detected '{kw}' in test_command. Run tests node-by-node."
                )

        report_parts = ["# Test Execution Report\n"]
        report_parts.append(f"## Target: {test_target.strip()}\n")

        # Step 1: Pre-cleanup
        cleanup_patterns = [
            "*.temp", "temp_*.py", "debug_*.py",
            "tests/output/*.tmp", "tests/output/*.temp",
        ]
        cleaned = []
        for pattern in cleanup_patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                    cleaned.append(f)
                except OSError:
                    pass
            for f in glob.glob(f"**/{pattern}", recursive=True):
                try:
                    os.remove(f)
                    cleaned.append(f)
                except OSError:
                    pass

        if cleaned:
            report_parts.append(f"## Pre-Cleanup\nRemoved {len(cleaned)} temp files:\n")
            for f in sorted(set(cleaned)):
                report_parts.append(f"  - {f}\n")
        else:
            report_parts.append("## Pre-Cleanup\nNo temp files found. Environment clean.\n")

        # Step 2: Run the test
        report_parts.append(f"\n## Test Command\n```\n{test_command.strip()}\n```\n")

        try:
            result = subprocess.run(
                test_command.strip().split(),
                capture_output=True,
                text=True,
                timeout=300,
            )
            report_parts.append(f"\n## Exit Code: {result.returncode}\n")

            if result.stdout:
                stdout_trimmed = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
                report_parts.append(f"\n## STDOUT\n```\n{stdout_trimmed}\n```\n")
            if result.stderr:
                stderr_trimmed = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                report_parts.append(f"\n## STDERR\n```\n{stderr_trimmed}\n```\n")

            status = "PASSED" if result.returncode == 0 else "FAILED"
            return f"{status}\n\n" + "".join(report_parts)

        except subprocess.TimeoutExpired:
            return "FAILED: Test timed out after 300 seconds.\n\n" + "".join(report_parts)
        except FileNotFoundError:
            return (
                f"FAILED: Command not found. Verify the test command is correct.\n"
                f"Command: {test_command.strip()}\n\n" + "".join(report_parts)
            )

    # ═══════════════════════════════════════════════════════════════
    # TaskSpec Workflow Enforcement (升级第 1 层软约束为硬约束)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    def aio__force_taskspec_submit(
        task_goal: str,
        scope_and_impact: str,
        files_to_modify: str,
        technical_constraints: str,
        acceptance_criteria: str,
        doc_impact: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Submit a taskSpec draft for user approval.

        This tool MUST be called in Phase 1 (LEAD/Architect) before any code changes.
        The AI MUST NOT write, edit, or execute any code before calling this tool.

        After calling this tool, the AI must wait for user approval. Only after
        the user approves should the AI call aio__force_taskspec_approve.

        Args:
            task_goal: One sentence describing the core purpose of this task.
            scope_and_impact: Which modules/nodes are affected.
            files_to_modify: Exact list of files to change and what to change.
            technical_constraints: Limitations (dependencies, performance, isolation).
            acceptance_criteria: Specific test steps to verify completion.
            doc_impact: Which project_map docs need updating. "NONE" if no impact.

        Returns:
            The formatted taskSpec for user review.
        """
        import datetime

        _audit("aio__force_taskspec_submit", "CALLED", task_goal[:100] if task_goal else "")

        # Validate: all fields must be non-empty
        fields = {
            "task_goal": task_goal,
            "scope_and_impact": scope_and_impact,
            "files_to_modify": files_to_modify,
            "technical_constraints": technical_constraints,
            "acceptance_criteria": acceptance_criteria,
            "doc_impact": doc_impact,
        }
        for name, value in fields.items():
            if not value or not value.strip():
                return f"REJECTED: {name} cannot be empty. All 6 taskSpec sections are mandatory."

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Build the taskSpec document
        spec_content = (
            f"# Task Specification\n\n"
            f"> Generated: {timestamp}\n"
            f"> Status: **PENDING APPROVAL**\n\n"
            f"## 1. Task Goal\n{task_goal.strip()}\n\n"
            f"## 2. Scope & Impact\n{scope_and_impact.strip()}\n\n"
            f"## 3. Files to Modify\n{files_to_modify.strip()}\n\n"
            f"## 4. Technical Constraints\n{technical_constraints.strip()}\n\n"
            f"## 5. Acceptance Criteria\n{acceptance_criteria.strip()}\n\n"
            f"## 6. Architecture Doc Impact\n{doc_impact.strip()}\n"
        )

        # Write the taskSpec file
        TASKSPEC_DIR.mkdir(parents=True, exist_ok=True)
        TASKSPEC_FILE.write_text(spec_content, encoding="utf-8")

        # Clear any previous approval flag
        if TASKSPEC_APPROVED_FLAG.exists():
            TASKSPEC_APPROVED_FLAG.unlink()

        return (
            f"SUCCESS: TaskSpec submitted for approval.\n\n"
            f"{spec_content}\n"
            f"---\n"
            f"⏸ Waiting for user approval. Do NOT write any code until approved.\n"
            f"After user says '批准/approved/ok go', call aio__force_taskspec_approve."
        )

    @mcp.tool()
    def aio__force_taskspec_approve(
        user_said: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Record user approval of the current taskSpec.

        This tool MUST be called after the user explicitly approves the taskSpec.
        It creates the approval flag that the git pre-commit hook checks before
        allowing code commits.

        Without this flag, git commits that modify project code files will be BLOCKED
        by the pre-commit hook.

        Args:
            user_said: The exact approval message from the user (e.g., "批准", "approved").

        Returns:
            Approval confirmation with execution permission granted.
        """
        _audit("aio__force_taskspec_approve", "CALLED", user_said[:50] if user_said else "")
        # Gate 1: taskSpec file must exist
        if not TASKSPEC_FILE.exists():
            return (
                "REJECTED: No taskSpec found.\n"
                "You must call aio__force_taskspec_submit first to create a taskSpec."
            )

        # Gate 2: user_said must contain an approval signal
        approval_signals = ["批准", "approved", "ok go", "执行", "ok", "go", "yes", "可以", "同意"]
        if not any(signal in user_said.lower() for signal in approval_signals):
            return (
                f"REJECTED: '{user_said}' does not look like an approval.\n"
                f"Expected one of: {', '.join(approval_signals)}"
            )

        # Gate 3: Check this isn't a stale approval (taskSpec must be PENDING)
        spec_content = TASKSPEC_FILE.read_text(encoding="utf-8")
        if "PENDING APPROVAL" not in spec_content:
            return (
                "REJECTED: taskSpec is not in PENDING state.\n"
                "Submit a new taskSpec with aio__force_taskspec_submit first."
            )

        # Mark as approved
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Update taskSpec status
        updated_spec = spec_content.replace(
            "**PENDING APPROVAL**",
            f"**APPROVED** ({timestamp}, user: {user_said.strip()[:50]})"
        )
        TASKSPEC_FILE.write_text(updated_spec, encoding="utf-8")

        # Create approval flag for pre-commit hook
        TASKSPEC_APPROVED_FLAG.write_text(
            f"approved|{timestamp}|{user_said.strip()[:50]}",
            encoding="utf-8"
        )

        return (
            f"SUCCESS: TaskSpec APPROVED.\n"
            f"Approval recorded at {timestamp}.\n"
            f"You may now proceed to Phase 2 (WORKER) — write code per the approved spec.\n"
            f"The approval flag has been created. Git commits will be allowed.\n\n"
            f"Reminder: Execute ONLY what the taskSpec specifies. No extra changes."
        )

    @mcp.tool()
    def aio__force_fast_track(
        reason: str,
        change_description: str,
    ) -> str:
        """
        [ENFORCEMENT TOOL] Declare a fast-track change (skip taskSpec).

        Use this for trivial changes that qualify for fast-track exemption.
        The threshold is DYNAMIC based on trust score:
        - Low trust (recent corrections): < 3 lines, single file only
        - Normal trust: < 5 lines, single file
        - High trust (5+ clean saves): < 10 lines, single file

        This creates a temporary flag that allows one commit without a full taskSpec.
        The flag is single-use and cleared after the next commit.

        Args:
            reason: Why this qualifies for fast-track (must be specific).
            change_description: What exactly will be changed (file + change).

        Returns:
            Fast-track permission granted, with trust level shown.
        """
        import datetime
        import re

        _audit("aio__force_fast_track", "CALLED", reason[:80] if reason else "")

        if not reason or not reason.strip():
            return "REJECTED: reason cannot be empty. Explain why this qualifies for fast-track."
        if not change_description or not change_description.strip():
            return "REJECTED: change_description cannot be empty. Specify what will be changed."

        # ── Trust Score Calculation ──────────────────────────────────
        # Read corrections.md to assess recent error frequency
        corrections_path = PROJECT_MAP_DIR / "corrections.md"
        recent_corrections = 0
        consecutive_clean_saves = 0

        if corrections_path.exists():
            content = corrections_path.read_text(encoding="utf-8")
            # Count corrections from last 30 days
            dates = re.findall(r"DATE: (\d{4}-\d{2}-\d{2})", content)
            now = datetime.datetime.now()
            for d in dates:
                try:
                    dt = datetime.datetime.strptime(d, "%Y-%m-%d")
                    if (now - dt).days <= 30:
                        recent_corrections += 1
                except ValueError:
                    pass

        # Check recent saves — count NONE lessons as "clean saves"
        if corrections_path.exists():
            content = corrections_path.read_text(encoding="utf-8")
            entries = content.split("---")
            # Count consecutive entries from the end that are clean
            for entry in reversed(entries):
                if "LESSON:" in entry and "NONE" not in entry.upper():
                    break
                if "LESSON:" in entry:
                    consecutive_clean_saves += 1

        # Determine trust level and threshold
        if recent_corrections >= 3:
            trust_level = "LOW"
            max_lines = 3
            trust_reason = f"{recent_corrections} corrections in last 30 days"
        elif consecutive_clean_saves >= 5:
            trust_level = "HIGH"
            max_lines = 10
            trust_reason = f"{consecutive_clean_saves} consecutive clean saves"
        else:
            trust_level = "NORMAL"
            max_lines = 5
            trust_reason = "default threshold"

        # Validate change size against trust-adjusted threshold
        lines_mentioned = change_description.count("\n") + 1
        if lines_mentioned > max_lines:
            _audit("aio__force_fast_track", "REJECTED", f"trust={trust_level}, lines={lines_mentioned}>{max_lines}")
            return (
                f"REJECTED: Change too large for fast-track at current trust level.\n"
                f"Trust: {trust_level} ({trust_reason})\n"
                f"Max lines: {max_lines}, your change: {lines_mentioned} lines\n"
                f"Use aio__force_taskspec_submit instead."
            )

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        FAST_TRACK_FLAG.write_text(
            f"fast_track|{timestamp}|{reason.strip()[:100]}",
            encoding="utf-8"
        )

        _audit("aio__force_fast_track", "SUCCESS", f"trust={trust_level}")
        return (
            f"SUCCESS: Fast-track permission granted.\n"
            f"Trust level: {trust_level} ({trust_reason})\n"
            f"Threshold: < {max_lines} lines\n"
            f"⚡ Fast-track: {reason.strip()}\n"
            f"Change: {change_description.strip()[:200]}\n\n"
            f"You may proceed. Remember to run [存档] after completion."
        )

    # ═══════════════════════════════════════════════════════════════
    # Real-Time Inventory (实时追加，解决 AI 上下文丢失问题)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    def aio__inventory_append(
        category: str,
        item: str,
    ) -> str:
        """
        [REAL-TIME PERSISTENCE TOOL] Immediately append one item to inventory.md.

        Call this tool THE MOMENT you discover, create, or decompose a new item
        (skill, module, API endpoint, data model, etc). Do NOT wait for [存档].

        WHY: If you discover 40 skills across a long conversation, your context
        window may only remember the last 10 by save time. By appending each
        item immediately when discovered, ALL items are persisted regardless
        of context window limits.

        This tool does NOT require taskSpec approval — it is a write-ahead log,
        not a code change.

        Args:
            category: The inventory category (e.g., "Skills", "API Endpoints", "Data Models").
            item: One-line description of the item. Include name and key details.
                  Example: "scene_detect — 从视频中检测场景切换点，输入 video_path，输出 List[Timestamp]"

        Returns:
            Confirmation with current count in that category.
        """
        import datetime

        if not category or not category.strip():
            return "REJECTED: category cannot be empty."
        if not item or not item.strip():
            return "REJECTED: item cannot be empty."

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        inventory_path = PROJECT_MAP_DIR / "inventory.md"

        # Read existing content
        existing = ""
        if inventory_path.exists():
            existing = inventory_path.read_text(encoding="utf-8")

        # If file doesn't exist or is empty, create with header
        if not existing.strip():
            existing = (
                f"# Project Inventory (资产清单)\n\n"
                f"> 本文件为实时追加模式。每发现一个资产立即写入，不等 [存档]。\n"
                f"> 定期运行 [整理清单] 去重整理。\n"
            )

        # Check if this exact item already exists (prevent duplicates)
        item_text = item.strip()
        if item_text in existing:
            # Count items in this category
            cat_count = existing.count(f"[{category.strip()}]")
            return f"SKIPPED: Item already exists in inventory. Category '{category.strip()}' has {cat_count} items."

        # Append the item
        entry = f"- [{category.strip()}] {item_text}  _(added {timestamp})_\n"

        with open(inventory_path, "a", encoding="utf-8") as f:
            f.write(entry)

        # Count items in this category after append
        updated = inventory_path.read_text(encoding="utf-8")
        cat_count = updated.count(f"[{category.strip()}]")
        total_count = updated.count("- [")

        _audit("aio__inventory_append", "SUCCESS", f"cat={category.strip()}, total={total_count}")
        return (
            f"SUCCESS: Appended to inventory.\n"
            f"Category: {category.strip()} ({cat_count} items)\n"
            f"Total inventory: {total_count} items\n"
            f"Item: {item_text[:100]}"
        )

    @mcp.tool()
    def aio__inventory_consolidate() -> str:
        """
        [MAINTENANCE TOOL] Read, deduplicate, and organize inventory.md.

        Call this when inventory has accumulated many entries and needs cleanup.
        Reads all entries, groups by category, removes exact duplicates,
        sorts alphabetically within each category, and rewrites the file.

        This is the "整理" step after many "追加" steps.

        Returns:
            Consolidation report with category counts.
        """
        import datetime

        inventory_path = PROJECT_MAP_DIR / "inventory.md"
        if not inventory_path.exists():
            return "SKIPPED: inventory.md does not exist. Nothing to consolidate."

        content = inventory_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Extract all inventory entries (lines starting with "- [")
        entries = {}  # category → set of items
        non_entry_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- [") and "]" in stripped:
                # Parse category and item
                bracket_end = stripped.index("]")
                category = stripped[3:bracket_end]
                item_part = stripped[bracket_end+1:].strip()
                # Remove timestamp suffix if present
                if "_(added " in item_part:
                    item_part = item_part[:item_part.index("_(added ")].strip()
                if category not in entries:
                    entries[category] = set()
                entries[category].add(item_part)
            else:
                if not stripped.startswith(">") and stripped != "---" and not stripped.startswith("# "):
                    continue  # Skip old headers/metadata

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        # Rebuild file grouped by category
        output = [
            "# Project Inventory (资产清单)\n",
            f"> 上次整理：{timestamp}",
            f"> 本文件为实时追加模式。每发现一个资产立即写入，不等 [存档]。",
            "> 定期运行 aio__inventory_consolidate 去重整理。\n",
        ]

        total = 0
        for category in sorted(entries.keys()):
            items = sorted(entries[category])
            output.append(f"## {category} ({len(items)} items)\n")
            for item in items:
                output.append(f"- {item}")
            output.append("")
            total += len(items)

        inventory_path.write_text("\n".join(output), encoding="utf-8")

        report_lines = [f"SUCCESS: Inventory consolidated."]
        report_lines.append(f"Total: {total} items across {len(entries)} categories\n")
        for cat in sorted(entries.keys()):
            report_lines.append(f"  {cat}: {len(entries[cat])} items")

        _audit("aio__inventory_consolidate", "SUCCESS", f"total={total}")
        return "\n".join(report_lines)

    # ═══════════════════════════════════════════════════════════════
    # Hierarchical Detail Retrieval (分级检索)
    # ═══════════════════════════════════════════════════════════════

    @mcp.tool()
    def aio__detail_read(
        detail_file: str,
    ) -> str:
        """
        [RETRIEVAL TOOL] Read a detail subfile that was split from a project_map file.

        When [读档] returns a section containing "→ [详见 details/xxx.md]",
        call this tool to read the full content of that section.

        This enables hierarchical retrieval: parent files stay small (within
        prompt budget), detail files hold the full content, read on demand.

        Args:
            detail_file: Filename in the details directory (e.g., "systemPatterns__可用单元清单.md").
                         Do NOT include the full path — just the filename.

        Returns:
            Full content of the detail file.
        """
        # Search in details/ and details/sub/ (multi-level)
        detail_path = DETAILS_DIR / detail_file
        if not detail_path.exists():
            detail_path = DETAILS_DIR / "sub" / detail_file

        if not detail_path.exists():
            # List all available files across all levels
            available = []
            if DETAILS_DIR.exists():
                available.extend(f.name for f in DETAILS_DIR.glob("*.md"))
                sub_dir = DETAILS_DIR / "sub"
                if sub_dir.exists():
                    available.extend(f"sub/{f.name}" for f in sub_dir.glob("*.md"))
            return (
                f"FAILED: Detail file '{detail_file}' not found.\n"
                f"Available: {', '.join(sorted(available)) if available else 'none'}"
            )

        content = detail_path.read_text(encoding="utf-8")
        _audit("aio__detail_read", "SUCCESS", detail_file)

        return (
            f"# Detail: {detail_file}\n"
            f"Size: {len(content)} chars\n\n"
            f"{content}"
        )

    @mcp.tool()
    def aio__detail_list() -> str:
        """
        [RETRIEVAL TOOL] List all detail subfiles and their sizes.

        Use this to see what sections have been split out of parent files.

        Returns:
            List of detail files with sizes.
        """
        if not DETAILS_DIR.exists():
            return "No details directory found. No sections have been split yet."

        files = sorted(DETAILS_DIR.glob("*.md"))
        if not files:
            return "Details directory exists but is empty. No sections have been split yet."

        report = ["# Detail Files (分级子文件)\n"]
        total_size = 0
        for f in files:
            size = f.stat().st_size
            total_size += size
            report.append(f"  - {f.name} ({size:,} bytes)")

        report.append(f"\nTotal: {len(files)} files, {total_size:,} bytes")
        return "\n".join(report)
