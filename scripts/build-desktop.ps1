# FigureSmith — build desktop app (Phase 4 Tauri shell)
#
# Prerequisites:
# - Rust (rustup) + cargo
# - Node.js 20+ / npm
# - WebView2 (Windows)
# - Python backend deps via ./scripts/setup-dev.ps1
#
# Does NOT package model weights.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== FigureSmith build-desktop (Phase 4) ===" -ForegroundColor Cyan

$Node = Get-Command node -ErrorAction SilentlyContinue
$Npm = Get-Command npm -ErrorAction SilentlyContinue
$Cargo = Get-Command cargo -ErrorAction SilentlyContinue
if (-not $Node -or -not $Npm) {
    Write-Error "Node.js / npm required. See apps/desktop/README.md"
}
if (-not $Cargo) {
    Write-Error "cargo required. Install Rust from https://rustup.rs"
}

$Desktop = Join-Path $RepoRoot "apps\desktop"
Set-Location $Desktop

if (-not (Test-Path (Join-Path $Desktop "node_modules"))) {
    Write-Host "npm install ..."
    npm install
}

Write-Host "Building Tauri release bundle (no model weights) ..."
$env:FIGURESMITH_REPO_ROOT = $RepoRoot
npm run tauri -- build

Write-Host ""
Write-Host "Build finished. Artifacts are under apps/desktop/src-tauri/target/release/ and bundle/." -ForegroundColor Green
Write-Host "Runtime pack / installer polish is Phase 6."
