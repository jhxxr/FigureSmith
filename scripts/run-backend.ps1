# FigureSmith — run local backend (Phase 2)
# Binds to 127.0.0.1 only by default. Health: /healthz
# Defaults FIGURESMITH_STRICT_OFFLINE=1 for local/desktop launches.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$HostAddr = if ($env:FIGURESMITH_HOST) { $env:FIGURESMITH_HOST } else { "127.0.0.1" }
$Port = if ($env:FIGURESMITH_PORT) { $env:FIGURESMITH_PORT } else { "8765" }

# Prefer project venv if present
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = Join-Path $RepoRoot ".venv\bin\python"
}
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
    Write-Host "Warning: .venv not found; using system python. Run ./scripts/setup-dev.ps1 first." -ForegroundColor Yellow
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
