"""
Bypass & Monitor framework — structured rule enforcement with audit trail.

Contains: aio__bypass_violation, has_bypass, clear_bypass, clear_all_bypasses,
          is_monitor_rule, set_rule_monitor, set_rule_active

Four-state enforcement model (inspired by Harness):
  REJECTED    — hard block, must fix, cannot bypass
  BYPASSABLE  — violation detected, user can authorize bypass with reason
  MONITOR     — violation detected, logged but NOT blocked (observation mode)
  SUCCESS     — passed all checks

Monitor mode: new rules start in MONITOR → see how often they'd fire →
user decides to promote to BYPASSABLE/REJECTED. Safer rule rollout.

Bypass flow: BYPASSABLE → user says "绕过" → aio__bypass_violation →
single-use flag → next submit skips that rule → flag consumed.
"""

import json
import datetime
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import BYPASS_DIR

MONITOR_FILE = Path(".ai-operation/.monitor_rules.json")


def _load_monitor_rules() -> set:
    """Load the set of rules in monitor mode."""
    if not MONITOR_FILE.exists():
        return set()
    try:
        data = json.loads(MONITOR_FILE.read_text(encoding="utf-8"))
        return set(data.get("rules", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def _save_monitor_rules(rules: set):
    """Persist monitor rules set."""
    MONITOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    MONITOR_FILE.write_text(
        json.dumps({"rules": sorted(rules)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_monitor_rule(rule_code: str) -> bool:
    """Check if a rule is in monitor mode (log-only, no block)."""
    return rule_code in _load_monitor_rules()


def set_rule_monitor(rule_code: str):
    """Put a rule into monitor mode."""
    rules = _load_monitor_rules()
    rules.add(rule_code)
    _save_monitor_rules(rules)


def set_rule_active(rule_code: str):
    """Promote a rule from monitor to active (enforce)."""
    rules = _load_monitor_rules()
    rules.discard(rule_code)
    _save_monitor_rules(rules)


def has_bypass(rule_code: str) -> bool:
    """Check if a specific rule has been bypassed."""
    flag = BYPASS_DIR / f"{rule_code}.bypass"
    return flag.exists()


def clear_bypass(rule_code: str):
    """Clear a single bypass flag (consumed after use)."""
    flag = BYPASS_DIR / f"{rule_code}.bypass"
    if flag.exists():
        flag.unlink()


def clear_all_bypasses():
    """Clear all bypass flags (called after successful submit/commit)."""
    if BYPASS_DIR.exists():
        for flag in BYPASS_DIR.glob("*.bypass"):
            flag.unlink()


def register_bypass_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register bypass tools onto the MCP server instance."""

    @mcp.tool()
    def aio__bypass_violation(
        rule_code: str,
        user_said: str,
    ) -> str:
        """
        [GOVERNANCE TOOL] Record user-authorized bypass of a BYPASSABLE rule violation.

        This tool may ONLY be called when:
        1. A previous tool returned BYPASSABLE for a specific rule
        2. The user explicitly authorized the bypass (said "绕过", "bypass", etc.)

        The bypass is single-use: it applies to the next submit/commit only,
        then the flag is consumed. All other rules still apply.

        Every bypass is recorded in audit.log with the user's reason.

        Args:
            rule_code: The rule code from the BYPASSABLE response
                       (e.g., "taskspec.files_to_modify_vague")
            user_said: The user's exact words authorizing the bypass

        Returns:
            SUCCESS with bypass recorded, or REJECTED if conditions not met.
        """
        _audit("aio__bypass_violation", "CALLED", f"rule={rule_code}")

        loop_msg = _loop_guard("aio__bypass_violation", rule_code)
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        # Validate rule_code format
        if not rule_code or not rule_code.strip():
            return "REJECTED: rule_code cannot be empty."

        # Validate user authorization signal
        bypass_signals = [
            "绕过", "bypass", "跳过", "skip", "override",
            "放行", "允许", "ok", "go", "yes", "可以",
        ]
        if not any(signal in user_said.lower() for signal in bypass_signals):
            return (
                f"REJECTED: '{user_said}' does not look like bypass authorization.\n"
                f"The user must explicitly say one of: {', '.join(bypass_signals)}"
            )

        # Rate limit: same rule can only be bypassed once per 24 hours
        flag = BYPASS_DIR / f"{rule_code.strip()}.bypass"
        if flag.exists():
            try:
                existing = json.loads(flag.read_text(encoding="utf-8"))
                last_ts = datetime.datetime.strptime(existing["ts"], "%Y-%m-%d %H:%M:%S")
                age_hours = (datetime.datetime.now() - last_ts).total_seconds() / 3600
                if age_hours < 24:
                    _audit("aio__bypass_violation", "REJECTED", f"rate_limit: {rule_code} bypassed {age_hours:.1f}h ago")
                    return (
                        f"REJECTED: Rule '{rule_code}' was already bypassed {age_hours:.1f} hours ago.\n"
                        f"Each rule can only be bypassed once per 24 hours.\n"
                        f"Wait {24 - age_hours:.1f} more hours, or fix the underlying issue."
                    )
            except (json.JSONDecodeError, KeyError, ValueError):
                pass  # Corrupted flag — allow re-bypass

        # Write per-rule bypass flag
        BYPASS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        flag.write_text(
            json.dumps({
                "rule": rule_code.strip(),
                "reason": user_said.strip()[:200],
                "ts": timestamp,
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        _audit(
            "aio__bypass_violation", "BYPASS_GRANTED",
            f"rule={rule_code}, reason={user_said.strip()[:100]}"
        )

        return (
            f"SUCCESS: Bypass granted for rule '{rule_code}'.\n"
            f"Reason: {user_said.strip()[:200]}\n"
            f"Recorded at {timestamp}.\n\n"
            f"This bypass is single-use — it applies to the next submit only.\n"
            f"All other rules still apply. Proceed with your operation."
        )

    @mcp.tool()
    def aio__rule_monitor(
        rule_code: str,
        action: str,
    ) -> str:
        """
        [GOVERNANCE TOOL] Toggle a rule between monitor and active mode.

        Monitor mode: rule checks still run, violations are LOGGED to audit.log
        but NOT blocked. Use this to observe a new rule's impact before enforcing it.

        Active mode: rule violations are enforced (REJECTED or BYPASSABLE).

        Args:
            rule_code: The rule code (e.g., "taskspec.files_to_modify_vague")
            action: "monitor" to enable observation mode, "active" to enforce

        Returns:
            Confirmation of mode change.
        """
        _audit("aio__rule_monitor", "CALLED", f"rule={rule_code}, action={action}")

        if not rule_code or not rule_code.strip():
            return "REJECTED: rule_code cannot be empty."

        action = action.strip().lower()
        if action not in ("monitor", "active"):
            return "REJECTED: action must be 'monitor' or 'active'."

        if action == "monitor":
            set_rule_monitor(rule_code.strip())
            _audit("aio__rule_monitor", "SET_MONITOR", rule_code)
            return (
                f"SUCCESS: Rule '{rule_code}' is now in MONITOR mode.\n"
                f"Violations will be logged to audit.log but will NOT block execution.\n"
                f"Use action='active' to start enforcing."
            )
        else:
            set_rule_active(rule_code.strip())
            _audit("aio__rule_monitor", "SET_ACTIVE", rule_code)
            return (
                f"SUCCESS: Rule '{rule_code}' is now ACTIVE.\n"
                f"Violations will be enforced (REJECTED or BYPASSABLE)."
            )
