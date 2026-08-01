# FigureSmith — run local backend (Phase 2)
# Binds to 127.0.0.1 only by default. Health: /healthz
# Defaults FIGURESMITH_STRICT_OFFLINE=1 for local/desktop launches.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$HostAddr = if ($env:FIGURESMITH_HOST) { $env:FIGURESMITH_HOST } else { "127.0.0.1" }
$Port = if ($env:FIGURESMITH_PORT) { $env:FIGURESMITH_PORT } else { "8765" }

# Prefer an explicit interpreter, then inspect multiple user-managed Python
# installations. The probe only checks bootstrap packages; model packages are
# reported by the welcome page and can be installed later.
$Probe = @'
import importlib.util, json, platform, sys
items = [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("pydantic", "pydantic"), ("python-multipart", "multipart")]
missing = []
for distribution, import_name in items:
    try:
        present = importlib.util.find_spec(import_name) is not None
    except Exception:
        present = False
    if not present:
        missing.append(distribution)
print(json.dumps({"executable": sys.executable, "major": sys.version_info.major, "minor": sys.version_info.minor, "missing": missing}))
'@

$Candidates = @()
if ($env:FIGURESMITH_PYTHON -and $env:FIGURESMITH_PYTHON.Trim()) {
    $Candidates += [pscustomobject]@{ Command = $env:FIGURESMITH_PYTHON.Trim(); Args = @(); Label = "FIGURESMITH_PYTHON" }
} else {
    $VenvCandidates = @(
        (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
        (Join-Path $RepoRoot ".venv\bin\python"),
        (Join-Path $RepoRoot "apps\backend\.venv\Scripts\python.exe"),
        (Join-Path $RepoRoot "apps\backend\.venv\bin\python")
    )
    foreach ($path in $VenvCandidates) {
        if (Test-Path $path -PathType Leaf) {
            $Candidates += [pscustomobject]@{ Command = $path; Args = @(); Label = $path }
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Candidates += [pscustomobject]@{ Command = "py"; Args = @("-3.12"); Label = "Windows Python launcher (3.12)" }
    }
    foreach ($name in @("python", "python3", "python3.12")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $Candidates += [pscustomobject]@{ Command = $name; Args = @(); Label = $name }
        }
    }
}

$Python = $null
$Diagnostics = @()
foreach ($candidate in $Candidates) {
    try {
        $probeArgs = @($candidate.Args) + @("-c", $Probe)
        $probeOutput = (& $candidate.Command @probeArgs 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($probeOutput)) {
            $Diagnostics += "$($candidate.Label): probe failed"
            continue
        }
        $info = $probeOutput | ConvertFrom-Json
        if ([int]$info.major -ne 3 -or [int]$info.minor -lt 10 -or [int]$info.minor -ge 13) {
            $Diagnostics += "$($candidate.Label): Python $($info.major).$($info.minor) is outside 3.10-3.12"
            continue
        }
        $missing = @($info.missing)
        if ($missing.Count -gt 0) {
            $Diagnostics += "$($candidate.Label): missing $($missing -join ', ')"
            continue
        }
        $Python = [string]$info.executable
        break
    } catch {
        $Diagnostics += "$($candidate.Label): $($_.Exception.Message)"
    }
}
if (-not $Python) {
    $hint = Join-Path $RepoRoot "scripts\runtime\requirements-runtime.txt"
    throw "No usable Python 3.10-3.12 environment found. Install bootstrap packages with '<python> -m pip install -r `"$hint`"' or set FIGURESMITH_PYTHON. Tried: $($Diagnostics -join '; ')"
}

$Backend = Join-Path $RepoRoot "apps\backend"
$Vendor = Join-Path $RepoRoot "vendor\autofigure_edit"

# PYTHONPATH: figuresmith package + flat vendor modules (server.py)
$env:PYTHONPATH = "$Backend;$Vendor"
if ($env:PYTHONPATH_EXTRA) {
    $env:PYTHONPATH = "$env:PYTHONPATH;$env:PYTHONPATH_EXTRA"
}

# Phase 2: strict offline by default for FigureSmith launcher
if (-not $env:FIGURESMITH_STRICT_OFFLINE) {
    $env:FIGURESMITH_STRICT_OFFLINE = "1"
}
if (-not $env:FIGURESMITH_FORCE_LOCAL_SAM) {
    $env:FIGURESMITH_FORCE_LOCAL_SAM = "1"
}
# This script is the explicit source-development entrypoint. Release/runtime
# launchers pass FIGURESMITH_INSTALL_ROOT instead and leave dev mode disabled.
if (-not $env:FIGURESMITH_DEV_MODE) {
    $env:FIGURESMITH_DEV_MODE = "1"
}
if ($env:FIGURESMITH_STRICT_OFFLINE -eq "1") {
    $env:HF_HUB_OFFLINE = "1"
    $env:TRANSFORMERS_OFFLINE = "1"
    $env:HF_DATASETS_OFFLINE = "1"
    if (-not $env:NO_PROXY) {
        $env:NO_PROXY = "127.0.0.1,localhost,::1"
    }
}

Write-Host "=== FigureSmith backend (Phase 2) ===" -ForegroundColor Cyan
Write-Host "Python     : $Python"
Write-Host "Bind       : http://${HostAddr}:${Port}/  (loopback recommended)"
Write-Host "Health     : http://${HostAddr}:${Port}/healthz"
Write-Host "Strict off.: $env:FIGURESMITH_STRICT_OFFLINE"
Write-Host "SAM ckpt   : $env:FIGURESMITH_SAM3_CHECKPOINT"
Write-Host "RMBG path  : $env:FIGURESMITH_RMBG_MODEL_PATH"
Write-Host "PYTHONPATH : $env:PYTHONPATH"
Write-Host "Entry      : apps/backend/main.py (imports vendor server:app)"
Write-Host ""

if ($HostAddr -ne "127.0.0.1" -and $HostAddr -ne "localhost") {
    Write-Host "WARNING: Host is not 127.0.0.1. Desktop policy is loopback-only." -ForegroundColor Red
}

& $Python (Join-Path $Backend "main.py") --host $HostAddr --port $Port
