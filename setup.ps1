# =============================================================================
# Vibe Coding Agent Framework - One-Command Installer (Windows PowerShell)
# =============================================================================
#
# USAGE (from your project root directory):
#
#   irm https://raw.githubusercontent.com/lyc812866241-a11y/AI-Operation/master/setup.ps1 | iex
#
# Or download and run locally:
#   .\setup.ps1
#
# What this script does:
#   1. Checks for Python 3.8+
#   2. Downloads scaffold files into the current directory
#   3. Creates a virtual environment at .\.ai-operation\venv\
#   4. Installs MCP dependencies (mcp[cli], fastmcp)
#   5. Installs repomix (global codebase map tool) via npx or pip
#   6. Auto-detects the venv Python path and writes it into all IDE MCP configs
#   7. Generates IDE rule files (.clinerules, CLAUDE.md, .cursorrules, .windsurfrules)
#   8. Verifies the MCP server can start
# =============================================================================

param(
    [switch]$Update  # Update mode: only overwrite framework code, preserve local products
)

$ErrorActionPreference = "Stop"

# -- Colors --
function Write-Step($msg)  { Write-Host "`n>> $msg" -ForegroundColor Blue }
function Write-Ok($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Info($msg)  { Write-Host "  $msg" }

# -- Banner --
Write-Host ""
if ($Update) {
    Write-Host "+==================================================+" -ForegroundColor Cyan
    Write-Host "|     Vibe Coding Agent Framework - UPDATE          |" -ForegroundColor Cyan
    Write-Host "+==================================================+" -ForegroundColor Cyan
} else {
    Write-Host "+==================================================+" -ForegroundColor White
    Write-Host "|     Vibe Coding Agent Framework - Setup           |" -ForegroundColor White
    Write-Host "+==================================================+" -ForegroundColor White
}
Write-Host ""

$REPO_URL = "https://github.com/lyc812866241-a11y/AI-Operation.git"
$INSTALL_DIR = Get-Location

# Framework code directories — these get overwritten on update
$FRAMEWORK_DIRS = @(
    "mcp_server",
    "scripts",
    "skills",
    "hooks",
    "cli",
    "rules.d"
)

# Local products — NEVER overwritten on update
# venv/, docs/project_map/, audit.log, .save_staging.json

$SCAFFOLD_ITEMS = @(
    ".ai-operation",
    ".clinerules",
    ".cursorrules",
    ".windsurfrules",
    "CLAUDE.md",
    ".roo",
    ".cursor",
    ".windsurf",
    ".mcp.json"
)

# -- Step 1: Detect Python --
Write-Step "Step 1/7: Checking Python version"

$PYTHON_CMD = $null
foreach ($cmd in @("python3", "python", "py")) {
    try {
        $version = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($version) {
            $parts = $version.Split(".")
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -ge 3 -and $minor -ge 8) {
                $PYTHON_CMD = $cmd
                Write-Ok "Found $cmd (Python $version)"
                break
            }
        }
    } catch {}
}

if (-not $PYTHON_CMD) {
    Write-Err "Python 3.8+ not found. Please install Python first."
    Write-Info "  Download: https://www.python.org/downloads/"
    Write-Info "  Or via winget: winget install Python.Python.3.11"
    exit 1
}

# ── UPDATE MODE ─────────────────────────────────────────────────────────────
# Only overwrite framework code directories, preserve local products
# (venv, project_map, audit.log, .save_staging.json, MCP configs)
if ($Update) {
    Write-Step "Update: Downloading latest framework code"

    if (-not (Test-Path ".ai-operation" -PathType Container)) {
        Write-Err ".ai-operation/ not found. Run setup.ps1 without -Update first."
        exit 1
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Err "git is required but not found."
        exit 1
    }

    $TMP_DIR = Join-Path $env:TEMP "ai-operation-update-$(Get-Random)"
    try {
        Write-Info "Cloning latest from GitHub..."
        git clone --depth=1 --quiet $REPO_URL $TMP_DIR 2>&1 | Out-Null

        # Overwrite framework code directories only
        foreach ($dir in $FRAMEWORK_DIRS) {
            $src = Join-Path $TMP_DIR ".ai-operation\$dir"
            $dst = Join-Path $INSTALL_DIR ".ai-operation\$dir"
            if (Test-Path $src) {
                if (Test-Path $dst) {
                    Remove-Item $dst -Recurse -Force
                }
                Copy-Item $src $dst -Recurse -Force
                Write-Ok "Updated .ai-operation\$dir"
            }
        }

        # Update template/reference docs (not project_map content)
        $docFiles = @("template_reference.md", "taskSpec_template.md", "codebaseSummary.md")
        foreach ($df in $docFiles) {
            $src = Join-Path $TMP_DIR ".ai-operation\docs\$df"
            $dst = Join-Path $INSTALL_DIR ".ai-operation\docs\$df"
            if (Test-Path $src) {
                Copy-Item $src $dst -Force
                Write-Ok "Updated docs\$df"
            }
        }

        # Update rule files
        $ruleFiles = @(".clinerules", "CLAUDE.md", ".cursorrules", ".windsurfrules")
        foreach ($rf in $ruleFiles) {
            $src = Join-Path $TMP_DIR $rf
            $dst = Join-Path $INSTALL_DIR $rf
            if (Test-Path $src) {
                Copy-Item $src $dst -Force
                Write-Ok "Updated $rf"
            }
        }

        # Update setup scripts themselves
        Copy-Item (Join-Path $TMP_DIR "setup.sh") (Join-Path $INSTALL_DIR "setup.sh") -Force
        Copy-Item (Join-Path $TMP_DIR "setup.ps1") (Join-Path $INSTALL_DIR "setup.ps1") -Force
        Write-Ok "Updated setup scripts"

    } finally {
        if (Test-Path $TMP_DIR) { Remove-Item $TMP_DIR -Recurse -Force }
    }

    # Rebuild venv if missing
    $VENV_DIR = Join-Path $INSTALL_DIR ".ai-operation\venv"
    if (-not (Test-Path $VENV_DIR)) {
        Write-Warn "venv missing — rebuilding..."
        & $PYTHON_CMD -m venv $VENV_DIR
        $VENV_PIP = Join-Path $VENV_DIR "Scripts\pip.exe"
        & $VENV_PIP install --quiet --upgrade pip 2>&1 | Out-Null
        & $VENV_PIP install --quiet "mcp[cli]" fastmcp 2>&1 | Out-Null
        Write-Ok "venv rebuilt and dependencies installed"
    }

    # Verify MCP server
    $VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
    $mcpServerDir = Join-Path $INSTALL_DIR ".ai-operation\mcp_server"
    $verifyResult = & $VENV_PYTHON -c @"
import sys
sys.path.insert(0, r'$mcpServerDir')
from tools.architect import register_architect_tools
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test')
register_architect_tools(mcp)
print('OK')
"@ 2>&1
    if ($verifyResult -match "OK") {
        Write-Ok "MCP server verified"
    } else {
        Write-Warn "MCP server verification failed — check manually"
    }

    Write-Host ""
    Write-Host "+==================================================+" -ForegroundColor Green
    Write-Host "|   Update complete!                                |" -ForegroundColor Green
    Write-Host "+==================================================+" -ForegroundColor Green
    Write-Host ""
    Write-Host "Preserved: venv/, project_map/, audit.log, MCP configs" -ForegroundColor Yellow
    Write-Host "Updated:   mcp_server/, scripts/, skills/, hooks/, cli/, rules" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Restart your IDE to reload MCP servers." -ForegroundColor White
    Write-Host ""
    exit 0
}

# -- Step 2: Download scaffold files (FRESH INSTALL) --
Write-Step "Step 2/7: Downloading scaffold files"

$isLocal = Test-Path ".ai-operation" -PathType Container
if ($isLocal) {
    Write-Ok "Running from local scaffold directory - skipping download"
} else {
    Write-Info "Installing into: $INSTALL_DIR"

    # Check for git
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Err "git is required but not found. Please install git first."
        exit 1
    }

    $TMP_DIR = Join-Path $env:TEMP "ai-operation-$(Get-Random)"
    try {
        Write-Info "Cloning scaffold from GitHub..."
        git clone --depth=1 --quiet $REPO_URL $TMP_DIR 2>&1 | Out-Null

        foreach ($item in $SCAFFOLD_ITEMS) {
            $src = Join-Path $TMP_DIR $item
            $dst = Join-Path $INSTALL_DIR $item
            if (Test-Path $src) {
                if (Test-Path $src -PathType Container) {
                    Copy-Item $src $dst -Recurse -Force
                } else {
                    Copy-Item $src $dst -Force
                }
                Write-Ok "Copied $item"
            }
        }
        # Copy setup scripts
        Copy-Item (Join-Path $TMP_DIR "setup.sh") (Join-Path $INSTALL_DIR "setup.sh") -Force
        Copy-Item (Join-Path $TMP_DIR "setup.ps1") (Join-Path $INSTALL_DIR "setup.ps1") -Force
    } finally {
        if (Test-Path $TMP_DIR) { Remove-Item $TMP_DIR -Recurse -Force }
    }

    Write-Ok "Scaffold files installed"
}

# -- Step 3: Create virtual environment --
Write-Step "Step 3/7: Creating virtual environment at .ai-operation\venv\"

$VENV_DIR = Join-Path $INSTALL_DIR ".ai-operation\venv"

if (Test-Path $VENV_DIR) {
    Write-Warn "venv already exists - skipping creation, will update dependencies"
} else {
    & $PYTHON_CMD -m venv $VENV_DIR
    Write-Ok "Virtual environment created at $VENV_DIR"
}

# Resolve Python/pip paths
$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$VENV_PIP = Join-Path $VENV_DIR "Scripts\pip.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    # Try Unix-style layout (WSL/Git Bash venv)
    $VENV_PYTHON = Join-Path $VENV_DIR "bin\python3"
    $VENV_PIP = Join-Path $VENV_DIR "bin\pip"
}

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Err "Could not locate venv Python at $VENV_DIR. Setup failed."
    exit 1
}

Write-Ok "Using Python at: $VENV_PYTHON"

# -- Step 4: Install MCP dependencies --
Write-Step "Step 4/7: Installing MCP dependencies"

# Use python -m pip to avoid Windows "pip.exe in use" error during self-upgrade
& $VENV_PYTHON -m pip install --quiet --upgrade pip 2>&1 | Out-Null
& $VENV_PYTHON -m pip install --quiet "mcp[cli]" fastmcp 2>&1 | Out-Null

$testImport = & $VENV_PYTHON -c "import mcp; import fastmcp; print('OK')" 2>&1
if ($testImport -match "OK") {
    $mcpVer = & $VENV_PYTHON -c "import mcp; print(mcp.__version__)" 2>$null
    Write-Ok "mcp (v$mcpVer) and fastmcp installed successfully"
} else {
    Write-Err "Dependency installation failed. Check your network connection."
    exit 1
}

# -- Step 5: Write Python path into all IDE MCP configs --
Write-Step "Step 5/7: Configuring MCP for all IDEs"

# Normalize path for JSON (forward slashes)
$VENV_PYTHON_JSON = $VENV_PYTHON.Replace("\", "/")

$mcpConfigs = @(
    ".roo/mcp.json",
    ".cursor/mcp.json",
    ".windsurf/mcp.json",
    ".mcp.json"
)

foreach ($configRelPath in $mcpConfigs) {
    $configPath = Join-Path $INSTALL_DIR $configRelPath
    if (Test-Path $configPath) {
        $content = Get-Content $configPath -Raw
        $content = $content.Replace("REPLACE_WITH_YOUR_VENV_PYTHON_PATH", $VENV_PYTHON_JSON)
        Set-Content $configPath $content -NoNewline
        Write-Ok "$configRelPath updated"
    }
}

# -- Step 5.5: Install repomix --
Write-Step "Step 5.5/7: Installing repomix (codebase map tool)"

$repomixInstalled = $false
if (Get-Command npx -ErrorAction SilentlyContinue) {
    Write-Ok "npx found - repomix will run on-demand via 'npx repomix' (no pre-download)"
    $repomixInstalled = $true
}

if (-not $repomixInstalled) {
    try {
        & $VENV_PIP install --quiet repomix 2>&1 | Out-Null
        Write-Ok "repomix installed via pip"
        $repomixInstalled = $true
    } catch {
        Write-Warn "repomix not installed. Project-bootstrap will skip the global map step."
        Write-Info "  To install manually: npm install -g repomix  OR  pip install repomix"
    }
}

# -- Step 6: Verify MCP server --
Write-Step "Step 6/7: Verifying MCP server"

$mcpServerDir = Join-Path $INSTALL_DIR ".ai-operation\mcp_server"
$verifyResult = & $VENV_PYTHON -c @"
import sys
sys.path.insert(0, r'$mcpServerDir')
from tools.architect import register_architect_tools
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test')
register_architect_tools(mcp)
print('OK')
"@ 2>&1

if ($verifyResult -match "OK") {
    Write-Ok "MCP server imports verified successfully"
} else {
    Write-Warn "MCP server import check failed"
    Write-Info "  Try: $VENV_PYTHON .ai-operation\mcp_server\server.py"
}

# -- Step 7: Summary --
Write-Step "Step 7/7: IDE rule files check"

$ruleFiles = @(".clinerules", "CLAUDE.md", ".cursorrules", ".windsurfrules")
foreach ($rf in $ruleFiles) {
    $rfPath = Join-Path $INSTALL_DIR $rf
    if (Test-Path $rfPath) {
        Write-Ok "$rf present"
    } else {
        Write-Warn "$rf missing"
    }
}

# -- Done --
Write-Host ""
Write-Host "+==================================================+" -ForegroundColor Green
Write-Host "|   Setup complete!                                 |" -ForegroundColor Green
Write-Host "+==================================================+" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Open this project in your IDE (Roo Code / Cursor / Windsurf / Claude Code)"
Write-Host "  2. Reload MCP servers:"
Write-Host "     Roo Code  : Ctrl+Shift+P -> 'Roo Code: Refresh MCP Servers'" -ForegroundColor Yellow
Write-Host "     Cursor    : Restart the IDE" -ForegroundColor Yellow
Write-Host "     Claude Code: claude mcp list (auto-detects .mcp.json)" -ForegroundColor Yellow
Write-Host "  3. In your first chat with the AI, type:"
Write-Host "     [初始化项目]" -ForegroundColor Cyan
Write-Host ""
Write-Host "  MCP server path: $VENV_PYTHON .ai-operation\mcp_server\server.py"
Write-Host "  Configs: .roo/mcp.json, .cursor/mcp.json, .windsurf/mcp.json, .mcp.json"
Write-Host ""
