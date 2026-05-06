#!/usr/bin/env python3
"""
AI-Operation Framework — Web Dashboard
=======================================
Zero-dependency local web server that visualizes project map status.
Uses only Python standard library (http.server + string templates).

Usage:
    python .ai-operation/cli/dashboard.py [port]
    python .ai-operation/cli/ai_op.py dashboard

Default: http://localhost:8420
"""

import http.server
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8420

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROJECT_MAP_DIR = PROJECT_ROOT / ".ai-operation" / "docs" / "project_map"

REQUIRED_FILES = [
    # 议题 #010: projectbrief 已删除,vision 在 design.md(在 conception/ 不在 project_map/)
    ("systemPatterns", "systemPatterns.md", "Architecture", "#8b5cf6"),
    ("techContext", "techContext.md", "Tech Stack", "#06b6d4"),
    ("activeContext", "activeContext.md", "Active Context", "#f59e0b"),
    ("progress", "progress.md", "Progress", "#10b981"),
    ("corrections", "corrections.md", "Corrections", "#ef4444"),
]

RULE_FILES = [
    (".clinerules", "Roo Code"),
    ("CLAUDE.md", "Claude Code"),
    (".cursorrules", "Cursor"),
    (".windsurfrules", "Windsurf"),
]

MCP_CONFIGS = [
    (".roo/mcp.json", "Roo Code"),
    (".cursor/mcp.json", "Cursor"),
    (".windsurf/mcp.json", "Windsurf"),
    (".mcp.json", "Claude Code"),
]


def read_file(path):
    """Read file content, return empty string if not found."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def md_to_html(md_text):
    """Minimal markdown to HTML (headings, lists, bold, code blocks)."""
    lines = md_text.split("\n")
    html_lines = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                html_lines.append("</pre>")
                in_code = False
            else:
                html_lines.append('<pre class="code-block">')
                in_code = True
            continue

        if in_code:
            html_lines.append(line.replace("<", "&lt;").replace(">", "&gt;"))
            continue

        # Headings
        if line.startswith("### "):
            html_lines.append(f"<h4>{line[4:]}</h4>")
        elif line.startswith("## "):
            html_lines.append(f"<h3>{line[3:]}</h3>")
        elif line.startswith("# "):
            html_lines.append(f"<h2>{line[2:]}</h2>")
        elif line.startswith("- [x] "):
            html_lines.append(f'<div class="task done">&#9745; {line[6:]}</div>')
        elif line.startswith("- [ ] "):
            html_lines.append(f'<div class="task pending">&#9744; {line[6:]}</div>')
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<div class='list-item'>&bull; {line[2:]}</div>")
        elif line.startswith("> "):
            html_lines.append(f'<blockquote>{line[2:]}</blockquote>')
        elif line.strip() == "---":
            html_lines.append("<hr>")
        elif line.strip():
            # Bold
            processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            # Inline code
            processed = re.sub(r'`(.+?)`', r'<code>\1</code>', processed)
            html_lines.append(f"<p>{processed}</p>")

    if in_code:
        html_lines.append("</pre>")

    return "\n".join(html_lines)


def get_stats():
    """Calculate project statistics."""
    progress = read_file(PROJECT_MAP_DIR / "progress.md")
    active = read_file(PROJECT_MAP_DIR / "activeContext.md")
    corrections = read_file(PROJECT_MAP_DIR / "corrections.md")

    todo_count = progress.count("- [ ]")
    done_count = progress.count("- [x]")
    correction_count = corrections.count("DATE:")
    # 议题 #010: 用 systemPatterns 替代 projectbrief 判断"已初始化"
    is_initialized = "[待填写]" not in read_file(PROJECT_MAP_DIR / "systemPatterns.md") and \
                     "[TODO]" not in read_file(PROJECT_MAP_DIR / "systemPatterns.md")

    # IDE status
    ide_status = []
    for path, name in RULE_FILES:
        exists = (PROJECT_ROOT / path).exists()
        ide_status.append({"name": name, "file": path, "exists": exists})

    mcp_status = []
    for path, name in MCP_CONFIGS:
        full_path = PROJECT_ROOT / path
        exists = full_path.exists()
        configured = False
        if exists:
            content = read_file(full_path)
            configured = "REPLACE_WITH" not in content
        mcp_status.append({"name": name, "file": path, "exists": exists, "configured": configured})

    hook_installed = (PROJECT_ROOT / ".git" / "hooks" / "pre-commit").exists()

    return {
        "todo": todo_count,
        "done": done_count,
        "corrections": correction_count,
        "initialized": is_initialized,
        "ide_status": ide_status,
        "mcp_status": mcp_status,
        "hook_installed": hook_installed,
    }


def build_html():
    """Build the full dashboard HTML page."""
    stats = get_stats()

    # Build file cards
    file_cards = ""
    for key, filename, title, color in REQUIRED_FILES:
        content = read_file(PROJECT_MAP_DIR / filename)
        html_content = md_to_html(content) if content else "<p class='empty'>File not found or empty</p>"
        file_cards += f"""
        <div class="card" style="border-left: 4px solid {color}">
            <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
                <h3 style="color: {color}">{title}</h3>
                <span class="filename">{filename}</span>
                <span class="toggle">&#9660;</span>
            </div>
            <div class="card-body">{html_content}</div>
        </div>
        """

    # Build IDE status
    ide_rows = ""
    for ide in stats["ide_status"]:
        status = "&#9745;" if ide["exists"] else "&#9744;"
        css = "ok" if ide["exists"] else "missing"
        ide_rows += f'<tr class="{css}"><td>{ide["name"]}</td><td><code>{ide["file"]}</code></td><td>{status}</td></tr>'

    mcp_rows = ""
    for mcp in stats["mcp_status"]:
        if mcp["configured"]:
            status, css = "&#9745; Configured", "ok"
        elif mcp["exists"]:
            status, css = "&#9888; Not configured", "warn"
        else:
            status, css = "&#9744; Missing", "missing"
        mcp_rows += f'<tr class="{css}"><td>{mcp["name"]}</td><td><code>{mcp["file"]}</code></td><td>{status}</td></tr>'

    hook_status = "&#9745; Installed" if stats["hook_installed"] else "&#9744; Not installed"
    hook_css = "ok" if stats["hook_installed"] else "missing"

    init_status = "Initialized" if stats["initialized"] else "NOT initialized — run [初始化项目]"
    init_css = "stat-ok" if stats["initialized"] else "stat-warn"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-Operation Dashboard</title>
<meta http-equiv="refresh" content="10">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid #1e293b; margin-bottom: 30px; }}
header h1 {{ font-size: 28px; color: #f8fafc; }}
header p {{ color: #64748b; margin-top: 8px; }}

.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 30px; }}
.stat {{ background: #1e293b; border-radius: 12px; padding: 20px; text-align: center; }}
.stat .number {{ font-size: 36px; font-weight: bold; }}
.stat .label {{ color: #94a3b8; font-size: 14px; margin-top: 4px; }}
.stat-ok {{ color: #10b981; }}
.stat-warn {{ color: #f59e0b; }}
.stat-blue {{ color: #3b82f6; }}
.stat-purple {{ color: #8b5cf6; }}

.section {{ margin-bottom: 30px; }}
.section h2 {{ font-size: 20px; margin-bottom: 16px; color: #f8fafc; }}

.card {{ background: #1e293b; border-radius: 12px; margin-bottom: 12px; overflow: hidden; }}
.card-header {{ display: flex; align-items: center; padding: 16px 20px; cursor: pointer; user-select: none; }}
.card-header h3 {{ flex: 1; font-size: 16px; }}
.card-header .filename {{ color: #64748b; font-size: 13px; font-family: monospace; margin-right: 12px; }}
.card-header .toggle {{ color: #64748b; transition: transform 0.2s; }}
.card.collapsed .card-body {{ display: none; }}
.card.collapsed .toggle {{ transform: rotate(-90deg); }}
.card-body {{ padding: 0 20px 20px; font-size: 14px; line-height: 1.7; }}
.card-body h2 {{ font-size: 18px; color: #f8fafc; margin: 16px 0 8px; }}
.card-body h3 {{ font-size: 16px; color: #cbd5e1; margin: 12px 0 6px; }}
.card-body h4 {{ font-size: 14px; color: #94a3b8; margin: 10px 0 4px; }}
.card-body p {{ color: #cbd5e1; margin: 4px 0; }}
.card-body blockquote {{ border-left: 3px solid #334155; padding-left: 12px; color: #94a3b8; margin: 8px 0; }}
.card-body code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #7dd3fc; }}
.card-body .code-block {{ background: #0f172a; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 13px; color: #a5f3fc; margin: 8px 0; }}
.card-body hr {{ border: none; border-top: 1px solid #334155; margin: 12px 0; }}
.card-body .list-item {{ padding: 2px 0 2px 8px; color: #cbd5e1; }}
.card-body .task {{ padding: 4px 0 4px 4px; }}
.card-body .task.done {{ color: #10b981; }}
.card-body .task.pending {{ color: #f59e0b; }}
.card-body .empty {{ color: #475569; font-style: italic; }}

table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; }}
th {{ text-align: left; padding: 12px 16px; background: #0f172a; color: #94a3b8; font-size: 13px; text-transform: uppercase; }}
td {{ padding: 10px 16px; border-top: 1px solid #0f172a; font-size: 14px; }}
tr.ok td:last-child {{ color: #10b981; }}
tr.warn td:last-child {{ color: #f59e0b; }}
tr.missing td:last-child {{ color: #ef4444; }}

.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} .stats {{ grid-template-columns: repeat(2, 1fr); }} }}

footer {{ text-align: center; padding: 20px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>AI-Operation Dashboard</h1>
        <p>Project Map Status &middot; Auto-refreshes every 10s &middot; {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </header>

    <div class="stats">
        <div class="stat">
            <div class="number {init_css}">{init_status.split()[0]}</div>
            <div class="label">Project Status</div>
        </div>
        <div class="stat">
            <div class="number stat-ok">{stats['done']}</div>
            <div class="label">Tasks Done</div>
        </div>
        <div class="stat">
            <div class="number stat-warn">{stats['todo']}</div>
            <div class="label">Tasks Pending</div>
        </div>
        <div class="stat">
            <div class="number stat-purple">{stats['corrections']}</div>
            <div class="label">Corrections</div>
        </div>
    </div>

    <div class="grid-2">
        <div class="section">
            <h2>IDE Rule Files</h2>
            <table>
                <tr><th>IDE</th><th>File</th><th>Status</th></tr>
                {ide_rows}
            </table>
        </div>
        <div class="section">
            <h2>MCP Configuration</h2>
            <table>
                <tr><th>IDE</th><th>Config</th><th>Status</th></tr>
                {mcp_rows}
                <tr class="{hook_css}"><td colspan="2"><strong>Git Pre-Commit Hook</strong></td><td>{hook_status}</td></tr>
            </table>
        </div>
    </div>

    <div class="section">
        <h2>Project Map Files</h2>
        {file_cards}
    </div>

    <footer>
        AI-Operation Framework &middot; The Plan IS the Product
    </footer>
</div>
</body>
</html>"""
    return html


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(build_html().encode("utf-8"))
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_stats()).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logs


def main():
    os.chdir(str(PROJECT_ROOT))
    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"\n  AI-Operation Dashboard")
    print(f"  {'─' * 40}")
    print(f"  URL: http://localhost:{PORT}")
    print(f"  Auto-refresh: every 10 seconds")
    print(f"  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
