"""
Skillify — extract reusable SKILL.md from audit.log patterns.
Contains: aio__extract_skill
"""

import json
import re
from collections import Counter
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


AUDIT_LOG_PATH = Path(".ai-operation/audit.log")
SKILLS_DIR = Path(".ai-operation/skills")


def register_skillify_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register skillify tools onto the MCP server instance."""

    @mcp.tool()
    def aio__extract_skill(
        skill_name: str,
        description: str,
        last_n_entries: int = 50,
    ) -> str:
        """
        [EXTRACTION TOOL] Extract a reusable SKILL.md from recent audit.log patterns.

        Analyzes the last N audit log entries to identify operation patterns:
        - Which tools were called and in what order
        - Which files were touched
        - What the common workflow sequence looks like

        Generates a SKILL.md draft with frontmatter, placed in skills/{skill_name}/.
        The skill is in PENDING_REVIEW state — user must confirm before it's active.

        Args:
            skill_name: Name for the new skill (lowercase, hyphenated, e.g., "api-migration")
            description: One-line description of what this skill does
            last_n_entries: How many recent audit entries to analyze (default 50)

        Returns:
            PENDING_REVIEW with the generated SKILL.md content for user review.
        """
        _audit("aio__extract_skill", "CALLED", f"name={skill_name}")

        loop_msg = _loop_guard("aio__extract_skill", skill_name)
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # Validate skill_name
        if not skill_name or not re.match(r'^[a-z][a-z0-9-]*$', skill_name):
            return (
                "REJECTED: skill_name must be lowercase, hyphenated, start with a letter.\n"
                "Example: 'api-migration', 'data-cleanup', 'deploy-check'"
            )

        # Check for duplicates
        target_dir = SKILLS_DIR / skill_name
        if target_dir.exists():
            return (
                f"REJECTED: Skill '{skill_name}' already exists at {target_dir}.\n"
                "Choose a different name or manually delete the existing skill first."
            )

        # Read audit log
        if not AUDIT_LOG_PATH.exists():
            return "REJECTED: No audit.log found. Cannot extract patterns without history."

        lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").strip().split("\n")
        recent = lines[-last_n_entries:] if len(lines) > last_n_entries else lines

        # Parse audit entries
        tool_sequence = []
        files_touched = Counter()
        tool_counts = Counter()

        for line in recent:
            try:
                entry = json.loads(line)
                tool = entry.get("tool", "")
                status = entry.get("status", "")
                details = entry.get("details", "")

                if tool and status in ("CALLED", "SUCCESS"):
                    tool_sequence.append(tool)
                    tool_counts[tool] += 1

                    # Extract file paths from details
                    file_matches = re.findall(r'[\w./\\-]+\.\w{1,5}', details)
                    for f in file_matches:
                        if not f.startswith("."):  # skip hidden files
                            files_touched[f] += 1
            except (json.JSONDecodeError, KeyError):
                continue

        if not tool_sequence:
            return "REJECTED: No usable audit entries found. Work on the project first, then extract."

        # Analyze patterns
        top_tools = tool_counts.most_common(10)
        top_files = files_touched.most_common(10)

        # Detect workflow phases (consecutive tool sequences)
        phases = []
        current_phase = []
        for tool in tool_sequence:
            if tool.startswith("aio__"):
                if current_phase:
                    phases.append(current_phase)
                current_phase = [tool]
            else:
                current_phase.append(tool)
        if current_phase:
            phases.append(current_phase)

        # Infer trigger keywords from description
        when_keywords = [w for w in re.findall(r'[\u4e00-\u9fff]+|[a-z]{3,}', description.lower()) if len(w) >= 2][:5]

        # Infer paths from touched files
        path_patterns = set()
        for f, _ in top_files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                path_patterns.add(f"{parts[0]}/**")
            ext = f.rsplit(".", 1)[-1] if "." in f else ""
            if ext:
                path_patterns.add(f"*.{ext}")

        # Build SKILL.md content
        when_yaml = json.dumps(when_keywords, ensure_ascii=False)
        paths_yaml = json.dumps(sorted(path_patterns)[:5], ensure_ascii=False)

        tool_list = "\n".join(f"  - {tool} ({count}x)" for tool, count in top_tools)
        file_list = "\n".join(f"  - {f} ({count}x)" for f, count in top_files)

        # Summarize phases
        phase_summary = ""
        for i, phase in enumerate(phases[:5], 1):
            phase_summary += f"\n### Phase {i}\n"
            for tool in phase[:5]:
                phase_summary += f"  1. {tool}\n"

        skill_content = (
            f"---\n"
            f"name: {skill_name}\n"
            f"description: {description}\n"
            f"when: {when_yaml}\n"
            f"paths: {paths_yaml}\n"
            f"tools: [\"Bash\", \"Read\", \"Edit\"]\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"> Auto-extracted from audit.log ({len(recent)} entries analyzed).\n"
            f"> **Status: PENDING_REVIEW** — review and edit before using.\n\n"
            f"## Description\n\n{description}\n\n"
            f"## Observed Tool Usage\n\n{tool_list}\n\n"
            f"## Files Commonly Touched\n\n{file_list}\n\n"
            f"## Workflow Phases (observed){phase_summary}\n\n"
            f"---\n\n"
            f"## TODO: Manual Refinement\n\n"
            f"- [ ] Review and edit the workflow phases above\n"
            f"- [ ] Add specific instructions for each phase\n"
            f"- [ ] Add guard rails and red flags\n"
            f"- [ ] Remove this TODO section when done\n"
        )

        # Write to disk
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        _audit("aio__extract_skill", "SUCCESS",
               f"name={skill_name}, tools={len(top_tools)}, files={len(top_files)}, phases={len(phases)}")

        return (
            f"PENDING_REVIEW: Skill '{skill_name}' extracted to {target_dir}/SKILL.md\n\n"
            f"Based on {len(recent)} audit entries:\n"
            f"  - {len(top_tools)} distinct tools used\n"
            f"  - {len(top_files)} files touched\n"
            f"  - {len(phases)} workflow phases detected\n\n"
            f"Preview:\n{skill_content}\n\n"
            f"---\n"
            f"Review the generated SKILL.md. Edit as needed, then remove the PENDING_REVIEW line.\n"
            f"The skill will appear in [读档] output once frontmatter is finalized."
        )
