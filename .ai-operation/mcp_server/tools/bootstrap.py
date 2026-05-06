"""
Bootstrap tools -- project initialization/bootstrap write.
Contains: aio__force_project_bootstrap_write
"""

import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import *


def register_bootstrap_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register bootstrap-related tools onto the MCP server instance."""

    @mcp.tool()
    def aio__force_project_bootstrap_write(
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
        - For the 2 static files (systemPatterns, techContext):
          Reads the existing template, finds [待填写...] placeholders, and replaces
          them with AI-generated content. Template structure (headers, fill instructions,
          examples) is PRESERVED. Unfilled sections keep their [待填写] placeholder.
        - For the 2 dynamic files (activeContext, progress):
          Generated fresh each time (they are session-specific).

        Use "SKIP" for any static file to leave it entirely untouched.
        This enables incremental initialization for large projects.

        Protocol reference: skills/project-bootstrap/SKILL.md (Phase 4)

        Args:
            systemPatterns_content: Section fills for systemPatterns.md, separated by
                "===SECTION===" delimiter (one fill per [待填写] placeholder, in order).
                Use "SKIP" to leave a section unfilled or for the entire param.
            techContext_content: Same format for techContext.md.
            activeContext_focus: Current focus statement for activeContext.md.
            progress_initial: Initial milestone entry for progress.md.
            user_confirmed: MUST be True.

        议题 #009 重组:conventions 删除,并入 corrections(scope=单项目)。
        议题 #010 重组:projectbrief 删除,vision/negative_scope 由 design.md §1/§2 接管(单一来源)。
        项目契约在后续 [存档] 中通过 corrections_update §1 段填入。
        wisdom.md(跨项目通用智慧)由人主动编辑,不通过 bootstrap 写入。

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
        gate2_fields = {
            "systemPatterns_content": systemPatterns_content,
            "techContext_content": techContext_content,
            "activeContext_focus": activeContext_focus,
            "progress_initial": progress_initial,
        }
        for field_name, content in gate2_fields.items():
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

        # -- Merge static files (preserve template structure) ----------
        def merge_into_template(filepath, ai_content):
            """Replace [待填写...] placeholders in template, preserve everything else."""
            if ai_content.strip().upper() == "SKIP":
                return "SKIPPED"

            if not filepath.exists():
                # No template to merge into -- write directly
                filepath.write_text(ai_content.strip(), encoding="utf-8")
                return "WRITTEN (no template found)"

            template = filepath.read_text(encoding="utf-8")

            # Find all [待填写...] placeholders in template
            placeholder_pattern = r'\[待填写[^\]]*\]'
            placeholders = list(re.finditer(placeholder_pattern, template))

            if not placeholders:
                # Template has no placeholders left -- full overwrite (re-initialization)
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
                f"{timestamp} -- bootstrap merge",
                result
            )

            filepath.write_text(result, encoding="utf-8")
            return f"MERGED ({filled_count} filled, {skipped_count} kept as template)"

        # 议题 #009: conventions 已删除;corrections 由后续 [存档] 填入(立项时只生成空模板)
        # 议题 #010: projectbrief 已删除;vision 在 design.md §1/§2(由 project-design skill 写入)
        static_files = {
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

        # -- Generate dynamic files (always fresh) ---------------------
        # 议题 #009: 新 5 段格式(taskSpec 边界 / 内部状态 / 决策 / 卡点 / 下一动作)
        # 由 state-checkpoint skill 维护,**OVERWRITE 模式**,≤ 80 行硬上限
        if activeContext_focus.strip().upper() != "SKIP":
            active_path = PROJECT_MAP_DIR / "activeContext.md"
            active_path.write_text(
                f"# activeContext\n\n"
                f"> [DYNAMIC] 议题 #002 The Engine 的物质载体。**OVERWRITE 模式**(快照,非日志)。\n"
                f"> 由 `skills/state-checkpoint/` 维护,不要手写。**≤ 80 行硬上限**。\n\n"
                f"**最后更新**: {timestamp}\n"
                f"**当前 taskSpec**: 立项中(未创建)\n\n"
                f"---\n\n"
                f"## 1. taskSpec 边界(粗粒度时间尺度)\n\n"
                f"- **上一个完成**: 无(项目刚立项)\n"
                f"- **当前**: 立项验收\n"
                f"- **下一个(预期)**: 第一个功能开发 taskSpec\n\n"
                f"## 2. 当前 taskSpec 内部状态(细粒度时间尺度)\n\n"
                f"- **子步骤**: 1/N — 立项 + project_map 初始化\n"
                f"- **打开的关键文件**:\n"
                f"  - .ai-operation/docs/project_map/systemPatterns.md\n"
                f"  - .ai-operation/docs/project_map/techContext.md\n\n"
                f"## 3. 本会话已做的关键决策\n\n"
                f"- 项目接管完成 — 由 project-bootstrap 技能于 {timestamp} 初始化\n\n"
                f"## 4. 当前卡点\n\n"
                f"- 无\n\n"
                f"## 5. 下一个具体动作\n\n"
                f"{activeContext_focus.strip()}\n",
                encoding="utf-8"
            )
            written_files.append("activeContext.md")
            merge_report.append("  activeContext.md: GENERATED (5-section format, 议题 #009)")
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

        # -- Count remaining placeholders ------------------------------
        remaining = 0
        for filename in ["systemPatterns.md", "techContext.md"]:
            filepath = PROJECT_MAP_DIR / filename
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                remaining += len(re.findall(r'\[待填写[^\]]*\]', content))

        # -- Git commit (non-blocking, same approach as save_confirm) ----
        git_status = "not attempted"
        try:
            _set_mcp_flag()
            files_to_add = [str(PROJECT_MAP_DIR / wf) for wf in written_files if (PROJECT_MAP_DIR / wf).exists()]
            if files_to_add:
                add_proc = subprocess.Popen(
                    ["git", "add"] + files_to_add,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                try:
                    add_proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    add_proc.kill()
                    add_proc.wait()

                if add_proc.returncode == 0:
                    commit_proc = subprocess.Popen(
                        ["git", "commit", "--no-verify", "--no-status", "-m",
                         f"chore: bootstrap project map [{timestamp}]", "--"] + files_to_add,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    try:
                        commit_proc.wait(timeout=30)
                        git_status = "committed" if commit_proc.returncode == 0 else f"exit {commit_proc.returncode}"
                    except subprocess.TimeoutExpired:
                        commit_proc.kill()
                        commit_proc.wait()
                        git_status = "commit timed out"
                else:
                    git_status = "git add failed"
        except Exception as e:
            git_status = f"error: {str(e)[:100]}"
        finally:
            _clear_mcp_flag()

        return (
            f"SUCCESS: Project bootstrap merge complete.\n\n"
            f"Merge report:\n" + "\n".join(merge_report) + "\n\n"
            f"Remaining [待填写] placeholders: {remaining}\n"
            f"{'Re-run [初始化项目] to fill remaining sections.' if remaining > 0 else 'All sections filled!'}\n\n"
            f"Git: {git_status}\n"
            f"{'Run git commit manually if needed.' if git_status != 'committed' else ''}\n"
            f"Next step: Run [读档] to verify the initialized state."
        )
