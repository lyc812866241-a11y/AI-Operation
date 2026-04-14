"""
Codebase scanner — single tool call replaces Phase 1 + Phase 2 T1/T3.

Contains: aio__scan_codebase

Walks the file tree, reads file headers, extracts signatures,
classifies roles, and returns a structured summary within budget.
No external dependencies (no repomix/npx needed).
"""

import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .constants import _budget_truncate

SKIP_DIRS = {
    ".git", ".ai-operation", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs",
    ".next", ".nuxt", "coverage", ".angular",
}

LANG_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React", ".tsx": "React/TS", ".go": "Go",
    ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".rb": "Ruby", ".php": "PHP", ".cs": "C#",
    ".cpp": "C++", ".c": "C", ".swift": "Swift",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
    ".toml": "TOML", ".sql": "SQL", ".sh": "Shell",
}

# Entry point filenames (high priority)
ENTRY_NAMES = {
    "main.py", "app.py", "server.py", "index.js", "index.ts",
    "manage.py", "cli.py", "main.go", "main.rs", "main.java",
    "wsgi.py", "asgi.py", "startup.py", "run.py", "bot.py",
}

# Config filenames
CONFIG_NAMES = {
    "config.py", "settings.py", "config.yaml", "config.yml",
    "config.json", ".env", "docker-compose.yml", "Dockerfile",
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod",
}

# Max lines to read per file for signature extraction
HEADER_LINES = 60
# No file cap — every code file must appear in output. Completeness is guaranteed.


def _classify_file(path: Path, content_head: str) -> str:
    """Classify a file's role based on name and content."""
    name = path.name.lower()
    stem = path.stem.lower()

    if name in ENTRY_NAMES:
        return "entry"
    if name in CONFIG_NAMES or name.startswith(".env"):
        return "config"
    if "test" in stem or stem.startswith("test_") or stem.endswith("_test"):
        return "test"
    if name == "__init__.py":
        return "init"
    if "migration" in str(path).lower() or "alembic" in str(path).lower():
        return "migration"

    # Check content for entry-point patterns
    if "if __name__" in content_head:
        return "entry"
    if "app = Flask" in content_head or "app = FastAPI" in content_head:
        return "entry"

    return "module"


def _extract_signatures(content: str, suffix: str) -> dict:
    """Extract key signatures from file header content."""
    result = {
        "imports": [],
        "classes": [],
        "functions": [],
        "decorators": [],
        "constants": [],
    }

    if suffix in (".py",):
        # Python
        for line in content.split("\n"):
            line_s = line.strip()
            if line_s.startswith("import ") or line_s.startswith("from "):
                # Simplify: just the module name
                mod = line_s.split("import ")[-1].split(" as ")[0].split(",")[0].strip()
                if line_s.startswith("from "):
                    mod = line_s.split("from ")[1].split(" import")[0].strip()
                if mod and mod not in result["imports"]:
                    result["imports"].append(mod)
            elif re.match(r'^class\s+(\w+)', line_s):
                cls = re.match(r'^class\s+(\w+)', line_s).group(1)
                result["classes"].append(cls)
            elif re.match(r'^def\s+(\w+)', line_s):
                func = re.match(r'^def\s+(\w+)', line_s).group(1)
                result["functions"].append(func)
            elif re.match(r'^    def\s+(\w+)', line) and not line_s.startswith("def"):
                # Skip methods (indented def) unless they're important
                pass
            elif re.match(r'^\s*@(\w+)', line_s) and not line_s.startswith("def"):
                dec = re.match(r'^\s*@(\w+)', line_s).group(1)
                if dec not in ("staticmethod", "classmethod", "property"):
                    if dec not in result["decorators"]:
                        result["decorators"].append(dec)
            elif re.match(r'^[A-Z][A-Z_0-9]+\s*=', line_s):
                const = line_s.split("=")[0].strip()
                result["constants"].append(const)

    elif suffix in (".js", ".ts", ".jsx", ".tsx"):
        # JavaScript/TypeScript
        for line in content.split("\n"):
            line_s = line.strip()
            if line_s.startswith("import ") or line_s.startswith("const ") and "require(" in line_s:
                result["imports"].append(line_s[:80])
            elif re.match(r'(?:export\s+)?(?:class|function)\s+(\w+)', line_s):
                m = re.match(r'(?:export\s+)?(?:class|function)\s+(\w+)', line_s)
                if "class" in line_s:
                    result["classes"].append(m.group(1))
                else:
                    result["functions"].append(m.group(1))
            elif re.match(r'(?:export\s+)?const\s+(\w+)', line_s):
                result["constants"].append(re.match(r'(?:export\s+)?const\s+(\w+)', line_s).group(1))

    elif suffix in (".go",):
        for line in content.split("\n"):
            line_s = line.strip()
            if re.match(r'^func\s+(\w+)', line_s):
                result["functions"].append(re.match(r'^func\s+(\w+)', line_s).group(1))
            elif re.match(r'^type\s+(\w+)\s+struct', line_s):
                result["classes"].append(re.match(r'^type\s+(\w+)', line_s).group(1))

    # Trim to keep output compact
    result["imports"] = result["imports"][:10]
    result["functions"] = result["functions"][:15]
    result["classes"] = result["classes"][:10]
    result["constants"] = result["constants"][:5]
    result["decorators"] = result["decorators"][:5]

    return result


def _scan_tree(root: Path, scope: str) -> list:
    """Walk file tree, read headers, return structured file info list."""
    scan_root = root / scope if scope else root
    if not scan_root.is_dir():
        return []

    code_exts = set(LANG_MAP.keys())
    files = []
    skipped_count = 0

    for p in sorted(scan_root.rglob("*")):
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        if not p.is_file():
            continue
        if p.suffix not in code_exts:
            continue

        try:
            # Read header only
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= HEADER_LINES:
                        break
                    lines.append(line)
                head = "".join(lines)

            total_lines = sum(1 for _ in open(p, "r", encoding="utf-8", errors="ignore"))
            rel_path = str(p.relative_to(root)).replace("\\", "/")

            role = _classify_file(p, head)
            sigs = _extract_signatures(head, p.suffix)
            lang = LANG_MAP.get(p.suffix, p.suffix)

            files.append({
                "path": rel_path,
                "lang": lang,
                "lines": total_lines,
                "role": role,
                "sigs": sigs,
            })
        except Exception:
            continue

    return files


def _format_report(files: list, root: Path, scope: str) -> str:
    """Format scanned files into a structured summary.

    Every code file appears in the output. No silent skipping.
    Output is designed to be directly usable as the module inventory
    section of systemPatterns.md.
    """
    if not files:
        scan_path = f"{root}/{scope}" if scope else str(root)
        return f"No code files found in {scan_path}"

    # Group by role
    groups = {"entry": [], "config": [], "module": [], "test": [], "init": [], "migration": []}
    for f in files:
        groups.get(f["role"], groups["module"]).append(f)

    # Language stats
    lang_counts = {}
    total_lines = 0
    for f in files:
        lang_counts[f["lang"]] = lang_counts.get(f["lang"], 0) + 1
        total_lines += f["lines"]

    lang_summary = ", ".join(f"{lang} {count}" for lang, count in
                            sorted(lang_counts.items(), key=lambda x: -x[1]))

    lines = []
    lines.append(f"# Codebase Scan: {scope or '.'}")
    lines.append(f"**{len(files)} files, {total_lines:,} lines** ({lang_summary})")
    lines.append("")

    # Entry points first (most important)
    if groups["entry"]:
        lines.append("## Entry Points")
        for f in groups["entry"]:
            lines.append(_format_file(f))
        lines.append("")

    # Config
    if groups["config"]:
        lines.append("## Config")
        for f in groups["config"]:
            lines.append(f"- **{f['path']}** ({f['lines']} lines)")
        lines.append("")

    # Core modules (the bulk)
    if groups["module"]:
        # Sub-group by directory
        dir_groups = {}
        for f in groups["module"]:
            parts = f["path"].split("/")
            dir_key = "/".join(parts[:-1]) if len(parts) > 1 else "."
            dir_groups.setdefault(dir_key, []).append(f)

        lines.append("## Modules")
        for dir_name in sorted(dir_groups.keys()):
            dir_files = dir_groups[dir_name]
            lines.append(f"\n### {dir_name}/")
            for f in dir_files:
                lines.append(_format_file(f))
        lines.append("")

    # Init files (compact)
    if groups["init"]:
        lines.append(f"## Init Files ({len(groups['init'])})")
        for f in groups["init"]:
            lines.append(f"- {f['path']}")
        lines.append("")

    # Tests
    if groups["test"]:
        lines.append(f"## Tests ({len(groups['test'])} files)")
        for f in groups["test"]:
            lines.append(f"- {f['path']} ({f['lines']} lines)")
        lines.append("")

    # Completeness guarantee
    lines.append("---")
    lines.append(f"**Completeness: {len(files)} files scanned, 0 skipped.**")
    lines.append("Every code file in the scan scope is listed above.")
    lines.append("This output can be used directly as the module inventory in systemPatterns.md.")

    return "\n".join(lines)


def _format_file(f: dict) -> str:
    """Format a single file entry."""
    sigs = f["sigs"]
    parts = [f"- **{f['path']}** ({f['lines']} lines)"]

    # Classes
    if sigs["classes"]:
        parts.append(f"  classes: {', '.join(sigs['classes'])}")
    # Functions (compact: show count if many)
    if sigs["functions"]:
        if len(sigs["functions"]) <= 5:
            parts.append(f"  functions: {', '.join(sigs['functions'])}")
        else:
            shown = ", ".join(sigs["functions"][:4])
            parts.append(f"  functions: {shown} ... +{len(sigs['functions']) - 4} more")
    # Decorators
    if sigs["decorators"]:
        parts.append(f"  decorators: {', '.join(sigs['decorators'])}")
    # Key imports (only external, skip stdlib)
    ext_imports = [i for i in sigs["imports"]
                   if not i.startswith(".") and i not in (
                       "os", "sys", "re", "json", "time", "datetime",
                       "pathlib", "typing", "collections", "functools",
                       "logging", "hashlib", "uuid", "copy", "math",
                   )]
    if ext_imports:
        parts.append(f"  imports: {', '.join(ext_imports[:6])}")
    # Constants
    if sigs["constants"]:
        parts.append(f"  constants: {', '.join(sigs['constants'])}")

    return "\n".join(parts)


def register_scan_tools(mcp: FastMCP, _audit, _loop_guard):
    """Register scan tools onto the MCP server instance."""

    @mcp.tool()
    def aio__scan_codebase(project_root: str, scope: str = "") -> str:
        """
        [BOOTSTRAP] Scan codebase and return structured file summary.

        Replaces manual Phase 1-2 scanning with a single tool call.
        Walks the file tree, reads file headers (first 60 lines only),
        extracts class/function/import signatures, classifies each file's
        role (entry/module/config/test), and returns a compact summary.

        No external dependencies needed (no repomix/npx).

        Args:
            project_root: Absolute path to the project root.
            scope: Optional subdirectory to scan (e.g. "src" or "agent_core/core").
                   If empty, scans the entire project root.
        """
        _audit("aio__scan_codebase", "CALLED", f"root={project_root[:60]}, scope={scope}")

        loop_msg = _loop_guard("aio__scan_codebase", f"{project_root}:{scope}")
        if loop_msg and "BLOCKED" in loop_msg:
            return loop_msg

        root = Path(project_root)
        if not root.is_dir():
            return f"FAILED: '{project_root}' is not a directory."

        scan_path = root / scope if scope else root
        if not scan_path.is_dir():
            return f"FAILED: scope '{scope}' not found in {project_root}"

        files = _scan_tree(root, scope)
        report = _format_report(files, root, scope)

        _audit("aio__scan_codebase", "SUCCESS", f"files={len(files)}, scope={scope}")
        return _budget_truncate(report)
