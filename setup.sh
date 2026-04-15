#!/usr/bin/env bash
# =============================================================================
# Vibe Coding Agent Framework — One-Command Installer
# =============================================================================
#
# USAGE (from your project root directory):
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.sh)
#
# What this script does:
#   1. Checks for Python 3.8+
#   2. Downloads scaffold files into the current directory
#   3. Creates a virtual environment at .ai-operation/venv/
#   4. Installs MCP dependencies (mcp[cli], fastmcp)
#   5. Installs repomix (global codebase map tool) via npx or pip
#   6. Auto-detects the venv Python path and writes it into all IDE MCP configs
#   7. Generates IDE rule files (.clinerules, CLAUDE.md, .cursorrules, .windsurfrules)
#   8. Verifies the MCP server can start
# =============================================================================

set -e

# ── Parse arguments ─────────────────────────────────────────────────────────
UPDATE_MODE=false
MIGRATE_MODE=false
CHECK_MODE=false
if [ "$1" = "--update" ] || [ "$1" = "-u" ]; then
    UPDATE_MODE=true
elif [ "$1" = "--migrate" ] || [ "$1" = "-m" ]; then
    MIGRATE_MODE=true
    UPDATE_MODE=true  # migrate implies update
elif [ "$1" = "--check" ] || [ "$1" = "-c" ]; then
    CHECK_MODE=true
fi

# Framework code directories — overwritten on update
FRAMEWORK_DIRS=("mcp_server" "scripts" "skills" "hooks" "cli" "rules.d")

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

print_step()  { echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }
print_ok()    { echo -e "  ${GREEN}✓ $1${NC}"; }
print_warn()  { echo -e "  ${YELLOW}⚠ $1${NC}"; }
print_error() { echo -e "  ${RED}✗ $1${NC}"; }
print_info()  { echo -e "  ${NC}$1${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
if [ "$CHECK_MODE" = true ]; then
    echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}${BOLD}║     Vibe Coding Agent Framework — CHECK          ║${NC}"
    echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
elif [ "$UPDATE_MODE" = true ]; then
    echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}${BOLD}║     Vibe Coding Agent Framework — UPDATE         ║${NC}"
    echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
else
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║     Vibe Coding Agent Framework — Setup          ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
fi
echo ""

# ── CHECK MODE ──────────────────────────────────────────────────────────────
if [ "$CHECK_MODE" = true ]; then
    PASS=0
    FAIL=0
    WARN=0

    check_pass() { PASS=$((PASS + 1)); print_ok "$1"; }
    check_fail() { FAIL=$((FAIL + 1)); print_error "$1"; }
    check_warn() { WARN=$((WARN + 1)); print_warn "$1"; }

    # 1. Framework directory
    print_step "1. Framework structure"
    [ -d ".ai-operation" ] && check_pass ".ai-operation/ exists" || check_fail ".ai-operation/ missing"
    [ -d ".ai-operation/mcp_server" ] && check_pass "MCP server code" || check_fail "MCP server missing"
    [ -d ".ai-operation/skills" ] && check_pass "Skills directory" || check_fail "Skills missing"
    [ -d ".ai-operation/hooks" ] && check_pass "Git hooks" || check_fail "Hooks missing"

    # 2. Python & venv
    print_step "2. Python & venv"
    if [ -f ".ai-operation/venv/Scripts/python.exe" ]; then
        VENV_PY=".ai-operation/venv/Scripts/python.exe"
        check_pass "venv Python: $VENV_PY"
    elif [ -f ".ai-operation/venv/bin/python3" ]; then
        VENV_PY=".ai-operation/venv/bin/python3"
        check_pass "venv Python: $VENV_PY"
    else
        VENV_PY=""
        check_fail "venv not found"
    fi

    if [ -n "$VENV_PY" ]; then
        "$VENV_PY" -c "import mcp; import fastmcp" 2>/dev/null \
            && check_pass "MCP dependencies installed" \
            || check_fail "MCP dependencies missing (run: pip install 'mcp[cli]' fastmcp)"
    fi

    # 3. MCP server & tools
    print_step "3. MCP tools"
    if [ -n "$VENV_PY" ]; then
        MCP_RESULT=$("$VENV_PY" -c "
import sys; sys.path.insert(0, '.ai-operation/mcp_server')
from tools.architect import register_architect_tools
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test'); register_architect_tools(mcp)
try:
    n = len(mcp._tool_manager._tools)
except: n = -1
print(f'OK:{n}')
" 2>&1 || echo "FAIL")
        if echo "$MCP_RESULT" | grep -q '^OK:'; then
            TOOL_COUNT=$(echo "$MCP_RESULT" | sed 's/OK://')
            check_pass "MCP server OK — $TOOL_COUNT tools registered"
        else
            check_fail "MCP server failed to load: $MCP_RESULT"
        fi
    fi

    # 4. IDE configs
    print_step "4. IDE configs"
    [ -f ".mcp.json" ] && check_pass ".mcp.json" || check_fail ".mcp.json missing"
    [ -f ".clinerules" ] && check_pass ".clinerules" || check_warn ".clinerules missing"
    [ -f "CLAUDE.md" ] && check_pass "CLAUDE.md" || check_warn "CLAUDE.md missing"

    if [ -f ".mcp.json" ]; then
        if grep -q "REPLACE_WITH_YOUR_VENV_PYTHON_PATH" .mcp.json; then
            check_fail ".mcp.json has unresolved Python path placeholder"
        else
            check_pass ".mcp.json Python path configured"
        fi
    fi

    # 5. Claude Code hooks
    print_step "5. Claude Code hooks"
    [ -d ".claude/hooks" ] && check_pass ".claude/hooks/ exists" || check_warn ".claude/hooks/ missing"
    [ -f ".claude/hooks/require-context.sh" ] && check_pass "Cognitive gate hook" || check_warn "Cognitive gate hook missing"
    [ -f ".claude/settings.json" ] && check_pass "Claude settings.json" || check_warn "Claude settings.json missing"

    # 6. Project map
    print_step "6. Project map"
    PM_DIR=".ai-operation/docs/project_map"
    [ -d "$PM_DIR" ] && check_pass "project_map/ exists" || check_fail "project_map/ missing"
    PM_FILES=0
    PM_FILLED=0
    for f in projectbrief systemPatterns techContext conventions activeContext progress corrections inventory; do
        pf="$PM_DIR/${f}.md"
        if [ -f "$pf" ]; then
            PM_FILES=$((PM_FILES + 1))
            if ! grep -q '待填写' "$pf" 2>/dev/null || [ "$(grep -c '待填写' "$pf" 2>/dev/null)" -lt 3 ]; then
                PM_FILLED=$((PM_FILLED + 1))
            fi
        fi
    done
    if [ "$PM_FILES" -eq 8 ]; then
        check_pass "All 8 project_map files present"
    else
        check_fail "Only $PM_FILES/8 project_map files found"
    fi
    if [ "$PM_FILLED" -ge 5 ]; then
        check_pass "$PM_FILLED/8 files have content (not template)"
    else
        check_warn "Only $PM_FILLED/8 files filled — run [初始化项目] to populate"
    fi

    # Summary
    echo ""
    TOTAL=$((PASS + FAIL + WARN))
    if [ "$FAIL" -eq 0 ]; then
        echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}${BOLD}║   ✅  All checks passed!  ($PASS pass, $WARN warn)        ║${NC}"
        echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${RED}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}${BOLD}║   ❌  Issues found: $FAIL fail, $WARN warn, $PASS pass       ║${NC}"
        echo -e "${RED}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "  Run ${YELLOW}setup.sh --update${NC} to fix framework issues."
        echo -e "  Run ${YELLOW}setup.sh --migrate${NC} if upgrading from an older version."
    fi
    echo ""
    exit $FAIL
fi

# ── Determine install target directory ───────────────────────────────────────
if [ -n "${BASH_SOURCE[0]}" ] && [ "${BASH_SOURCE[0]}" != "/dev/stdin" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REMOTE_MODE=false
else
    SCRIPT_DIR="$(pwd)"
    REMOTE_MODE=true
fi

REPO_URL="https://github.com/lyc812866241-a11y/AI-Operation.git"
SCAFFOLD_ITEMS=(
    ".ai-operation"
    ".clinerules"
    ".cursorrules"
    ".windsurfrules"
    "CLAUDE.md"
    ".roo"
    ".cursor"
    ".windsurf"
    ".mcp.json"
)

# ── Step 1: Detect Python ─────────────────────────────────────────────────────
print_step "Step 1/7: Checking Python version"

PYTHON_CMD=""
for cmd in python3 python3.11 python3.10 python3.9 python3.8 python; do
    if command -v "$cmd" &>/dev/null; then
        VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        MAJOR=$(echo "$VERSION" | cut -d. -f1)
        MINOR=$(echo "$VERSION" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 8 ]; then
            PYTHON_CMD="$cmd"
            print_ok "Found $cmd (Python $VERSION)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    print_error "Python 3.8+ not found. Please install Python first."
    print_info "  Mac:   brew install python3"
    print_info "  Linux: sudo apt install python3"
    print_info "  Win:   https://www.python.org/downloads/"
    exit 1
fi

# ── UPDATE MODE ─────────────────────────────────────────────────────────────
if [ "$UPDATE_MODE" = true ]; then
    print_step "Update: Downloading latest framework code"

    if [ ! -d ".ai-operation" ]; then
        print_error ".ai-operation/ not found. Run setup.sh without --update first."
        exit 1
    fi

    if ! command -v git &>/dev/null; then
        print_error "git is required but not found."
        exit 1
    fi

    TMP_DIR=$(mktemp -d)
    trap "rm -rf $TMP_DIR" EXIT

    print_info "Cloning latest from GitHub..."
    git clone --depth=1 --quiet "$REPO_URL" "$TMP_DIR"

    # Overwrite framework code directories only
    for dir in "${FRAMEWORK_DIRS[@]}"; do
        if [ -d "$TMP_DIR/.ai-operation/$dir" ]; then
            rm -rf "$SCRIPT_DIR/.ai-operation/$dir"
            cp -r "$TMP_DIR/.ai-operation/$dir" "$SCRIPT_DIR/.ai-operation/$dir"
            print_ok "Updated .ai-operation/$dir"
        fi
    done

    # Update template/reference docs (not project_map content)
    for df in template_reference.md; do
        if [ -f "$TMP_DIR/.ai-operation/docs/$df" ]; then
            cp "$TMP_DIR/.ai-operation/docs/$df" "$SCRIPT_DIR/.ai-operation/docs/$df"
            print_ok "Updated docs/$df"
        fi
    done

    # Update rule files (NOT .mcp.json — handled separately below)
    for rf in .clinerules CLAUDE.md .cursorrules .windsurfrules .gitignore; do
        if [ -f "$TMP_DIR/$rf" ]; then
            cp "$TMP_DIR/$rf" "$SCRIPT_DIR/$rf"
            print_ok "Updated $rf"
        fi
    done

    # Smart-merge .mcp.json: keep user's Python path, update alwaysAllow from upstream
    if [ -f "$TMP_DIR/.mcp.json" ] && [ -f "$SCRIPT_DIR/.mcp.json" ]; then
        "$PYTHON_CMD" -c "
import json, sys
# Read both files
with open('$SCRIPT_DIR/.mcp.json', encoding='utf-8') as f:
    local = json.load(f)
with open('$TMP_DIR/.mcp.json', encoding='utf-8') as f:
    upstream = json.load(f)
# Preserve user's Python path and ensure args use absolute paths
import os
local_cmd = local.get('mcpServers',{}).get('project_architect',{}).get('command','')
if local_cmd and local_cmd != 'REPLACE_WITH_YOUR_VENV_PYTHON_PATH':
    upstream['mcpServers']['project_architect']['command'] = local_cmd
else:
    for p in ['$SCRIPT_DIR/.ai-operation/venv/Scripts/python.exe',
              '$SCRIPT_DIR/.ai-operation/venv/bin/python3']:
        if os.path.exists(p):
            upstream['mcpServers']['project_architect']['command'] = p
            break
# Fix args to absolute path (relative paths break when IDE cwd differs)
server_abs = os.path.abspath(os.path.join('$SCRIPT_DIR', '.ai-operation/mcp_server/server.py'))
if os.path.exists(server_abs):
    upstream['mcpServers']['project_architect']['args'] = [server_abs.replace(os.sep, '/')]
with open('$SCRIPT_DIR/.mcp.json', 'w', encoding='utf-8') as f:
    json.dump(upstream, f, indent=2, ensure_ascii=False)
print('OK')
" && print_ok "Smart-merged .mcp.json (kept Python path, updated alwaysAllow)" \
        || { cp "$TMP_DIR/.mcp.json" "$SCRIPT_DIR/.mcp.json"; print_warn ".mcp.json replaced (smart merge failed)"; }
    fi

    # Update setup scripts
    cp "$TMP_DIR/setup.sh" "$SCRIPT_DIR/setup.sh"
    [ -f "$TMP_DIR/setup.ps1" ] && cp "$TMP_DIR/setup.ps1" "$SCRIPT_DIR/setup.ps1"
    print_ok "Updated setup scripts"

    # Update Claude Code hooks (always overwrite — framework code)
    CLAUDE_HOOKS_SRC="$SCRIPT_DIR/.ai-operation/docs/templates/claude"
    CLAUDE_DIR="$SCRIPT_DIR/.claude"
    if [ -d "$CLAUDE_HOOKS_SRC" ]; then
        mkdir -p "$CLAUDE_DIR/hooks"
        for hook_file in check-dangerous.sh require-context.sh governance-capture.sh; do
            if [ -f "$CLAUDE_HOOKS_SRC/hooks/$hook_file" ]; then
                cp "$CLAUDE_HOOKS_SRC/hooks/$hook_file" "$CLAUDE_DIR/hooks/$hook_file"
                chmod +x "$CLAUDE_DIR/hooks/$hook_file"
            fi
        done
        print_ok "Updated Claude Code hooks"
        # Create settings.json if missing (don't overwrite user customizations)
        if [ ! -f "$CLAUDE_DIR/settings.json" ]; then
            cp "$CLAUDE_HOOKS_SRC/settings.json" "$CLAUDE_DIR/settings.json"
            print_ok "Created Claude Code settings.json"
        fi
    fi

    # Create .session_confirmed so cognitive gate doesn't lock out the user
    SESSION_FLAG="$SCRIPT_DIR/.ai-operation/.session_confirmed"
    if [ ! -f "$SESSION_FLAG" ]; then
        echo "0" > "$SESSION_FLAG"
        print_ok "Created session flag (cognitive gate unblocked)"
    fi

    # Add SESSION_KEY to corrections.md if missing (required by new cognitive gate)
    CORRECTIONS="$SCRIPT_DIR/.ai-operation/docs/project_map/corrections.md"
    if [ -f "$CORRECTIONS" ]; then
        if ! grep -q "SESSION_KEY:" "$CORRECTIONS"; then
            echo "" >> "$CORRECTIONS"
            echo "SESSION_KEY: init000" >> "$CORRECTIONS"
            print_ok "Added SESSION_KEY to corrections.md"
        fi
    fi

    # Migrate: add new template files to project_map if missing
    TEMPLATES_DIR="$SCRIPT_DIR/.ai-operation/docs/templates/project_map"
    PROJECT_MAP_DIR="$SCRIPT_DIR/.ai-operation/docs/project_map"
    if [ -d "$TEMPLATES_DIR" ] && [ -d "$PROJECT_MAP_DIR" ]; then
        for tmpl in "$TEMPLATES_DIR"/*.md; do
            fname=$(basename "$tmpl")
            target="$PROJECT_MAP_DIR/$fname"
            if [ ! -f "$target" ]; then
                cp "$tmpl" "$target"
                print_ok "Migrated new template: $fname"
            fi
        done
    fi

    # Rebuild venv if missing
    VENV_DIR="$SCRIPT_DIR/.ai-operation/venv"
    if [ ! -d "$VENV_DIR" ]; then
        print_warn "venv missing — rebuilding..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        if [ -f "$VENV_DIR/bin/pip" ]; then
            "$VENV_DIR/bin/pip" install --quiet --upgrade pip
            "$VENV_DIR/bin/pip" install --quiet "mcp[cli]" fastmcp
        elif [ -f "$VENV_DIR/Scripts/pip.exe" ]; then
            "$VENV_DIR/Scripts/pip.exe" install --quiet --upgrade pip
            "$VENV_DIR/Scripts/pip.exe" install --quiet "mcp[cli]" fastmcp
        fi
        print_ok "venv rebuilt and dependencies installed"
    fi

    # ── MIGRATE MODE (runs after update) ──────────────────────────────────────
    if [ "$MIGRATE_MODE" = true ]; then
        print_step "Migrate: Project data migration"

        BACKUP_DIR="$SCRIPT_DIR/.ai-operation/migrate_backup"
        mkdir -p "$BACKUP_DIR"
        MIGRATED_ITEMS=()

        # ── Step M1: Migrate old docs/project_map/ → .ai-operation/docs/project_map/ ──
        OLD_PM="$SCRIPT_DIR/docs/project_map"
        NEW_PM="$SCRIPT_DIR/.ai-operation/docs/project_map"

        if [ -d "$OLD_PM" ]; then
            print_info "Found old project_map at docs/project_map/"
            # Backup old path
            cp -r "$OLD_PM" "$BACKUP_DIR/old_project_map"

            for old_file in "$OLD_PM"/*.md; do
                [ -f "$old_file" ] || continue
                fname=$(basename "$old_file")
                new_file="$NEW_PM/$fname"

                if [ ! -f "$new_file" ]; then
                    # New file doesn't exist — copy
                    cp "$old_file" "$new_file"
                    print_ok "Migrated $fname (new)"
                    MIGRATED_ITEMS+=("$fname")
                elif grep -qc '待填写' "$new_file" 2>/dev/null && [ "$(grep -c '待填写' "$new_file")" -ge 3 ]; then
                    # New file is a template (3+ placeholders) — overwrite with old data
                    cp "$old_file" "$new_file"
                    print_ok "Migrated $fname (replaced template)"
                    MIGRATED_ITEMS+=("$fname")
                else
                    print_info "Skipped $fname (new path already has content)"
                fi
            done

            # Migrate details/ subdir
            if [ -d "$OLD_PM/details" ]; then
                mkdir -p "$NEW_PM/details"
                cp -n "$OLD_PM/details/"*.md "$NEW_PM/details/" 2>/dev/null && \
                    print_ok "Migrated details/ subfiles" || true
            fi

            # Migrate corrections/ subdir (key-value experience files)
            if [ -d "$OLD_PM/../corrections" ] || [ -d "$SCRIPT_DIR/docs/corrections" ]; then
                CORR_SRC="${OLD_PM}/../corrections"
                [ -d "$CORR_SRC" ] || CORR_SRC="$SCRIPT_DIR/docs/corrections"
                if [ -d "$CORR_SRC" ]; then
                    mkdir -p "$NEW_PM/../corrections"
                    cp -n "$CORR_SRC/"*.md "$NEW_PM/../corrections/" 2>/dev/null && \
                        print_ok "Migrated corrections/ experience files" || true
                fi
            fi

            # Leave pointer in old location
            echo "# Migrated" > "$OLD_PM/README.md"
            echo "Project map data has been migrated to .ai-operation/docs/project_map/" >> "$OLD_PM/README.md"
            echo "This directory can be safely deleted." >> "$OLD_PM/README.md"
            print_ok "Left migration pointer in old docs/project_map/"
        else
            print_info "No old docs/project_map/ found — skipping path migration"
        fi

        # ── Step M2: Extract custom rules from old CLAUDE.md / .clinerules ──────
        OLD_CLAUDE="$SCRIPT_DIR/CLAUDE.md"
        OLD_CLINERULES="$SCRIPT_DIR/.clinerules"
        RULES_D="$SCRIPT_DIR/.ai-operation/rules.d"
        CUSTOM_RULES="$RULES_D/project_custom.md"

        # Check if there's a pre-update backup of CLAUDE.md in git
        # or if the current CLAUDE.md still has old-format content
        EXTRACT_RULES=false

        # Strategy: if backup exists from before this update, use it
        if [ -f "$BACKUP_DIR/CLAUDE.md.bak" ]; then
            EXTRACT_RULES=true
            EXTRACT_FROM="$BACKUP_DIR/CLAUDE.md.bak"
        fi

        # If no backup but current CLAUDE.md has content beyond framework template,
        # try to extract from git history
        if [ "$EXTRACT_RULES" = false ] && command -v git &>/dev/null; then
            # Check if CLAUDE.md was different in previous commit
            OLD_CONTENT=$(git show HEAD~1:CLAUDE.md 2>/dev/null || echo "")
            if [ -n "$OLD_CONTENT" ]; then
                OLD_LINES=$(echo "$OLD_CONTENT" | wc -l)
                if [ "$OLD_LINES" -gt 70 ]; then
                    # Old CLAUDE.md was significantly larger — likely has custom rules
                    echo "$OLD_CONTENT" > "$BACKUP_DIR/CLAUDE.md.bak"
                    EXTRACT_RULES=true
                    EXTRACT_FROM="$BACKUP_DIR/CLAUDE.md.bak"
                    print_info "Recovered old CLAUDE.md from git history ($OLD_LINES lines)"
                fi
            fi
        fi

        if [ "$EXTRACT_RULES" = true ] && [ -f "$EXTRACT_FROM" ]; then
            # Use Python to extract custom sections
            "$PYTHON_CMD" -c "
import sys

# Read old CLAUDE.md
with open('$EXTRACT_FROM', encoding='utf-8', errors='ignore') as f:
    old_content = f.read()

# Read new .clinerules (the framework template)
try:
    with open('$OLD_CLINERULES', encoding='utf-8', errors='ignore') as f:
        new_content = f.read()
except FileNotFoundError:
    new_content = ''

# Known framework section headers (these exist in both old and new)
framework_headers = [
    '开机自检', '源文件索引', '项目记忆', '规范与协议',
    '指令路由', 'AI-Operation', 'auto-generated',
    'Do NOT edit', '.clinerules', 'MCP tools',
]

# Extract sections from old that are NOT framework sections
lines = old_content.split('\n')
custom_sections = []
current_section = []
current_header = ''
in_custom = False

for line in lines:
    if line.startswith('## ') or line.startswith('# '):
        # Save previous section if it was custom
        if in_custom and current_section:
            custom_sections.append('\n'.join(current_section))

        # Check if this header is a framework header
        header_text = line.lstrip('#').strip()
        is_framework = any(fh in header_text or fh in line for fh in framework_headers)

        if is_framework:
            in_custom = False
            current_section = []
        else:
            in_custom = True
            current_section = [line]
        current_header = header_text
    elif in_custom:
        current_section.append(line)

# Don't forget last section
if in_custom and current_section:
    custom_sections.append('\n'.join(current_section))

if custom_sections:
    result = '# 项目自定义规则\\n\\n'
    result += '> 从旧 CLAUDE.md 迁移。由 setup.sh --migrate 自动提取。\\n'
    result += '> 此文件由 [读档] 自动加载到 AI 上下文中。\\n\\n'
    result += '\\n\\n---\\n\\n'.join(custom_sections)
    result += '\\n'

    with open('$CUSTOM_RULES', 'w', encoding='utf-8') as f:
        f.write(result)
    print(f'EXTRACTED:{len(custom_sections)} sections')
else:
    print('NO_CUSTOM_CONTENT')
" 2>/dev/null
            EXTRACT_RESULT=$?
            if [ -f "$CUSTOM_RULES" ]; then
                SECTION_COUNT=$(head -1 "$CUSTOM_RULES" | wc -c)  # rough check
                print_ok "Extracted custom rules → .ai-operation/rules.d/project_custom.md"
                MIGRATED_ITEMS+=("custom_rules")
            else
                print_info "No custom rules found in old CLAUDE.md"
            fi
        else
            print_info "No old CLAUDE.md to extract rules from"
        fi

        # ── Migration Summary ──────────────────────────────────────────────────
        echo ""
        if [ ${#MIGRATED_ITEMS[@]} -gt 0 ]; then
            echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}${BOLD}║   ✅  Migration complete!                         ║${NC}"
            echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "  ${YELLOW}Migrated:${NC}"
            for item in "${MIGRATED_ITEMS[@]}"; do
                echo -e "    - $item"
            done
            echo ""
            echo -e "  ${YELLOW}Backup:${NC}  .ai-operation/migrate_backup/"
            echo ""
            echo -e "  ${BOLD}Review checklist:${NC}"
            echo -e "    1. Check .ai-operation/docs/project_map/ — data migrated correctly?"
            [ -f "$CUSTOM_RULES" ] && \
            echo -e "    2. Check .ai-operation/rules.d/project_custom.md — custom rules complete?"
            echo -e "    3. Run [初始化项目] with Phase 3.5 audit to verify"
            echo -e "    4. Old docs/project_map/ can be deleted after verification"
        else
            echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}${BOLD}║   ✅  Update complete! (nothing to migrate)       ║${NC}"
            echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
        fi
        echo ""
        echo -e "  Restart your IDE to reload MCP servers."
        echo ""
        exit 0
    fi

    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║   ✅  Update complete!                            ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${YELLOW}Preserved:${NC} venv/, project_map/, audit.log, MCP configs"
    echo -e "  ${YELLOW}Updated:${NC}   mcp_server/, scripts/, skills/, hooks/, cli/, rules"
    echo ""
    echo -e "  Restart your IDE to reload MCP servers."
    echo ""
    exit 0
fi

# ── Step 2: Download scaffold files (FRESH INSTALL, remote mode only) ────────
print_step "Step 2/7: Downloading scaffold files"

if [ "$REMOTE_MODE" = true ]; then
    print_info "Installing into: $SCRIPT_DIR"

    if ! command -v git &>/dev/null; then
        print_error "git is required but not found. Please install git first."
        exit 1
    fi

    TMP_DIR=$(mktemp -d)
    trap "rm -rf $TMP_DIR" EXIT

    print_info "Cloning scaffold from GitHub..."
    git clone --depth=1 --quiet "$REPO_URL" "$TMP_DIR"

    for item in "${SCAFFOLD_ITEMS[@]}"; do
        if [ -e "$TMP_DIR/$item" ]; then
            cp -r "$TMP_DIR/$item" "$SCRIPT_DIR/"
            print_ok "Copied $item"
        fi
    done
    # Copy setup scripts
    cp "$TMP_DIR/setup.sh" "$SCRIPT_DIR/setup.sh"
    [ -f "$TMP_DIR/setup.ps1" ] && cp "$TMP_DIR/setup.ps1" "$SCRIPT_DIR/setup.ps1"

    print_ok "Scaffold files installed into $(pwd)"
else
    print_ok "Running from local scaffold directory — skipping download"
fi

# ── Step 2.5: Initialize project_map from templates ──────────────────────────
PROJECT_MAP_DIR="$SCRIPT_DIR/.ai-operation/docs/project_map"
TEMPLATES_DIR="$SCRIPT_DIR/.ai-operation/docs/templates/project_map"

if [ ! -d "$PROJECT_MAP_DIR" ]; then
    print_step "Step 2.5: Initializing project_map from templates"
    mkdir -p "$PROJECT_MAP_DIR/details"
    if [ -d "$TEMPLATES_DIR" ]; then
        cp "$TEMPLATES_DIR"/*.md "$PROJECT_MAP_DIR/"
        print_ok "project_map initialized with templates (all [待填写])"
    else
        print_warn "Templates not found at $TEMPLATES_DIR"
    fi
else
    print_ok "project_map already exists — skipping template copy"
fi

# ── Step 3: Create virtual environment ───────────────────────────────────────
print_step "Step 3/7: Creating virtual environment at .ai-operation/venv/"

VENV_DIR="$SCRIPT_DIR/.ai-operation/venv"

if [ -d "$VENV_DIR" ]; then
    print_warn "venv already exists — skipping creation, will update dependencies"
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    print_ok "Virtual environment created at $VENV_DIR"
fi

# Resolve Python / pip paths (cross-platform)
if [ -f "$VENV_DIR/bin/python3" ]; then
    VENV_PYTHON="$VENV_DIR/bin/python3"
    VENV_PIP="$VENV_DIR/bin/pip"
elif [ -f "$VENV_DIR/Scripts/python.exe" ]; then
    VENV_PYTHON="$VENV_DIR/Scripts/python.exe"
    VENV_PIP="$VENV_DIR/Scripts/pip.exe"
else
    print_error "Could not locate venv Python. Setup failed."
    exit 1
fi

print_ok "Using Python at: $VENV_PYTHON"

# ── Step 4: Install MCP dependencies ─────────────────────────────────────────
print_step "Step 4/7: Installing MCP dependencies"

"$VENV_PIP" install --quiet --upgrade pip
"$VENV_PIP" install --quiet "mcp[cli]" fastmcp

if "$VENV_PYTHON" -c "import mcp; import fastmcp" 2>/dev/null; then
    MCP_VERSION=$("$VENV_PYTHON" -c "import mcp; print(mcp.__version__)" 2>/dev/null || echo "unknown")
    print_ok "mcp (v$MCP_VERSION) and fastmcp installed successfully"
else
    print_error "Dependency installation failed. Check your network connection and try again."
    exit 1
fi

# ── Step 5: Write Python path into all IDE MCP configs ────────────────────────
print_step "Step 5/7: Configuring MCP for all IDEs"

MCP_CONFIGS=(
    "$SCRIPT_DIR/.roo/mcp.json"
    "$SCRIPT_DIR/.cursor/mcp.json"
    "$SCRIPT_DIR/.windsurf/mcp.json"
    "$SCRIPT_DIR/.mcp.json"
)

for MCP_JSON_PATH in "${MCP_CONFIGS[@]}"; do
    if [ -f "$MCP_JSON_PATH" ]; then
        # Replace placeholder — works on both GNU sed (Linux) and BSD sed (macOS)
        if sed --version 2>/dev/null | grep -q GNU; then
            sed -i "s|REPLACE_WITH_YOUR_VENV_PYTHON_PATH|$VENV_PYTHON|g" "$MCP_JSON_PATH"
        else
            sed -i '' "s|REPLACE_WITH_YOUR_VENV_PYTHON_PATH|$VENV_PYTHON|g" "$MCP_JSON_PATH"
        fi

        if grep -q "REPLACE_WITH_YOUR_VENV_PYTHON_PATH" "$MCP_JSON_PATH"; then
            print_warn "Failed to update $MCP_JSON_PATH — edit manually"
        else
            print_ok "$(basename "$(dirname "$MCP_JSON_PATH")")/$(basename "$MCP_JSON_PATH") updated"
        fi
    fi
done

# ── Step 5.5: Install repomix ────────────────────────────────────────────────
print_step "Step 5.5/7: Installing repomix (codebase map tool)"

REPOMIX_INSTALLED=false

if command -v npx &>/dev/null; then
    print_ok "npx found — repomix will run on-demand via 'npx repomix' (no pre-download)"
    REPOMIX_INSTALLED=true
fi

if [ "$REPOMIX_INSTALLED" = false ]; then
    if "$VENV_PIP" install --quiet repomix 2>/dev/null; then
        print_ok "repomix installed via pip"
        REPOMIX_INSTALLED=true
    else
        print_warn "repomix not installed (no npx or pip fallback). Project-bootstrap will skip the global map step."
        print_info "  To install manually: npm install -g repomix  OR  pip install repomix"
    fi
fi

# ── Step 5.6: Install oh-my-mermaid ─────────────────────────────────────────
print_step "Step 5.6/7: Installing oh-my-mermaid (architecture diagrams)"

if command -v npm &>/dev/null; then
    if npm list -g oh-my-mermaid &>/dev/null; then
        print_ok "oh-my-mermaid already installed"
    else
        if npm install -g oh-my-mermaid &>/dev/null; then
            print_ok "oh-my-mermaid installed (omm CLI for [架构扫描])"
        else
            print_warn "oh-my-mermaid install failed. [架构扫描] will not work."
            print_info "  To install manually: npm install -g oh-my-mermaid"
        fi
    fi
else
    print_warn "npm not found — skipping oh-my-mermaid install"
    print_info "  Install Node.js, then: npm install -g oh-my-mermaid"
fi

# ── Step 6: Verify MCP server ─────────────────────────────────────────────────
print_step "Step 6/7: Verifying MCP server"

MCP_SERVER_DIR="$SCRIPT_DIR/.ai-operation/mcp_server"

if "$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$MCP_SERVER_DIR')
from tools.architect import register_architect_tools
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test')
register_architect_tools(mcp)
print('OK')
" 2>/dev/null | grep -q "OK"; then
    print_ok "MCP server imports verified successfully"
else
    print_warn "MCP server import check failed — try: $VENV_PYTHON .ai-operation/mcp_server/server.py"
fi

# ── Step 7: Install Claude Code hooks (.claude/) ────────────────────────────
print_step "Step 7/9: Installing Claude Code hooks"

CLAUDE_HOOKS_SRC="$SCRIPT_DIR/.ai-operation/docs/templates/claude"
CLAUDE_DIR="$SCRIPT_DIR/.claude"

if [ -d "$CLAUDE_HOOKS_SRC" ]; then
    # Create .claude/hooks/ if it doesn't exist
    mkdir -p "$CLAUDE_DIR/hooks"

    # Copy hook scripts (always overwrite — these are framework code)
    for hook_file in check-dangerous.sh require-context.sh governance-capture.sh; do
        if [ -f "$CLAUDE_HOOKS_SRC/hooks/$hook_file" ]; then
            cp "$CLAUDE_HOOKS_SRC/hooks/$hook_file" "$CLAUDE_DIR/hooks/$hook_file"
            chmod +x "$CLAUDE_DIR/hooks/$hook_file"
        fi
    done
    print_ok "Claude Code hooks installed (cognitive gate + dangerous guard + audit)"

    # Copy settings.json only if it doesn't exist (don't overwrite user customizations)
    if [ ! -f "$CLAUDE_DIR/settings.json" ]; then
        cp "$CLAUDE_HOOKS_SRC/settings.json" "$CLAUDE_DIR/settings.json"
        print_ok "Claude Code settings.json created with hook configuration"
    else
        print_ok "Claude Code settings.json already exists — preserved"
    fi

    # Create initial .session_confirmed so AI can run [初始化项目] on first use
    SESSION_FLAG="$SCRIPT_DIR/.ai-operation/.session_confirmed"
    if [ ! -f "$SESSION_FLAG" ]; then
        echo "0" > "$SESSION_FLAG"
        print_ok "Initial session confirmed (allows first [初始化项目])"
    fi
else
    print_warn "Claude hooks template not found — skipping"
fi

# ── Step 8: Install git hooks ────────────────────────────────────────────────
print_step "Step 8/9: Installing git hooks"

INSTALL_HOOKS="$SCRIPT_DIR/.ai-operation/scripts/install-hooks.sh"
if [ -f "$INSTALL_HOOKS" ] && [ -d "$SCRIPT_DIR/.git" ]; then
    bash "$INSTALL_HOOKS"
    print_ok "Git pre-commit hook installed (auto-sync rules + project_map guard)"
else
    print_warn "Git hooks not installed (not a git repo or install script missing)"
fi

# ── Step 9: Verify IDE rule files ────────────────────────────────────────────
print_step "Step 9/9: Checking IDE rule files"

RULE_FILES=(".clinerules" "CLAUDE.md" ".cursorrules" ".windsurfrules")
for rf in "${RULE_FILES[@]}"; do
    if [ -f "$SCRIPT_DIR/$rf" ]; then
        print_ok "$rf present"
    else
        print_warn "$rf missing"
    fi
done

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   ✅  Setup complete!                             ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. Open this project in your IDE:"
echo -e "     ${YELLOW}Roo Code${NC}  — reads .clinerules + .roo/mcp.json"
echo -e "     ${YELLOW}Cursor${NC}    — reads .cursorrules + .cursor/mcp.json"
echo -e "     ${YELLOW}Windsurf${NC}  — reads .windsurfrules + .windsurf/mcp.json"
echo -e "     ${YELLOW}Claude Code${NC} — reads CLAUDE.md + .mcp.json"
echo -e "  2. Reload MCP servers (Ctrl+Shift+P or restart IDE)"
echo -e "  3. In your first chat with the AI, type:"
echo -e "     ${BLUE}[初始化项目]${NC}"
echo -e ""
echo -e "  ${BOLD}Tip:${NC} During [初始化项目], the AI will run 'npx repomix --compress'"
echo -e "  to generate a full codebase map. Requires Node.js / npx."
echo ""
echo -e "  ${BOLD}MCP server:${NC}  $VENV_PYTHON .ai-operation/mcp_server/server.py"
echo -e "  ${BOLD}Framework:${NC}   .ai-operation/"
echo -e "  ${BOLD}IDE configs:${NC} .roo/ .cursor/ .windsurf/ .mcp.json"
echo ""
