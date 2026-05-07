"""
Skill state machine — physical enforcement for file-modifying skills.

议题 #013(skill 物理强制):routine skills 不再是"AI 可以读了不执行"的纯文档,
而是被 aio__skill_invoke / aio__skill_complete 包夹的强制流程。
- invoke 时锁定,记录 primary_artifact + start_time
- complete 时验证 primary_artifact 在锁定期被修改过
- 否则视为 skill 没真正执行,拒绝释放锁
- 议题 #004 物理强制原则在 skill 层的彻底落地

参与 skill(在 SKILL.md frontmatter 声明 primary_artifact):
- lesson-distill   → corrections.md
- state-checkpoint → activeContext.md
- omm-scan         → systemPatterns.md
"""

import json
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .constants import _parse_skill_frontmatter

SKILL_LOCK_FILE = Path(".ai-operation/.skill_active.json")
SKILL_LOCK_TTL = 3600  # 1 hour 自动释放(防遗忘锁死)


def _read_active_lock():
    """Return active lock dict or None. Auto-clear stale locks."""
    if not SKILL_LOCK_FILE.exists():
        return None
    try:
        data = json.loads(SKILL_LOCK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    age = time.time() - data.get("start_time", 0)
    if age > SKILL_LOCK_TTL:
        try:
            SKILL_LOCK_FILE.unlink()
        except Exception:
            pass
        return None
    return data


def is_skill_active() -> bool:
    """Public helper for other modules to check if a skill is in progress."""
    return _read_active_lock() is not None


def register_skill_lock_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register skill state-machine tools."""

    @mcp.tool()
    def aio__skill_invoke(skill_name: str) -> str:
        """
        [SKILL STATE MACHINE] 锁定一个 skill 的执行,直到 aio__skill_complete 调用才释放。

        议题 #013 物理强制:任何在 SKILL.md frontmatter 声明了 primary_artifact 的 skill,
        必须用 invoke / complete 包裹执行。aio__skill_complete 会验证 primary_artifact
        在 invoke 之后真的被改过——没改 = skill 没真正执行 = 拒绝释放锁。

        约束:
        - 同时只能有一个 skill 处于 active 状态(锁互斥)
        - 锁 TTL 1 小时,超过自动清除(防遗忘锁死)
        - skill 完成后必须调 aio__skill_complete 释放锁

        Args:
            skill_name: skill 目录名(例:'lesson-distill', 'state-checkpoint', 'omm-scan')

        Returns:
            SUCCESS:锁获得,附 primary_artifact 信息
            REJECTED:已有其他 skill active,或 skill 不存在
        """
        _audit("aio__skill_invoke", "CALLED", skill_name)

        active = _read_active_lock()
        if active and active.get("skill_name") != skill_name:
            return (
                f"REJECTED: skill '{active['skill_name']}' is already active "
                f"(started at {time.strftime('%H:%M:%S', time.localtime(active['start_time']))}).\n"
                f"Call aio__skill_complete('{active['skill_name']}') first."
            )

        skill_md = Path(f".ai-operation/skills/{skill_name}/SKILL.md")
        if not skill_md.exists():
            _audit("aio__skill_invoke", "FAILED", f"skill not found: {skill_name}")
            return (
                f"FAILED: skill '{skill_name}' not found at {skill_md}.\n"
                f"Check available skills via [读档]'s 'Available Skills' section."
            )

        meta = _parse_skill_frontmatter(skill_md)
        primary = meta.get("primary_artifact", "").strip()

        if not primary:
            return (
                f"NOTE: skill '{skill_name}' has no primary_artifact declared.\n"
                f"Lock acquired but completion verification will be soft (mtime check skipped).\n"
                f"Add `primary_artifact: <path>` to SKILL.md frontmatter for strict enforcement."
            )

        # Capture pre-execution mtime so we can verify modification later
        artifact_path = Path(primary)
        pre_mtime = artifact_path.stat().st_mtime if artifact_path.exists() else 0

        SKILL_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "skill_name": skill_name,
            "start_time": time.time(),
            "primary_artifact": primary,
            "pre_mtime": pre_mtime,
            "description": meta.get("description", ""),
        }
        SKILL_LOCK_FILE.write_text(
            json.dumps(lock_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        _audit("aio__skill_invoke", "SUCCESS", f"{skill_name}|{primary}")
        return (
            f"SUCCESS: skill '{skill_name}' invoked.\n"
            f"  Primary artifact: {primary}\n"
            f"  Description: {meta.get('description', '(none)')[:120]}\n\n"
            f"You MUST call aio__skill_complete('{skill_name}') after finishing.\n"
            f"On complete, the tool verifies '{primary}' was modified during this lock window.\n"
            f"If you don't modify it, completion will be REJECTED."
        )

    @mcp.tool()
    def aio__skill_complete(skill_name: str) -> str:
        """
        [SKILL STATE MACHINE] 释放 skill 执行锁,验证 primary_artifact 被修改。

        议题 #013 强制核心:验证 primary_artifact 的 mtime 在 skill_invoke 之后,
        证明 skill 真的修改了应该修改的文件——没修改 = skill 没真正执行。

        Args:
            skill_name: skill 目录名(必须匹配当前 active 的 skill)

        Returns:
            SUCCESS:验证通过,锁释放
            REJECTED:无 active skill / 名称不匹配 / primary_artifact 未被修改
        """
        _audit("aio__skill_complete", "CALLED", skill_name)

        active = _read_active_lock()
        if not active:
            return (
                "REJECTED: no skill is currently active.\n"
                "Did you forget to call aio__skill_invoke first?"
            )
        if active.get("skill_name") != skill_name:
            return (
                f"REJECTED: active skill is '{active['skill_name']}', not '{skill_name}'.\n"
                f"Either complete that one first, or call aio__skill_complete with its real name."
            )

        primary = active.get("primary_artifact", "").strip()
        pre_mtime = active.get("pre_mtime", 0)
        start_time = active.get("start_time", 0)

        # If skill declared no primary_artifact, soft completion
        if not primary:
            try:
                SKILL_LOCK_FILE.unlink()
            except Exception:
                pass
            _audit("aio__skill_complete", "SOFT", skill_name)
            return (
                f"SUCCESS (soft): skill '{skill_name}' completed.\n"
                f"No primary_artifact declared — no mtime verification."
            )

        # Verify primary artifact was modified
        artifact_path = Path(primary)
        if not artifact_path.exists():
            _audit("aio__skill_complete", "REJECTED", f"{skill_name}|artifact missing")
            return (
                f"REJECTED: primary artifact '{primary}' does not exist after skill execution.\n"
                f"The skill should have created or modified this file. Lock NOT released."
            )

        post_mtime = artifact_path.stat().st_mtime
        if post_mtime <= pre_mtime:
            _audit(
                "aio__skill_complete", "REJECTED",
                f"{skill_name}|not modified|pre={pre_mtime} post={post_mtime}",
            )
            return (
                f"REJECTED: primary artifact '{primary}' was NOT modified during skill execution.\n"
                f"  pre-invoke mtime:  {time.strftime('%H:%M:%S', time.localtime(pre_mtime))}\n"
                f"  current mtime:     {time.strftime('%H:%M:%S', time.localtime(post_mtime))}\n"
                f"  skill started at:  {time.strftime('%H:%M:%S', time.localtime(start_time))}\n\n"
                f"Did you skip the skill steps? Lock NOT released — re-execute the skill,\n"
                f"actually modify the file, then call aio__skill_complete again."
            )

        # All good — release lock
        try:
            SKILL_LOCK_FILE.unlink()
        except Exception:
            pass

        _audit("aio__skill_complete", "SUCCESS", f"{skill_name}|{primary}")
        elapsed = int(time.time() - start_time)
        return (
            f"SUCCESS: skill '{skill_name}' completed in {elapsed}s.\n"
            f"  Primary artifact '{primary}' verified modified during lock window.\n"
            f"  Lock released."
        )
