# FigureSmith — run local backend (Phase 1)
# Binds to 127.0.0.1 only by default. Health: /healthz

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

Write-Host "=== FigureSmith backend ===" -ForegroundColor Cyan
Write-Host "Python     : $Python"
Write-Host "Bind       : http://${HostAddr}:${Port}/  (loopback recommended)"
Write-Host "Health     : http://${HostAddr}:${Port}/healthz"
Write-Host "PYTHONPATH : $env:PYTHONPATH"
Write-Host "Entry      : apps/backend/main.py (imports vendor server:app)"
Write-Host ""

if ($HostAddr -ne "127.0.0.1" -and $HostAddr -ne "localhost") {
    Write-Host "WARNING: Host is not 127.0.0.1. Desktop policy is loopback-only." -ForegroundColor Red
}

& $Python (Join-Path $Backend "main.py") --host $HostAddr --port $Port
