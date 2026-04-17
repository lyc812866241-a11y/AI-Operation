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
    [switch]$Update,   # Update mode: only overwrite framework code, preserve local products
    [switch]$Migrate,  # Migrate mode: update + migrate old project data (paths, rules, corrections)
    [switch]$Check     # Check mode: verify installation health, no modifications
)

# Migrate implies Update
if ($Migrate) { $Update = $true }

$ErrorActionPreference = "Stop"

# -- Colors --
function Write-Step($msg)  { Write-Host "`n>> $msg" -ForegroundColor Blue }
function Write-Ok($msg)    { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Info($msg)  { Write-Host "  $msg" }

# -- Banner --
Write-Host ""
if ($Check) {
    Write-Host "+==================================================+" -ForegroundColor Cyan
    Write-Host "|     Vibe Coding Agent Framework - CHECK           |" -ForegroundColor Cyan
    Write-Host "+==================================================+" -ForegroundColor Cyan
} elseif ($Update) {
    Write-Host "+==================================================+" -ForegroundColor Cyan
    Write-Host "|     Vibe Coding Agent Framework - UPDATE          |" -ForegroundColor Cyan
    Write-Host "+==================================================+" -ForegroundColor Cyan
} else {
    Write-Host "+==================================================+" -ForegroundColor White
    Write-Host "|     Vibe Coding Agent Framework - Setup           |" -ForegroundColor White
    Write-Host "+==================================================+" -ForegroundColor White
}
Write-Host ""

# ── CHECK MODE ─────────────────────────────────────────────────────────────
if ($Check) {
    $pass = 0; $fail = 0; $warn = 0
    function Check-Pass($msg) { $script:pass++; Write-Ok $msg }
    function Check-Fail($msg) { $script:fail++; Write-Err $msg }
    function Check-Warn($msg) { $script:warn++; Write-Warn $msg }

    # 1. Framework structure
    Write-Step "1. Framework structure"
    if (Test-Path ".ai-operation") { Check-Pass ".ai-operation/ exists" } else { Check-Fail ".ai-operation/ missing" }
    if (Test-Path ".ai-operation\mcp_server") { Check-Pass "MCP server code" } else { Check-Fail "MCP server missing" }
    if (Test-Path ".ai-operation\skills") { Check-Pass "Skills directory" } else { Check-Fail "Skills missing" }

    # 2. Python & venv
    Write-Step "2. Python & venv"
    $venvPy = Join-Path (Get-Location) ".ai-operation\venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
        Check-Pass "venv Python found"
        $depCheck = & $venvPy -c "import mcp; import fastmcp; print('OK')" 2>&1
        if ($depCheck -match "OK") { Check-Pass "MCP dependencies installed" }
        else { Check-Fail "MCP dependencies missing" }
    } else {
        Check-Fail "venv not found"
        $venvPy = $null
    }

    # 3. MCP tools
    Write-Step "3. MCP tools"
    if ($venvPy) {
        $mcpDir = Join-Path (Get-Location) ".ai-operation\mcp_server"
        $mcpResult = & $venvPy -c @"
import sys
sys.path.insert(0, r'$mcpDir')
from tools.architect import register_architect_tools
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test')
register_architect_tools(mcp)
try:
    n = len(mcp._tool_manager._tools)
except:
    n = -1
print(f'OK:{n}')
"@ 2>&1
        if ("$mcpResult" -match 'OK:(\d+)') {
            Check-Pass "MCP server OK - $($Matches[1]) tools registered"
        } else {
            Check-Fail "MCP server failed to load: $mcpResult"
        }
    }

    # 4. IDE configs
    Write-Step "4. IDE configs"
    if (Test-Path ".mcp.json") { Check-Pass ".mcp.json" } else { Check-Fail ".mcp.json missing" }
    if (Test-Path ".clinerules") { Check-Pass ".clinerules" } else { Check-Warn ".clinerules missing" }
    if (Test-Path "CLAUDE.md") { Check-Pass "CLAUDE.md" } else { Check-Warn "CLAUDE.md missing" }
    if (Test-Path ".mcp.json") {
        if ((Get-Content ".mcp.json" -Raw) -match "REPLACE_WITH_YOUR_VENV_PYTHON_PATH") {
            Check-Fail ".mcp.json has unresolved Python path placeholder"
        } else {
            Check-Pass ".mcp.json Python path configured"
        }
    }

    # 5. Claude Code hooks
    Write-Step "5. Claude Code hooks"
    if (Test-Path ".claude\hooks") { Check-Pass ".claude\hooks\ exists" } else { Check-Warn ".claude\hooks\ missing" }
    if (Test-Path ".claude\hooks\require-context.sh") { Check-Pass "Cognitive gate hook" } else { Check-Warn "Cognitive gate hook missing" }
    if (Test-Path ".claude\settings.json") { Check-Pass "Claude settings.json" } else { Check-Warn "Claude settings.json missing" }

    # 6. Project map
    Write-Step "6. Project map"
    $pmDir = ".ai-operation\docs\project_map"
    if (Test-Path $pmDir) { Check-Pass "project_map\ exists" } else { Check-Fail "project_map\ missing" }
    $pmFiles = 0; $pmFilled = 0
    foreach ($f in @("projectbrief","systemPatterns","techContext","conventions","activeContext","progress","corrections","inventory")) {
        $pf = Join-Path $pmDir "$f.md"
        if (Test-Path $pf) {
            $pmFiles++
            $content = Get-Content $pf -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
            $placeholders = ([regex]::Matches($content, 'TODO')).Count
            if ($placeholders -lt 3) { $pmFilled++ }
        }
    }
    if ($pmFiles -eq 8) { Check-Pass "All 8 project_map files present" }
    else { Check-Fail "Only $pmFiles/8 project_map files found" }
    if ($pmFilled -ge 5) { Check-Pass "$pmFilled/8 files have content" }
    else { Check-Warn "Only $pmFilled/8 files filled - run [初始化项目]" }

    # 7. Git integration -- auto-fix .gitignore blocking project_map
    Write-Step "7. Git integration"
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCmd) {
        Check-Warn "git not installed - skipping .gitignore audit"
    } else {
        $gitDirProbe = & git rev-parse --git-dir 2>$null
        if (-not $gitDirProbe) {
            Check-Warn "not a git repo - skipping .gitignore audit"
        } elseif (-not (Test-Path ".gitignore")) {
            Check-Pass "no .gitignore (nothing can block project_map)"
        } elseif (-not (Test-Path $pmDir)) {
            Check-Warn "project_map missing - cannot probe ignore state"
        } else {
            $probeFile = $null
            foreach ($cand in @("activeContext.md", "projectbrief.md")) {
                $pf = Join-Path $pmDir $cand
                if (Test-Path $pf) { $probeFile = $pf; break }
            }
            if (-not $probeFile) {
                Check-Warn "no project_map file to probe ignore rules"
            } else {
                $ignoreOut = & git check-ignore -v $probeFile 2>$null
                if (-not $ignoreOut) {
                    Check-Pass ".gitignore does not block project_map"
                } else {
                    $first = ($ignoreOut -split "`n")[0]
                    $left = $first -split "`t", 2 | Select-Object -First 1
                    $srcParts = $left -split ":", 3
                    $pattern = if ($srcParts.Count -ge 3) { $srcParts[2].Trim() } else { "" }
                    if (-not $pattern) {
                        Check-Warn "could not parse check-ignore output: $first"
                    } elseif ($pattern -match "project_map") {
                        # Precise - delete the line
                        $key = $pattern.TrimEnd('/')
                        $lines = Get-Content ".gitignore" -Encoding UTF8
                        $kept = @()
                        $removed = 0
                        foreach ($l in $lines) {
                            $s = $l.Trim()
                            if ($s -and -not $s.StartsWith("#") -and $s.TrimEnd('/') -eq $key) {
                                $removed++
                                continue
                            }
                            $kept += $l
                        }
                        ($kept -join "`n") + "`n" | Set-Content ".gitignore" -Encoding UTF8 -NoNewline
                        Check-Pass "Auto-fixed: removed '$pattern' from .gitignore (was blocking project_map)"
                    } else {
                        # Broad rule - append whitelist
                        $wl = "!.ai-operation/docs/project_map/"
                        $wlGlob = "!.ai-operation/docs/project_map/**"
                        $giContent = Get-Content ".gitignore" -Encoding UTF8
                        $hasWl = $giContent | Where-Object { $_.Trim() -eq $wl -or $_.Trim() -eq $wlGlob }
                        if ($hasWl) {
                            Check-Warn "broad rule '$pattern' blocks project_map but whitelist already present (may need manual review)"
                        } else {
                            Add-Content ".gitignore" -Value $wl -Encoding UTF8
                            Check-Pass "Auto-fixed: appended whitelist '$wl' (broad rule '$pattern' preserved)"
                        }
                    }
                }
            }
        }
    }

    # Summary
    Write-Host ""
    if ($fail -eq 0) {
        Write-Host "+==================================================+" -ForegroundColor Green
        Write-Host "|   All checks passed!  ($pass pass, $warn warn)            |" -ForegroundColor Green
        Write-Host "+==================================================+" -ForegroundColor Green
    } else {
        Write-Host "+==================================================+" -ForegroundColor Red
        Write-Host "|   Issues found: $fail fail, $warn warn, $pass pass            |" -ForegroundColor Red
        Write-Host "+==================================================+" -ForegroundColor Red
        Write-Host ""
        Write-Host "  Run: .\setup.ps1 -Update    to fix framework issues" -ForegroundColor Yellow
        Write-Host "  Run: .\setup.ps1 -Migrate   if upgrading from older version" -ForegroundColor Yellow
    }
    Write-Host ""
    exit $fail
}

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

    $TMP_DIR = Join-Path $env:TEMP "ai-operation-update-$(Get-Random)"
    try {
        # Try git clone first, fall back to curl/Invoke-WebRequest if git fails
        $downloadOk = $false
        if (Get-Command git -ErrorAction SilentlyContinue) {
            Write-Info "Trying git clone..."
            try {
                git clone --depth=1 --quiet $REPO_URL $TMP_DIR 2>&1 | Out-Null
                if (Test-Path (Join-Path $TMP_DIR ".ai-operation")) {
                    $downloadOk = $true
                    Write-Ok "Downloaded via git"
                }
            } catch {}
            if (-not $downloadOk -and (Test-Path $TMP_DIR)) {
                Remove-Item $TMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        if (-not $downloadOk) {
            Write-Warn "git clone failed, trying web download..."
            New-Item -ItemType Directory -Path $TMP_DIR -Force | Out-Null
            $zipUrl = "https://github.com/lyc812866241-a11y/AI-Operation/archive/refs/heads/master.zip"
            $zipFile = Join-Path $TMP_DIR "aio.zip"
            try {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
                Expand-Archive -Path $zipFile -DestinationPath $TMP_DIR -Force
                # GitHub ZIP extracts to AI-Operation-master/
                $extracted = Join-Path $TMP_DIR "AI-Operation-master"
                if (Test-Path $extracted) {
                    Get-ChildItem $extracted | Move-Item -Destination $TMP_DIR -Force
                    Remove-Item $extracted -Recurse -Force
                }
                Remove-Item $zipFile -Force
                $downloadOk = $true
                Write-Ok "Downloaded via web (zip fallback)"
            } catch {
                Write-Err "Both git and web download failed. Check network."
                exit 1
            }
        }

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
        $docFiles = @("template_reference.md")
        foreach ($df in $docFiles) {
            $src = Join-Path $TMP_DIR ".ai-operation\docs\$df"
            $dst = Join-Path $INSTALL_DIR ".ai-operation\docs\$df"
            if (Test-Path $src) {
                Copy-Item $src $dst -Force
                Write-Ok "Updated docs\$df"
            }
        }

        # Update rule files (NOT .mcp.json — handled separately below)
        $ruleFiles = @(".clinerules", "CLAUDE.md", ".cursorrules", ".windsurfrules", ".gitignore")
        foreach ($rf in $ruleFiles) {
            $src = Join-Path $TMP_DIR $rf
            $dst = Join-Path $INSTALL_DIR $rf
            if (Test-Path $src) {
                Copy-Item $src $dst -Force
                Write-Ok "Updated $rf"
            }
        }

        # Smart-merge .mcp.json: LOCAL is base, only merge alwaysAllow from upstream
        $mcpSrc = Join-Path $TMP_DIR ".mcp.json"
        $mcpDst = Join-Path $INSTALL_DIR ".mcp.json"
        if ((Test-Path $mcpSrc) -and (Test-Path $mcpDst)) {
            try {
                $localMcp = Get-Content $mcpDst -Raw -Encoding UTF8 | ConvertFrom-Json
                $upstreamMcp = Get-Content $mcpSrc -Raw -Encoding UTF8 | ConvertFrom-Json
                $pa = $localMcp.mcpServers.project_architect

                # Only fix command if still placeholder
                if (-not $pa.command -or $pa.command -eq "REPLACE_WITH_YOUR_VENV_PYTHON_PATH") {
                    $venvPy = Join-Path $INSTALL_DIR ".ai-operation\venv\Scripts\python.exe"
                    if (Test-Path $venvPy) {
                        $pa.command = $venvPy.Replace("\", "/")
                    }
                }

                # Only fix args if missing or still template default
                $templateArgs = @(".ai-operation/mcp_server/server.py")
                if (-not $pa.args -or ($pa.args.Count -eq 1 -and $pa.args[0] -eq $templateArgs[0])) {
                    $serverAbs = (Join-Path $INSTALL_DIR ".ai-operation\mcp_server\server.py").Replace("\", "/")
                    $pa.args = @("-u", $serverAbs)
                }

                # Merge alwaysAllow: add new tools from upstream, keep existing
                $upstreamAllow = $upstreamMcp.mcpServers.project_architect.alwaysAllow
                $localAllow = [System.Collections.ArrayList]@($pa.alwaysAllow)
                foreach ($tool in $upstreamAllow) {
                    if ($tool -notin $localAllow) {
                        $localAllow.Add($tool) | Out-Null
                    }
                }
                $pa.alwaysAllow = @($localAllow)

                # Write LOCAL back (not upstream)
                $localMcp | ConvertTo-Json -Depth 10 | Set-Content $mcpDst -Encoding UTF8 -NoNewline
                Write-Ok "Smart-merged .mcp.json (local preserved, alwaysAllow updated)"
            } catch {
                Copy-Item $mcpSrc $mcpDst -Force
                Write-Warn ".mcp.json replaced (smart merge failed)"
            }
        }

        # Update setup scripts themselves
        Copy-Item (Join-Path $TMP_DIR "setup.sh") (Join-Path $INSTALL_DIR "setup.sh") -Force
        Copy-Item (Join-Path $TMP_DIR "setup.ps1") (Join-Path $INSTALL_DIR "setup.ps1") -Force
        Write-Ok "Updated setup scripts"

    } finally {
        if (Test-Path $TMP_DIR) { Remove-Item $TMP_DIR -Recurse -Force }
    }

    # Update Claude Code hooks (always overwrite — framework code)
    $CLAUDE_HOOKS_SRC = Join-Path $INSTALL_DIR ".ai-operation\docs\templates\claude"
    $CLAUDE_DIR = Join-Path $INSTALL_DIR ".claude"
    if (Test-Path $CLAUDE_HOOKS_SRC) {
        $hooksDir = Join-Path $CLAUDE_DIR "hooks"
        New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null
        foreach ($hookFile in @("check-dangerous.sh", "require-context.sh", "governance-capture.sh")) {
            $src = Join-Path $CLAUDE_HOOKS_SRC "hooks\$hookFile"
            $dst = Join-Path $hooksDir $hookFile
            if (Test-Path $src) { Copy-Item $src $dst -Force }
        }
        Write-Ok "Updated Claude Code hooks"
        # Create settings.json if missing
        $settingsPath = Join-Path $CLAUDE_DIR "settings.json"
        if (-not (Test-Path $settingsPath)) {
            Copy-Item (Join-Path $CLAUDE_HOOKS_SRC "settings.json") $settingsPath -Force
            Write-Ok "Created Claude Code settings.json"
        }
    }

    # Create .session_confirmed so cognitive gate doesn't lock out the user
    $sessionFlag = Join-Path $INSTALL_DIR ".ai-operation\.session_confirmed"
    if (-not (Test-Path $sessionFlag)) {
        Set-Content $sessionFlag "0" -NoNewline
        Write-Ok "Created session flag (cognitive gate unblocked)"
    }

    # Add SESSION_KEY to corrections.md if missing (required by cognitive gate)
    $corrections = Join-Path $INSTALL_DIR ".ai-operation\docs\project_map\corrections.md"
    if (Test-Path $corrections) {
        $corrContent = Get-Content $corrections -Raw -Encoding UTF8
        if ($corrContent -notmatch "SESSION_KEY:") {
            Add-Content $corrections "`n`nSESSION_KEY: init000" -Encoding UTF8
            Write-Ok "Added SESSION_KEY to corrections.md"
        }
    }

    # Migrate: add new template files to project_map if missing
    $TEMPLATES_DIR = Join-Path $INSTALL_DIR ".ai-operation\docs\templates\project_map"
    $PROJECT_MAP_DIR = Join-Path $INSTALL_DIR ".ai-operation\docs\project_map"
    if ((Test-Path $TEMPLATES_DIR) -and (Test-Path $PROJECT_MAP_DIR)) {
        Get-ChildItem "$TEMPLATES_DIR\*.md" | ForEach-Object {
            $target = Join-Path $PROJECT_MAP_DIR $_.Name
            if (-not (Test-Path $target)) {
                Copy-Item $_.FullName $target -Force
                Write-Ok "Migrated new template: $($_.Name)"
            }
        }
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

    # ── MIGRATE MODE ─────────────────────────────────────────────────────────
    if ($Migrate) {
        Write-Step "Migrate: Project data migration"

        $BACKUP_DIR = Join-Path $INSTALL_DIR ".ai-operation\migrate_backup"
        New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
        $migratedItems = @()

        # ── Step M1: Migrate old docs/project_map/ → .ai-operation/docs/project_map/
        $OLD_PM = Join-Path $INSTALL_DIR "docs\project_map"
        $NEW_PM = Join-Path $INSTALL_DIR ".ai-operation\docs\project_map"

        if (Test-Path $OLD_PM -PathType Container) {
            Write-Info "Found old project_map at docs\project_map\"
            Copy-Item $OLD_PM "$BACKUP_DIR\old_project_map" -Recurse -Force

            Get-ChildItem "$OLD_PM\*.md" | ForEach-Object {
                $fname = $_.Name
                $newFile = Join-Path $NEW_PM $fname

                if (-not (Test-Path $newFile)) {
                    Copy-Item $_.FullName $newFile -Force
                    Write-Ok "Migrated $fname (new)"
                    $migratedItems += $fname
                } elseif ((Get-Content $newFile -Raw -Encoding UTF8) -match '\[TODO') {
                    $placeholders = ([regex]::Matches((Get-Content $newFile -Raw -Encoding UTF8), 'TODO')).Count
                    if ($placeholders -ge 3) {
                        Copy-Item $_.FullName $newFile -Force
                        Write-Ok "Migrated $fname (replaced template)"
                        $migratedItems += $fname
                    } else {
                        Write-Info "Skipped $fname (new path already has content)"
                    }
                } else {
                    Write-Info "Skipped $fname (new path already has content)"
                }
            }

            # Migrate details/
            $oldDetails = Join-Path $OLD_PM "details"
            if (Test-Path $oldDetails) {
                $newDetails = Join-Path $NEW_PM "details"
                New-Item -ItemType Directory -Path $newDetails -Force | Out-Null
                Get-ChildItem "$oldDetails\*.md" | ForEach-Object {
                    $target = Join-Path $newDetails $_.Name
                    if (-not (Test-Path $target)) {
                        Copy-Item $_.FullName $target -Force
                    }
                }
                Write-Ok "Migrated details/ subfiles"
            }

            # Leave pointer
            Set-Content (Join-Path $OLD_PM "README.md") @"
# Migrated
Project map data has been migrated to .ai-operation/docs/project_map/
This directory can be safely deleted.
"@
            Write-Ok "Left migration pointer in old docs\project_map\"
        } else {
            Write-Info "No old docs\project_map\ found — skipping path migration"
        }

        # ── Step M2: Extract custom rules from old CLAUDE.md ───────────────────
        $RULES_D = Join-Path $INSTALL_DIR ".ai-operation\rules.d"
        $CUSTOM_RULES = Join-Path $RULES_D "project_custom.md"

        # Try to recover old CLAUDE.md from git history
        $oldClaudeMd = ""
        if (Get-Command git -ErrorAction SilentlyContinue) {
            try {
                $oldClaudeMd = git show HEAD~1:CLAUDE.md 2>$null
            } catch {}
        }
        if ($oldClaudeMd -and ($oldClaudeMd.Split("`n").Count -gt 70)) {
            $oldClaudeBak = Join-Path $BACKUP_DIR "CLAUDE.md.bak"
            Set-Content $oldClaudeBak $oldClaudeMd -Encoding UTF8
            Write-Info "Recovered old CLAUDE.md from git history ($($oldClaudeMd.Split("`n").Count) lines)"

            # Extract custom sections using Python
            & $VENV_PYTHON -c @"
import sys, re

with open(r'$oldClaudeBak', encoding='utf-8', errors='ignore') as f:
    old_content = f.read()

framework_headers = [
    '开机自检', '源文件索引', '项目记忆', '规范与协议',
    '指令路由', 'AI-Operation', 'auto-generated',
    'Do NOT edit', '.clinerules', 'MCP tools',
]

lines = old_content.split('\n')
custom_sections = []
current_section = []
in_custom = False

for line in lines:
    if line.startswith('## ') or line.startswith('# '):
        if in_custom and current_section:
            custom_sections.append('\n'.join(current_section))
        header_text = line.lstrip('#').strip()
        is_framework = any(fh in header_text or fh in line for fh in framework_headers)
        if is_framework:
            in_custom = False
            current_section = []
        else:
            in_custom = True
            current_section = [line]
    elif in_custom:
        current_section.append(line)

if in_custom and current_section:
    custom_sections.append('\n'.join(current_section))

if custom_sections:
    result = '# 项目自定义规则\n\n'
    result += '> 从旧 CLAUDE.md 迁移。由 setup.ps1 -Migrate 自动提取。\n'
    result += '> 此文件由 [读档] 自动加载到 AI 上下文中。\n\n'
    result += '\n\n---\n\n'.join(custom_sections)
    result += '\n'
    with open(r'$CUSTOM_RULES', 'w', encoding='utf-8') as f:
        f.write(result)
    print(f'EXTRACTED:{len(custom_sections)}')
else:
    print('NO_CUSTOM')
"@ 2>&1

            if (Test-Path $CUSTOM_RULES) {
                Write-Ok "Extracted custom rules -> .ai-operation\rules.d\project_custom.md"
                $migratedItems += "custom_rules"
            } else {
                Write-Info "No custom rules found in old CLAUDE.md"
            }
        } else {
            Write-Info "No old CLAUDE.md to extract rules from"
        }

        # ── Migration Summary ──────────────────────────────────────────────────
        Write-Host ""
        if ($migratedItems.Count -gt 0) {
            Write-Host "+==================================================+" -ForegroundColor Green
            Write-Host "|   Migration complete!                             |" -ForegroundColor Green
            Write-Host "+==================================================+" -ForegroundColor Green
            Write-Host ""
            Write-Host "Migrated:" -ForegroundColor Yellow
            foreach ($item in $migratedItems) {
                Write-Host "    - $item"
            }
            Write-Host ""
            Write-Host "Backup:  .ai-operation\migrate_backup\" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Review checklist:" -ForegroundColor White
            Write-Host "  1. Check .ai-operation\docs\project_map\ — data migrated correctly?"
            if (Test-Path $CUSTOM_RULES) {
                Write-Host "  2. Check .ai-operation\rules.d\project_custom.md — custom rules complete?"
            }
            Write-Host "  3. Run [初始化项目] with Phase 3.5 audit to verify"
            Write-Host "  4. Old docs\project_map\ can be deleted after verification"
        } else {
            Write-Host "+==================================================+" -ForegroundColor Green
            Write-Host "|   Update complete! (nothing to migrate)           |" -ForegroundColor Green
            Write-Host "+==================================================+" -ForegroundColor Green
        }
        Write-Host ""
        Write-Host "Restart your IDE to reload MCP servers." -ForegroundColor White
        Write-Host ""
        exit 0
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

# -- Step 2.5: Initialize project_map from templates --
$PROJECT_MAP_DIR = Join-Path $INSTALL_DIR ".ai-operation\docs\project_map"
$TEMPLATES_DIR = Join-Path $INSTALL_DIR ".ai-operation\docs\templates\project_map"

if (-not (Test-Path $PROJECT_MAP_DIR)) {
    Write-Step "Step 2.5: Initializing project_map from templates"
    New-Item -ItemType Directory -Path $PROJECT_MAP_DIR -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $PROJECT_MAP_DIR "details") -Force | Out-Null
    if (Test-Path $TEMPLATES_DIR) {
        Copy-Item "$TEMPLATES_DIR\*" $PROJECT_MAP_DIR -Force
        Write-Ok "project_map initialized with templates (all [TODO])"
    } else {
        Write-Warn "Templates not found at $TEMPLATES_DIR"
    }
} else {
    Write-Ok "project_map already exists — skipping template copy"
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

# -- Step 5.6: Install oh-my-mermaid (architecture diagram tool) --
Write-Step "Step 5.6/7: Installing oh-my-mermaid (architecture diagrams)"

if (Get-Command npm -ErrorAction SilentlyContinue) {
    try {
        $ommCheck = npm list -g oh-my-mermaid 2>$null
        if ($ommCheck -match "oh-my-mermaid") {
            Write-Ok "oh-my-mermaid already installed"
        } else {
            npm install -g oh-my-mermaid 2>&1 | Out-Null
            Write-Ok "oh-my-mermaid installed (omm CLI for [架构扫描])"
        }
    } catch {
        Write-Warn "oh-my-mermaid install failed. [架构扫描] will not work."
        Write-Info "  To install manually: npm install -g oh-my-mermaid"
    }
} else {
    Write-Warn "npm not found — skipping oh-my-mermaid install"
    Write-Info "  Install Node.js, then: npm install -g oh-my-mermaid"
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

# -- Step 7: Install Claude Code hooks --
Write-Step "Step 7/8: Installing Claude Code hooks"

$CLAUDE_HOOKS_SRC = Join-Path $INSTALL_DIR ".ai-operation\docs\templates\claude"
$CLAUDE_DIR = Join-Path $INSTALL_DIR ".claude"

if (Test-Path $CLAUDE_HOOKS_SRC) {
    # Create .claude/hooks/ if it doesn't exist
    $hooksDir = Join-Path $CLAUDE_DIR "hooks"
    New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null

    # Copy hook scripts (always overwrite — framework code)
    foreach ($hookFile in @("check-dangerous.sh", "require-context.sh", "governance-capture.sh")) {
        $src = Join-Path $CLAUDE_HOOKS_SRC "hooks\$hookFile"
        $dst = Join-Path $hooksDir $hookFile
        if (Test-Path $src) {
            Copy-Item $src $dst -Force
        }
    }
    Write-Ok "Claude Code hooks installed (cognitive gate + dangerous guard + audit)"

    # Copy settings.json only if it doesn't exist (preserve user customizations)
    $settingsPath = Join-Path $CLAUDE_DIR "settings.json"
    if (-not (Test-Path $settingsPath)) {
        Copy-Item (Join-Path $CLAUDE_HOOKS_SRC "settings.json") $settingsPath -Force
        Write-Ok "Claude Code settings.json created with hook configuration"
    } else {
        Write-Ok "Claude Code settings.json already exists — preserved"
    }

    # Create initial .session_confirmed so AI can run [初始化项目] on first use
    $sessionFlag = Join-Path $INSTALL_DIR ".ai-operation\.session_confirmed"
    if (-not (Test-Path $sessionFlag)) {
        Set-Content $sessionFlag "0" -NoNewline
        Write-Ok "Initial session confirmed (allows first [初始化项目])"
    }
} else {
    Write-Warn "Claude hooks template not found — skipping"
}

# -- Step 8: Summary --
Write-Step "Step 8/8: IDE rule files check"

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
