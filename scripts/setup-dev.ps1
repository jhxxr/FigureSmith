# FigureSmith — Windows development environment setup (Phase 1)
# Creates .venv at repo root and installs backend requirements.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== FigureSmith setup-dev ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Error "Python not found on PATH. Install Python 3.10+ (3.12 preferred) and retry."
}

$PyVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $PyVersion"

$VenvPath = Join-Path $RepoRoot ".venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment at .venv ..."
    & python -m venv $VenvPath
} else {
    Write-Host "Using existing .venv"
}

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    # Git Bash / non-Windows layout fallback
    $VenvPython = Join-Path $VenvPath "bin/python"
}
if (-not (Test-Path $VenvPython)) {
    Write-Error "Could not find venv Python interpreter under .venv"
}

Write-Host "Upgrading pip ..."
& $VenvPython -m pip install --upgrade pip

$Req = Join-Path $RepoRoot "apps\backend\requirements.txt"
Write-Host "Installing backend requirements from $Req ..."
Write-Host "Note: torch/CUDA wheels vary by machine; this may take a while."
& $VenvPython -m pip install -r $Req

Write-Host ""
Write-Host "SAM3 is NOT installed by this script (separate optional install)." -ForegroundColor Yellow
Write-Host "  git clone https://github.com/facebookresearch/sam3.git"
Write-Host "  cd sam3; pip install -e ."
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. Copy .env.example to .env and fill OpenAI-compatible keys if needed"
Write-Host "  2. Run:  ./scripts/run-backend.ps1"
Write-Host "  3. Open: http://127.0.0.1:8765/healthz"
Write-Host ""
Write-Host "Model weights are not downloaded by setup-dev (by design)."
