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
if [ "$1" = "--update" ] || [ "$1" = "-u" ]; then
    UPDATE_MODE=true
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
if [ "$UPDATE_MODE" = true ]; then
    echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}${BOLD}║     Vibe Coding Agent Framework — UPDATE         ║${NC}"
    echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
else
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║     Vibe Coding Agent Framework — Setup          ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
fi
echo ""

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
    for df in template_reference.md taskSpec_template.md codebaseSummary.md; do
        if [ -f "$TMP_DIR/.ai-operation/docs/$df" ]; then
            cp "$TMP_DIR/.ai-operation/docs/$df" "$SCRIPT_DIR/.ai-operation/docs/$df"
            print_ok "Updated docs/$df"
        fi
    done

    # Update rule files
    for rf in .clinerules CLAUDE.md .cursorrules .windsurfrules; do
        if [ -f "$TMP_DIR/$rf" ]; then
            cp "$TMP_DIR/$rf" "$SCRIPT_DIR/$rf"
            print_ok "Updated $rf"
        fi
    done

    # Update setup scripts
    cp "$TMP_DIR/setup.sh" "$SCRIPT_DIR/setup.sh"
    [ -f "$TMP_DIR/setup.ps1" ] && cp "$TMP_DIR/setup.ps1" "$SCRIPT_DIR/setup.ps1"
    print_ok "Updated setup scripts"

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

# ── Step 7: Install git hooks ────────────────────────────────────────────────
print_step "Step 7/8: Installing git hooks"

INSTALL_HOOKS="$SCRIPT_DIR/.ai-operation/scripts/install-hooks.sh"
if [ -f "$INSTALL_HOOKS" ] && [ -d "$SCRIPT_DIR/.git" ]; then
    bash "$INSTALL_HOOKS"
    print_ok "Git pre-commit hook installed (auto-sync rules + project_map guard)"
else
    print_warn "Git hooks not installed (not a git repo or install script missing)"
fi

# ── Step 8: Verify IDE rule files ────────────────────────────────────────────
print_step "Step 8/8: Checking IDE rule files"

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
