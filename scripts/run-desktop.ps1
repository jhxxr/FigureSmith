# FigureSmith — run desktop app (Phase 4 Tauri shell)
# Spawns Tauri which starts the Python sidecar on 127.0.0.1 with a session token.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== FigureSmith desktop (Phase 4) ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# Toolchain checks
$Node = Get-Command node -ErrorAction SilentlyContinue
$Npm = Get-Command npm -ErrorAction SilentlyContinue
$Cargo = Get-Command cargo -ErrorAction SilentlyContinue
$Rustc = Get-Command rustc -ErrorAction SilentlyContinue

if (-not $Node -or -not $Npm) {
    Write-Error "Node.js / npm not found. Install Node 20+ and retry. See apps/desktop/README.md"
}
if (-not $Cargo -or -not $Rustc) {
    Write-Error "Rust toolchain (cargo/rustc) not found. Install from https://rustup.rs and retry."
}

# The desktop shell creates/uses a dedicated per-user Python environment.
# FIGURESMITH_PYTHON remains available as an explicit base-Python override,
# but the sidecar itself always runs from the isolated FigureSmith environment.
Remove-Item Env:FIGURESMITH_PYTHON -ErrorAction SilentlyContinue
Write-Host "The desktop sidecar will create/use the isolated FigureSmith environment under LocalAppData." -ForegroundColor DarkGreen

$env:FIGURESMITH_REPO_ROOT = $RepoRoot
$env:FIGURESMITH_STRICT_OFFLINE = "1"
# Desktop always uses token auth from the shell; do not export DISABLE_AUTH.
Remove-Item Env:FIGURESMITH_DISABLE_AUTH -ErrorAction SilentlyContinue

$Desktop = Join-Path $RepoRoot "apps\desktop"
if (-not (Test-Path (Join-Path $Desktop "package.json"))) {
    Write-Error "apps/desktop/package.json missing — Phase 4 scaffold incomplete."
}

Set-Location $Desktop

if (-not (Test-Path (Join-Path $Desktop "node_modules"))) {
    Write-Host "Installing npm dependencies in apps/desktop ..."
    npm install
}

Write-Host "Launching: npm run tauri -- dev"
Write-Host "Sidecar binds 127.0.0.1 only; token stays in memory/env."
Write-Host "Quit the app window to stop the Python process."
Write-Host ""

npm run tauri -- dev
