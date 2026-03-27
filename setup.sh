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
#   3. Creates a virtual environment at ./venv/
#   4. Installs MCP dependencies (mcp[cli], fastmcp)
#   5. Installs repomix (global codebase map tool) via npx or pip
#   6. Auto-detects the venv Python path and writes it into .roo/mcp.json
#   7. Verifies the MCP server can start
#   8. Prints next steps
# =============================================================================

set -e

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
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Vibe Coding Agent Framework — Setup          ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Determine install target directory ───────────────────────────────────────
# If run via curl | bash, BASH_SOURCE[0] is empty or /dev/stdin.
# In that case, install into the current working directory (the user's project).
if [ -n "${BASH_SOURCE[0]}" ] && [ "${BASH_SOURCE[0]}" != "/dev/stdin" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REMOTE_MODE=false
else
    SCRIPT_DIR="$(pwd)"
    REMOTE_MODE=true
fi

REPO_URL="https://github.com/lyc812866241-a11y/AI-Operation.git"
SCAFFOLD_FILES=(".clinerules" ".roo" "docs" "mcp_server" "skills")

# ── Step 1: Detect Python ─────────────────────────────────────────────────────
print_step "Step 1/6: Checking Python version"

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

# ── Step 2: Download scaffold files (remote mode only) ───────────────────────
print_step "Step 2/6: Downloading scaffold files"

if [ "$REMOTE_MODE" = true ]; then
    print_info "Installing into: $SCRIPT_DIR"

    # Check for git
    if ! command -v git &>/dev/null; then
        print_error "git is required but not found. Please install git first."
        exit 1
    fi

    TMP_DIR=$(mktemp -d)
    trap "rm -rf $TMP_DIR" EXIT

    print_info "Cloning scaffold from GitHub..."
    git clone --depth=1 --quiet "$REPO_URL" "$TMP_DIR"

    # Copy scaffold files into the target project directory
    for item in "${SCAFFOLD_FILES[@]}"; do
        if [ -e "$TMP_DIR/$item" ]; then
            cp -r "$TMP_DIR/$item" "$SCRIPT_DIR/"
            print_ok "Copied $item"
        fi
    done
    # Also copy setup.sh itself so the user has it locally
    cp "$TMP_DIR/setup.sh" "$SCRIPT_DIR/setup.sh"

    # Point SCRIPT_DIR to the installed location for subsequent steps
    SCRIPT_DIR="$SCRIPT_DIR"
    print_ok "Scaffold files installed into $(pwd)"
else
    print_ok "Running from local scaffold directory — skipping download"
fi

# ── Step 3: Create virtual environment ───────────────────────────────────────
print_step "Step 3/6: Creating virtual environment at ./venv/"

VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    print_warn "venv/ already exists — skipping creation, will update dependencies"
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
print_step "Step 4/6: Installing MCP dependencies"

"$VENV_PIP" install --quiet --upgrade pip
"$VENV_PIP" install --quiet "mcp[cli]" fastmcp

if "$VENV_PYTHON" -c "import mcp; import fastmcp" 2>/dev/null; then
    MCP_VERSION=$("$VENV_PYTHON" -c "import mcp; print(mcp.__version__)" 2>/dev/null || echo "unknown")
    print_ok "mcp (v$MCP_VERSION) and fastmcp installed successfully"
else
    print_error "Dependency installation failed. Check your network connection and try again."
    exit 1
fi

# ── Step 5: Write Python path into .roo/mcp.json ─────────────────────────────
print_step "Step 5/6: Configuring .roo/mcp.json"

MCP_JSON_PATH="$SCRIPT_DIR/.roo/mcp.json"

if [ ! -f "$MCP_JSON_PATH" ]; then
    print_error ".roo/mcp.json not found at $MCP_JSON_PATH"
    exit 1
fi

# Replace placeholder — works on both GNU sed (Linux) and BSD sed (macOS)
if sed --version 2>/dev/null | grep -q GNU; then
    sed -i "s|REPLACE_WITH_YOUR_VENV_PYTHON_PATH|$VENV_PYTHON|g" "$MCP_JSON_PATH"
else
    sed -i '' "s|REPLACE_WITH_YOUR_VENV_PYTHON_PATH|$VENV_PYTHON|g" "$MCP_JSON_PATH"
fi

if grep -q "REPLACE_WITH_YOUR_VENV_PYTHON_PATH" "$MCP_JSON_PATH"; then
    print_error "Failed to update .roo/mcp.json. Please edit it manually:"
    print_info "  Replace REPLACE_WITH_YOUR_VENV_PYTHON_PATH with: $VENV_PYTHON"
    exit 1
else
    print_ok ".roo/mcp.json updated with Python path: $VENV_PYTHON"
fi

# ── Step 5.5: Install repomix ────────────────────────────────────────────────
print_step "Step 5.5/6: Installing repomix (codebase map tool)"

REPOMIX_INSTALLED=false

# Try npx first (Node.js ecosystem, most common)
if command -v npx &>/dev/null; then
    print_info "npx found — repomix will be available via 'npx repomix'"
    # Warm up the npx cache so first run is fast
    npx repomix --version &>/dev/null 2>&1 && print_ok "repomix (npx) ready" || print_warn "npx repomix cache warm-up failed — will work on first use"
    REPOMIX_INSTALLED=true
fi

# Fallback: try pip install repomix (Python port)
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
print_step "Step 6/6: Verifying MCP server"

if "$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/mcp_server')
from tools.architect import register_architect_tools
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test')
register_architect_tools(mcp)
print('OK')
" 2>/dev/null | grep -q "OK"; then
    print_ok "MCP server imports verified successfully"
else
    print_warn "MCP server import check failed — try: $VENV_PYTHON mcp_server/server.py"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   ✅  Setup complete!                             ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. Open this project in your IDE (Roo Code / Cursor / Windsurf)"
echo -e "  2. Reload MCP servers:"
echo -e "     ${YELLOW}Roo Code${NC}: Ctrl+Shift+P → 'Roo Code: Refresh MCP Servers'"
echo -e "     ${YELLOW}Cursor${NC}  : Restart the IDE"
echo -e "  3. In your first chat with the AI, type:"
echo -e "     ${BLUE}[初始化项目]${NC}"
echo -e ""
echo -e "  ${BOLD}Tip:${NC} During [初始化项目], the AI will run 'npx repomix --compress'"
echo -e "  to generate a full codebase map. This ensures NO modules are missed."
echo -e "  Requires Node.js / npx to be available in the project's environment."
echo ""
echo -e "  ${BOLD}MCP server path:${NC} $VENV_PYTHON mcp_server/server.py"
echo -e "  ${BOLD}Config file:${NC}     $MCP_JSON_PATH"
echo ""
