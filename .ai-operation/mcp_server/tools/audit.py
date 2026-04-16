"""
Audit tools -- programmatic verification of project_map claims against actual code.

Contains: aio__audit_project_map

This tool closes the "AI self-validates its own claims" gap in bootstrap.
Instead of trusting AI to say "现有内容准确", it runs code-level checks:
  1. File existence -- do claimed paths actually exist?
  2. Decorator count -- does the actual count match inventory?
  3. Dependency truth -- are claimed libraries actually imported?
  4. Naming consistency -- do conventions match real code?
  5. Config parsing -- do .env / docker-compose match techContext?
"""

import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import _budget_truncate

# Directories to skip when scanning code
SKIP_DIRS = {
    ".git", ".ai-operation", "__pycache__", "node_modules", ".venv", "venv",
    ".env", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".eggs", "*.egg-info",
}

MAX_SCAN_FILES = 500  # Safety cap for file scanning


def _iter_code_files(root: Path, extensions: set = None) -> list:
    """Walk project tree, skip vendor/build dirs, return code file paths."""
    if extensions is None:
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java"}
    files = []
    for p in root.rglob("*"):
        if len(files) >= MAX_SCAN_FILES:
            break
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        if p.is_file() and p.suffix in extensions:
            files.append(p)
    return files


def _extract_paths_from_md(content: str) -> list:
    """Extract file/directory paths from markdown content.

    Filters out API endpoint paths (v1/chat, oapi/topapi/...) and framework paths.
    """
    # Match paths like core/llm_client.py, plugins/pm_workflow_skills.py, etc.
    pattern = r'(?:^|\s|`|/)([a-zA-Z_][\w./-]*\.(?:py|js|ts|jsx|tsx|go|rs|java|yaml|yml|json|toml|sh|ps1|sql|css|html))'
    paths = re.findall(pattern, content)

    # Filter out false positives
    filtered = []
    api_prefixes = ("v1/", "v1.", "v2/", "v2.", "oapi/", "api/", "http", "www.")
    framework_prefixes = (".ai-operation/skills/", ".ai-operation/mcp_server/")
    for p in paths:
        p_lower = p.lower()
        # Skip API endpoint paths
        if any(p_lower.startswith(prefix) for prefix in api_prefixes):
            continue
        # Skip framework internal paths
        if any(p_lower.startswith(prefix) for prefix in framework_prefixes):
            continue
        # Skip paths that look like URL fragments (contain /v1.0/, /oapi/, etc.)
        if "/v1" in p_lower or "/oapi/" in p_lower or "/topapi/" in p_lower:
            continue
        filtered.append(p)

    return list(set(filtered))


def _resolve_path(root: Path, claimed_path: str) -> Path | None:
    """Try to resolve a claimed path against the project root.

    Strategy:
    1. Try exact path relative to root
    2. Try common subdirectories (one level deep)
    3. Try glob search by filename (last resort)
    """
    # Normalize
    claimed = claimed_path.replace("\\", "/").strip("/")

    # 1. Exact match
    candidate = root / claimed
    if candidate.exists():
        return candidate

    # 2. Try subdirectories (common patterns: src/, lib/, agent_core/, app/)
    for subdir in root.iterdir():
        if subdir.is_dir() and subdir.name not in SKIP_DIRS:
            candidate = subdir / claimed
            if candidate.exists():
                return candidate

    # 3. Glob by filename (only for files, not dirs)
    if not claimed.endswith("/"):
        filename = Path(claimed).name
        matches = list(root.glob(f"**/{filename}"))
        # Filter out matches in skip dirs
        matches = [m for m in matches if not any(s in m.parts for s in SKIP_DIRS)]
        if len(matches) == 1:
            return matches[0]

    return None


def _check_file_existence(root: Path, files: dict) -> dict:
    """Check 1: Verify file paths in systemPatterns/inventory actually exist."""
    all_claimed = []
    for fname in ["systemPatterns.md", "inventory.md"]:
        if fname in files:
            all_claimed.extend(_extract_paths_from_md(files[fname]))

    if not all_claimed:
        return {
            "name": "Check 1: File Existence",
            "status": "SKIP",
            "detail": "No file paths found in systemPatterns.md or inventory.md to verify."
        }

    # Deduplicate and filter trivial paths
    claimed_set = set()
    for p in all_claimed:
        p = p.strip("/")
        # Skip very short paths or just extensions
        if len(p) > 5 and "/" in p:
            claimed_set.add(p)

    found = []
    missing = []
    for cp in sorted(claimed_set):
        resolved = _resolve_path(root, cp)
        if resolved:
            found.append(cp)
        else:
            missing.append(cp)

    total = len(found) + len(missing)
    if not missing:
        status = "PASS"
    elif len(missing) / total < 0.1:
        status = "WARN"
    else:
        status = "FAIL"

    detail_lines = [f"Checked {total} file paths from systemPatterns.md + inventory.md"]
    detail_lines.append(f"Found: {len(found)}/{total}")
    if missing:
        detail_lines.append(f"Missing ({len(missing)}):")
        for m in missing[:20]:  # Cap output
            detail_lines.append(f"  - {m}")
        if len(missing) > 20:
            detail_lines.append(f"  ... and {len(missing) - 20} more")

    return {"name": "Check 1: File Existence", "status": status, "detail": "\n".join(detail_lines)}


def _check_decorator_count(root: Path, files: dict) -> dict:
    """Check 2: Verify decorator/tool count matches inventory claims."""
    inv_content = files.get("inventory.md", "")
    if not inv_content:
        return {
            "name": "Check 2: Decorator/Tool Count",
            "status": "SKIP",
            "detail": "inventory.md not found."
        }

    # Extract claimed tool total from inventory
    # Strategy: count unique tool function names (tool_xxx) in inventory.
    # This is more reliable than regex for total numbers, which can match
    # version numbers (V18) or permission counts (26个) by accident.
    claimed_total = None
    tool_names_in_inv = set(re.findall(r'(tool_\w+)', inv_content))
    if tool_names_in_inv:
        claimed_total = len(tool_names_in_inv)

    # Auto-detect decorator pattern from systemPatterns or inventory
    decorator_pattern = "@enterprise_tool"
    sp_content = files.get("systemPatterns.md", "")
    for pattern_candidate in ["@enterprise_tool", "@app.route", "@mcp.tool", "@tool"]:
        if pattern_candidate in inv_content or pattern_candidate in sp_content:
            decorator_pattern = pattern_candidate
            break

    # Count actual decorators in code (only lines starting with @, not mentions in docstrings)
    code_files = _iter_code_files(root, {".py"})
    actual_count = 0
    per_file = {}
    for cf in code_files:
        try:
            content = cf.read_text(encoding="utf-8", errors="ignore")
            # Count lines where the decorator appears as an actual decorator
            count = len(re.findall(
                rf'^\s*{re.escape(decorator_pattern)}',
                content, re.MULTILINE
            ))
            if count > 0:
                rel = str(cf.relative_to(root))
                per_file[rel] = count
                actual_count += count
        except Exception:
            continue

    detail_lines = [f"Decorator pattern: `{decorator_pattern}`"]
    detail_lines.append(f"Actual count in code: {actual_count} across {len(per_file)} files")
    if claimed_total is not None:
        detail_lines.append(f"Inventory claimed total: {claimed_total}")
        diff = actual_count - claimed_total
        if diff != 0:
            detail_lines.append(f"Discrepancy: {'+' if diff > 0 else ''}{diff}")
    else:
        detail_lines.append("Could not extract claimed total from inventory.md")

    # Per-file breakdown (top 10)
    if per_file:
        detail_lines.append("Top files:")
        for f, c in sorted(per_file.items(), key=lambda x: -x[1])[:10]:
            detail_lines.append(f"  {f}: {c}")

    if claimed_total is None:
        status = "WARN"
    elif actual_count == claimed_total:
        status = "PASS"
    elif abs(actual_count - claimed_total) <= 2:
        status = "WARN"
    else:
        status = "FAIL"

    return {"name": "Check 2: Decorator/Tool Count", "status": status, "detail": "\n".join(detail_lines)}


def _check_dependency_truth(root: Path, files: dict) -> dict:
    """Check 3: Verify claimed dependencies are actually imported in code."""
    tc_content = files.get("techContext.md", "")
    sp_content = files.get("systemPatterns.md", "")
    combined = tc_content + "\n" + sp_content

    if not combined.strip():
        return {
            "name": "Check 3: Dependency Truth",
            "status": "SKIP",
            "detail": "techContext.md and systemPatterns.md not found."
        }

    # Extract claimed libraries/frameworks from tech stack
    # Common pattern: library names in backticks, table cells, or explicit mentions
    known_libs = {
        "openai": ["import openai", "from openai"],
        "langchain": ["import langchain", "from langchain"],
        "langgraph": ["import langgraph", "from langgraph"],
        "fastapi": ["import fastapi", "from fastapi"],
        "flask": ["import flask", "from flask"],
        "django": ["import django", "from django"],
        "chromadb": ["import chromadb", "from chromadb"],
        "milvus": ["import pymilvus", "from pymilvus"],
        "apscheduler": ["import apscheduler", "from apscheduler"],
        "pyyaml": ["import yaml", "from yaml"],
        "requests": ["import requests", "from requests"],
        "httpx": ["import httpx", "from httpx"],
        "aiohttp": ["import aiohttp", "from aiohttp"],
        "sqlalchemy": ["import sqlalchemy", "from sqlalchemy"],
        "pydantic": ["import pydantic", "from pydantic"],
        "numpy": ["import numpy", "from numpy"],
        "pandas": ["import pandas", "from pandas"],
        "torch": ["import torch", "from torch"],
        "tensorflow": ["import tensorflow", "from tensorflow"],
        "beautifulsoup4": ["import bs4", "from bs4"],
        "selenium": ["import selenium", "from selenium"],
        "playwright": ["import playwright", "from playwright"],
    }

    # Find which libs are mentioned in project_map
    claimed_present = {}  # lib -> True (claimed used) or False (claimed NOT used)
    for lib in known_libs:
        if lib.lower() in combined.lower():
            # Check if it's an explicit negative claim -- must be in same sentence/line
            # Pattern: "零 X 依赖" or "不使用 X" or "no X dependency" -- X must be adjacent
            neg_patterns = [
                rf'零\s*{lib}',           # "零LangChain" -- directly adjacent
                rf'不.*使用\s*{lib}',      # "不使用LangChain"
                rf'no\s+{lib}',           # "no LangChain"
                rf'without\s+{lib}',      # "without LangChain"
                rf'零.*{lib}.*依赖',      # "零 LangChain/LangGraph 依赖"
            ]
            is_negative = any(re.search(p, combined, re.IGNORECASE) for p in neg_patterns)
            if is_negative:
                claimed_present[lib] = False
            else:
                claimed_present[lib] = True

    if not claimed_present:
        return {
            "name": "Check 3: Dependency Truth",
            "status": "SKIP",
            "detail": "No recognizable library claims found in techContext/systemPatterns."
        }

    # Scan code for actual imports
    code_files = _iter_code_files(root, {".py", ".js", ".ts"})
    all_code = ""
    for cf in code_files:
        try:
            all_code += cf.read_text(encoding="utf-8", errors="ignore") + "\n"
        except Exception:
            continue

    # Also check requirements.txt / package.json
    req_content = ""
    for req_file in ["requirements.txt", "pyproject.toml", "package.json"]:
        req_path = root / req_file
        if not req_path.exists():
            # Try subdirectories
            matches = list(root.glob(f"**/{req_file}"))
            matches = [m for m in matches if not any(s in m.parts for s in SKIP_DIRS)]
            if matches:
                req_path = matches[0]
        if req_path.exists():
            try:
                req_content += req_path.read_text(encoding="utf-8", errors="ignore") + "\n"
            except Exception:
                pass

    issues = []
    verified = []

    for lib, claimed_used in claimed_present.items():
        import_patterns = known_libs.get(lib, [f"import {lib}", f"from {lib}"])
        actually_imported = any(p in all_code for p in import_patterns)
        in_requirements = lib.lower() in req_content.lower()

        if claimed_used and not actually_imported and not in_requirements:
            issues.append(f"CLAIMED but NOT FOUND: `{lib}` -- no import in code, not in requirements")
        elif claimed_used and not actually_imported and in_requirements:
            issues.append(f"WARN: `{lib}` in requirements but never imported -- unused dependency?")
        elif not claimed_used and actually_imported:
            issues.append(f"CLAIMED ABSENT but FOUND: `{lib}` -- import exists in code despite negative claim")
        else:
            verified.append(lib)

    detail_lines = [f"Checked {len(claimed_present)} library claims"]
    if verified:
        detail_lines.append(f"Verified: {', '.join(verified)}")
    if issues:
        detail_lines.append("Issues:")
        for issue in issues:
            detail_lines.append(f"  - {issue}")

    if not issues:
        status = "PASS"
    elif any("CLAIMED ABSENT but FOUND" in i or "CLAIMED but NOT FOUND" in i for i in issues):
        status = "FAIL"
    else:
        status = "WARN"

    return {"name": "Check 3: Dependency Truth", "status": status, "detail": "\n".join(detail_lines)}


def _check_naming_consistency(root: Path, files: dict) -> dict:
    """Check 4: Verify naming conventions in conventions.md match actual code."""
    conv_content = files.get("conventions.md", "")

    if not conv_content or conv_content.count("[待填写") >= 3:
        return {
            "name": "Check 4: Naming Consistency",
            "status": "SKIP",
            "detail": "conventions.md not filled yet (3+ [待填写] sections). Skipping."
        }

    # Extract naming rules
    rules = []

    # Check for prefix rules (e.g., "tool_ 前缀", "aio__ prefix")
    prefix_matches = re.findall(r'[`*]*(\w+)[_]*[`*]*\s*前缀|prefix[：:]\s*[`*]*(\w+)', conv_content)
    for m in prefix_matches:
        prefix = m[0] or m[1]
        if prefix:
            rules.append(("prefix", prefix))

    # Check for case rules
    if "snake_case" in conv_content.lower():
        rules.append(("func_case", "snake_case"))
    if "PascalCase" in conv_content:
        rules.append(("class_case", "PascalCase"))
    if "UPPER_SNAKE" in conv_content or "全大写" in conv_content:
        rules.append(("const_case", "UPPER_SNAKE_CASE"))

    if not rules:
        return {
            "name": "Check 4: Naming Consistency",
            "status": "SKIP",
            "detail": "No parseable naming rules found in conventions.md."
        }

    # Sample code files
    code_files = _iter_code_files(root, {".py"})[:30]  # Sample 30 files

    func_names = []
    class_names = []
    for cf in code_files:
        try:
            content = cf.read_text(encoding="utf-8", errors="ignore")
            func_names.extend(re.findall(r'^def\s+(\w+)\s*\(', content, re.MULTILINE))
            class_names.extend(re.findall(r'^class\s+(\w+)', content, re.MULTILINE))
        except Exception:
            continue

    violations = []
    checks_done = []

    for rule_type, rule_val in rules:
        if rule_type == "prefix":
            # Check that functions with this domain use the prefix
            prefix = rule_val.rstrip("_") + "_"
            # Just report how many functions use the prefix
            with_prefix = [f for f in func_names if f.startswith(prefix)]
            checks_done.append(f"Prefix `{prefix}`: {len(with_prefix)} functions use it")

        elif rule_type == "func_case":
            # Check snake_case: all lowercase with underscores
            non_snake = [f for f in func_names
                        if not re.match(r'^[a-z_][a-z0-9_]*$', f)
                        and not f.startswith("__")]  # Skip dunder
            if non_snake:
                violations.append(f"Non-snake_case functions ({len(non_snake)}): {', '.join(non_snake[:5])}")
            total = len([f for f in func_names if not f.startswith("__")])
            compliant = total - len(non_snake)
            pct = (compliant / total * 100) if total > 0 else 100
            checks_done.append(f"snake_case functions: {compliant}/{total} ({pct:.0f}%)")

        elif rule_type == "class_case":
            # Check PascalCase: starts with uppercase
            non_pascal = [c for c in class_names if not re.match(r'^[A-Z]', c)]
            if non_pascal:
                violations.append(f"Non-PascalCase classes ({len(non_pascal)}): {', '.join(non_pascal[:5])}")
            pct = ((len(class_names) - len(non_pascal)) / len(class_names) * 100) if class_names else 100
            checks_done.append(f"PascalCase classes: {len(class_names) - len(non_pascal)}/{len(class_names)} ({pct:.0f}%)")

    detail_lines = [f"Scanned {len(code_files)} files, {len(func_names)} functions, {len(class_names)} classes"]
    for c in checks_done:
        detail_lines.append(f"  {c}")
    if violations:
        detail_lines.append("Violations:")
        for v in violations:
            detail_lines.append(f"  - {v}")

    if not violations:
        status = "PASS"
    elif len(violations) <= 2:
        status = "WARN"
    else:
        status = "FAIL"

    return {"name": "Check 4: Naming Consistency", "status": status, "detail": "\n".join(detail_lines)}


def _check_config_parsing(root: Path, files: dict) -> dict:
    """Check 5: Verify config claims (env vars, ports, services) match reality."""
    tc_content = files.get("techContext.md", "")

    if not tc_content:
        return {
            "name": "Check 5: Config Parsing",
            "status": "SKIP",
            "detail": "techContext.md not found."
        }

    issues = []
    checks = []

    # --- 5a: Check .env variables ---
    # Extract claimed env vars from techContext
    claimed_vars = set(re.findall(r'[`*]*([A-Z][A-Z0-9_]{2,})[`*]*', tc_content))
    # Filter out common words that aren't env vars
    false_positives = {"API", "URL", "SQL", "HTTP", "YAML", "JSON", "HTML", "CSS",
                       "SDK", "CLI", "IDE", "MCP", "LLM", "SSE", "CRUD", "RBAC",
                       "ORM", "DAG", "MAX", "MIN", "GET", "POST", "PUT", "DELETE",
                       "TRUE", "FALSE", "NULL", "NONE", "SKIP", "TODO", "FIXME",
                       "STATIC", "DYNAMIC", "TABLE", "CREATE", "INSERT", "SELECT",
                       "NOTE", "WARN", "INFO", "DEBUG", "ERROR", "FAIL", "PASS"}
    claimed_vars = {v for v in claimed_vars if v not in false_positives and len(v) > 4}

    # Find .env files -- search root and all immediate subdirectories
    env_vars_in_file = set()
    env_found_path = None
    for env_name in [".env", ".env.example", ".env.sample"]:
        # Check root
        env_path = root / env_name
        if env_path.exists():
            env_found_path = env_path
        else:
            # Check immediate subdirectories
            for subdir in root.iterdir():
                if subdir.is_dir() and subdir.name not in SKIP_DIRS:
                    candidate = subdir / env_name
                    if candidate.exists():
                        env_found_path = candidate
                        break
            if not env_found_path:
                # Deep search as last resort (limit depth)
                matches = list(root.glob(f"**/{env_name}"))
                matches = [m for m in matches if not any(s in m.parts for s in SKIP_DIRS)]
                if matches:
                    env_found_path = matches[0]
        if env_found_path:
            try:
                env_content = env_found_path.read_text(encoding="utf-8", errors="ignore")
                env_vars_in_file.update(re.findall(r'^([A-Z][A-Z0-9_]+)\s*=', env_content, re.MULTILINE))
            except Exception:
                pass
            break  # Found one, stop searching

    if claimed_vars and env_vars_in_file:
        # Check claimed vars that look like env vars (contain _ and are in UPPER_CASE)
        env_like_claimed = {v for v in claimed_vars if "_" in v}
        missing_in_env = env_like_claimed - env_vars_in_file
        # Only report truly missing ones (not just mentioned as concepts)
        if missing_in_env:
            # Double-check: are these actually used in code as env vars?
            code_files = _iter_code_files(root, {".py"})
            code_content = ""
            for cf in code_files[:100]:
                try:
                    code_content += cf.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass
            actually_used = {v for v in missing_in_env
                           if f'"{v}"' in code_content or f"'{v}'" in code_content
                           or f"os.getenv('{v}')" in code_content or f'os.getenv("{v}")' in code_content
                           or f"os.environ['{v}']" in code_content or f'os.environ["{v}"]' in code_content}
            if actually_used:
                issues.append(f"Env vars used in code but missing from .env: {', '.join(sorted(actually_used))}")

        env_rel = str(env_found_path.relative_to(root)) if env_found_path else ".env"
        checks.append(f".env ({env_rel}): {len(env_vars_in_file)} vars found, {len(env_like_claimed)} claimed in techContext")
    elif claimed_vars:
        checks.append("No .env file found to verify against (searched root + subdirectories)")
    else:
        checks.append("No env variable claims detected in techContext")

    # --- 5b: Check docker-compose ports ---
    dc_path = root / "docker-compose.yml"
    if not dc_path.exists():
        dc_path = root / "docker-compose.yaml"
    if not dc_path.exists():
        matches = list(root.glob("**/docker-compose.y*ml"))
        matches = [m for m in matches if not any(s in m.parts for s in SKIP_DIRS)]
        if matches:
            dc_path = matches[0]

    if dc_path.exists():
        try:
            dc_content = dc_path.read_text(encoding="utf-8", errors="ignore")
            # Extract exposed ports
            port_matches = re.findall(r'(?:ports:\s*\n(?:\s+-\s+["\']?\d+:\d+["\']?\s*\n?)+)', dc_content)
            actual_ports = re.findall(r'["\']?(\d+):(\d+)["\']?', dc_content)

            # Check for port conflicts (same host port used by different services)
            host_ports = [hp for hp, cp in actual_ports]
            duplicates = [p for p in set(host_ports) if host_ports.count(p) > 1]
            if duplicates:
                issues.append(f"Docker port conflict: host port(s) {', '.join(duplicates)} used by multiple services")

            # Extract service names
            services = re.findall(r'^  (\w[\w-]*):\s*$', dc_content, re.MULTILINE)

            checks.append(f"docker-compose: {len(services)} services, {len(actual_ports)} port mappings")
            if duplicates:
                checks.append(f"  Port conflicts: {', '.join(duplicates)}")
        except Exception:
            checks.append("docker-compose.yml exists but failed to parse")
    else:
        checks.append("No docker-compose.yml found (OK if not using Docker)")

    # --- 5c: Check requirements.txt vs techContext ---
    for req_name in ["requirements.txt"]:
        req_path = root / req_name
        if not req_path.exists():
            matches = list(root.glob(f"**/{req_name}"))
            matches = [m for m in matches if not any(s in m.parts for s in SKIP_DIRS)]
            if matches:
                req_path = matches[0]
        if req_path.exists():
            try:
                req_content = req_path.read_text(encoding="utf-8", errors="ignore")
                req_packages = set()
                for line in req_content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        pkg = re.split(r'[>=<!\[\]]', line)[0].strip().lower()
                        if pkg:
                            req_packages.add(pkg)
                checks.append(f"requirements.txt: {len(req_packages)} packages listed")
            except Exception:
                pass

    detail_lines = []
    for c in checks:
        detail_lines.append(c)
    if issues:
        detail_lines.append("Issues:")
        for i in issues:
            detail_lines.append(f"  - {i}")

    if not issues:
        status = "PASS"
    else:
        status = "WARN"

    return {"name": "Check 5: Config Parsing", "status": status, "detail": "\n".join(detail_lines)}


def register_audit_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register audit tools onto the MCP server instance."""

    @mcp.tool()
    def aio__audit_project_map(project_root: str) -> str:
        """
        [VERIFICATION] Programmatically verify project_map claims against actual code.

        Runs 5 automated checks against the target project's codebase:
        1. File existence -- paths in systemPatterns/inventory -> os.path.exists
        2. Decorator count -- grep @enterprise_tool count vs inventory claim
        3. Dependency truth -- claimed libraries -> grep actual imports
        4. Naming consistency -- conventions.md rules -> sample-check code
        5. Config parsing -- .env / docker-compose vs techContext claims

        When to call:
        - After [初始化项目] Phase 3 (before writing to project_map)
        - After [存档] when static files were updated
        - Anytime you suspect project_map drift

        This tool is READ-ONLY. It does NOT modify any files.

        Args:
            project_root: Absolute path to the target project root directory.
        """
        _audit("aio__audit_project_map", "CALLED", project_root[:100])

        loop_msg = _loop_guard("aio__audit_project_map", project_root)
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        root = Path(project_root)
        if not root.is_dir():
            return f"FAILED: project_root '{project_root}' is not a directory."

        pm_dir = root / ".ai-operation" / "docs" / "project_map"
        if not pm_dir.is_dir():
            return f"FAILED: No project_map at {pm_dir}. Run [初始化项目] first."

        # Read project_map files
        pm_files = {}
        for name in ["systemPatterns.md", "inventory.md", "techContext.md", "conventions.md"]:
            fp = pm_dir / name
            if fp.exists():
                try:
                    pm_files[name] = fp.read_text(encoding="utf-8")
                except Exception:
                    pm_files[name] = ""

        # Run all 5 checks
        results = [
            _check_file_existence(root, pm_files),
            _check_decorator_count(root, pm_files),
            _check_dependency_truth(root, pm_files),
            _check_naming_consistency(root, pm_files),
            _check_config_parsing(root, pm_files),
        ]

        # Build summary
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
        for r in results:
            counts[r["status"]] = counts.get(r["status"], 0) + 1

        summary_parts = []
        for s in ["PASS", "WARN", "FAIL", "SKIP"]:
            if counts[s] > 0:
                summary_parts.append(f"{counts[s]} {s}")

        report = [
            f"AUDIT_COMPLETE: 5 checks executed. Result: {', '.join(summary_parts)}",
            "",
        ]

        for r in results:
            report.append(f"## {r['name']} [{r['status']}]")
            report.append(r["detail"])
            report.append("")

        if counts["FAIL"] > 0:
            report.append("ACTION REQUIRED: Fix FAIL items in project_map before writing/confirming.")
        elif counts["WARN"] > 0:
            report.append("REVIEW: WARN items may indicate minor inaccuracies. Check and fix if needed.")

        _audit("aio__audit_project_map", "SUCCESS",
               f"pass={counts['PASS']},warn={counts['WARN']},fail={counts['FAIL']},skip={counts['SKIP']}")

        return _budget_truncate("\n".join(report))
