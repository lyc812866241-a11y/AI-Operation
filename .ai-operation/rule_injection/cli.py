"""
Command-line entry point for rule_injection.

Runs in two modes:
  - As a module:  python -m rule_injection.cli <cmd> [...]
  - As a script:  python /path/to/cli.py <cmd> [...]

The script mode is what editor hooks invoke -- avoids PYTHONPATH wrestling
across Windows / macOS / Linux.

Usage:
  ... install <adapter>     # wire up editor hook
  ... uninstall <adapter>   # remove editor hook
  ... inject <adapter>      # print rule paper (hot path, called per prompt)
  ... status <adapter>      # report health
  ... list-adapters         # show registry
  ... list-rules            # show registered rules
"""

import argparse
import json
import sys
from pathlib import Path

# Bootstrap sys.path so absolute imports work whether we're invoked as
# `python -m rule_injection.cli` or `python <abs path>/cli.py`.
_FRAMEWORK_DIR = Path(__file__).resolve().parent.parent  # .ai-operation/
if str(_FRAMEWORK_DIR) not in sys.path:
    sys.path.insert(0, str(_FRAMEWORK_DIR))

from rule_injection.base import AdapterError  # noqa: E402
from rule_injection.adapters import REGISTRY, get_adapter  # noqa: E402
from rule_injection.engine import build_paper, list_rules  # noqa: E402


def _cmd_install(args):
    adapter = get_adapter(args.adapter)
    result = adapter.install(dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_uninstall(args):
    adapter = get_adapter(args.adapter)
    result = adapter.uninstall(dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_inject(args):
    """Hot path: this is what gets called on every user prompt.
    Stay quiet on stderr, print only the paper to stdout, exit fast.
    Failures must NOT crash the editor -- emit empty paper, log to stderr.
    """
    try:
        adapter = get_adapter(args.adapter)
        sys.stdout.write(adapter.inject())
        return 0
    except Exception as e:
        # Don't break the editor's prompt flow on a hook failure.
        # Print a minimal stamp so something still arrives, log error to stderr.
        sys.stderr.write(f"[rule_injection] inject failed: {e}\n")
        sys.stdout.write(
            "## [AI-Operation Rule Injection (DEGRADED)]\n"
            f"(injection failed: {e})\n"
            "## [End AI-Operation Rule Injection]\n"
        )
        return 0  # don't surface non-zero, editor would treat as error


def _cmd_status(args):
    adapter = get_adapter(args.adapter)
    result = adapter.status()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result.get("issues") else 1


def _cmd_list_adapters(_args):
    print(json.dumps(sorted(REGISTRY.keys()), indent=2))
    return 0


def _cmd_list_rules(_args):
    rules = [str(p.name) for p in list_rules()]
    print(json.dumps(rules, indent=2, ensure_ascii=False))
    return 0


def main(argv=None):
    # Force UTF-8 stdout/stderr. Windows shells default to cp936/cp1252
    # and mangle Chinese rule text. Editors expect UTF-8 regardless of
    # host shell encoding.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

    parser = argparse.ArgumentParser(prog="rule_injection")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install", help="Wire injection hook into editor")
    p_install.add_argument("adapter", help="adapter name, e.g. claude_code")
    p_install.add_argument("--dry-run", action="store_true")
    p_install.set_defaults(func=_cmd_install)

    p_uninstall = sub.add_parser("uninstall", help="Remove injection hook from editor")
    p_uninstall.add_argument("adapter")
    p_uninstall.add_argument("--dry-run", action="store_true")
    p_uninstall.set_defaults(func=_cmd_uninstall)

    p_inject = sub.add_parser("inject", help="Print rule paper to stdout (hook entry)")
    p_inject.add_argument("adapter")
    p_inject.set_defaults(func=_cmd_inject)

    p_status = sub.add_parser("status", help="Report adapter health")
    p_status.add_argument("adapter")
    p_status.set_defaults(func=_cmd_status)

    p_la = sub.add_parser("list-adapters", help="Show registered adapter names")
    p_la.set_defaults(func=_cmd_list_adapters)

    p_lr = sub.add_parser("list-rules", help="Show registered rule files")
    p_lr.set_defaults(func=_cmd_list_rules)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyError as e:
        sys.stderr.write(f"error: {e}\n")
        return 2
    except AdapterError as e:
        sys.stderr.write(f"adapter error: {e}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())
