# FigureSmith — build desktop app (Phase 6 packaging)
#
# Outputs (under dist-desktop/):
#   FigureSmith-Setup-x64-<ver>.*     (from Tauri bundle when present)
#   FigureSmith-Portable-x64-<ver>.zip
#   checksums.txt
#
# Never packages model weights.

param(
    [switch]$SkipBuild,
    [string]$Version = "",
    [string]$RuntimeRoot = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($Version)) {
    $verFile = Join-Path $RepoRoot "VERSION"
    if (Test-Path $verFile) {
        $Version = (Get-Content $verFile -Raw).Trim()
    } else {
        $Version = "0.0.0-dev"
    }
}

$distDesktop = Join-Path $RepoRoot "dist-desktop"
if (-not (Test-Path $distDesktop)) {
    New-Item -ItemType Directory -Path $distDesktop | Out-Null
}

Write-Host "=== FigureSmith build-desktop (Phase 6) ===" -ForegroundColor Cyan
Write-Host "Version: $Version"

$Desktop = Join-Path $RepoRoot "apps\desktop"
$TauriTarget = Join-Path $Desktop "src-tauri\target\release"
$BundleDir = Join-Path $TauriTarget "bundle"
$RuntimeRoot = if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    Join-Path $Desktop "src-tauri\runtime"
} else {
    (Resolve-Path $RuntimeRoot).Path
}

function Assert-ApplicationRuntime([string]$Root) {
    if (-not (Test-Path $Root -PathType Container)) {
        throw "Application runtime directory is missing: $Root"
    }
    $manifestPath = Join-Path $Root "runtime-manifest.json"
    if (-not (Test-Path $manifestPath -PathType Leaf)) {
        throw "Application runtime manifest is missing: $manifestPath"
    }
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.product -ne "FigureSmith" -or $manifest.application_only -ne $true) {
        throw "Desktop packaging requires application_only=true for FigureSmith"
    }
    if ($manifest.python_required -ne "external" -or $manifest.runtime_complete -ne $false) {
        throw "Desktop packaging must declare user-managed Python"
    }
    foreach ($relative in @(
        "app\backend\main.py",
        "app\vendor\autofigure_edit\server.py",
        "app\backend\figuresmith\runtime\dependencies.json",
        "requirements-runtime.txt",
        "requirements-bootstrap.txt",
        "requirements-models.txt"
    )) {
        $path = Join-Path $Root $relative
        if (-not (Test-Path $path -PathType Leaf)) { throw "Application runtime file is missing: $path" }
    }
    $embedded = Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object {
        $_.Name -ieq "python.exe" -or $_.Name -like "python*.dll" -or $_.Extension -ieq ".whl"
    }
    if ($embedded) { throw "Application runtime contains Python or dependency artifacts: $($embedded.FullName -join ', ')" }
}
Write-Host "Using application pack with user-managed Python: $RuntimeRoot" -ForegroundColor DarkGreen
$TauriSourceRuntime = Join-Path $Desktop "src-tauri\runtime"
if ((Resolve-Path $RuntimeRoot).Path -ne ([System.IO.Path]::GetFullPath($TauriSourceRuntime))) {
    if (Test-Path $TauriSourceRuntime) { Remove-Item $TauriSourceRuntime -Recurse -Force }
    Copy-Item $RuntimeRoot $TauriSourceRuntime -Recurse -Force
}

if (-not $SkipBuild) {
    $Node = Get-Command node -ErrorAction SilentlyContinue
    $Npm = Get-Command npm -ErrorAction SilentlyContinue
    $Cargo = Get-Command cargo -ErrorAction SilentlyContinue
    if (-not $Node -or -not $Npm) {
        Write-Error "Node.js / npm required. See apps/desktop/README.md (or re-run with -SkipBuild)"
    }
    if (-not $Cargo) {
        Write-Error "cargo required. Install Rust from https://rustup.rs (or re-run with -SkipBuild)"
    }

    Set-Location $Desktop
    if (-not (Test-Path (Join-Path $Desktop "node_modules"))) {
        Write-Host "npm install ..."
        npm install
    }

    # Align tauri version string if jq/python available — best-effort via file already set
    Write-Host "Building Tauri release bundle (no model weights) ..."
    $env:FIGURESMITH_REPO_ROOT = $RepoRoot
    npm run tauri -- build
    Set-Location $RepoRoot
} else {
    Write-Host "SkipBuild: reusing existing Tauri target if present" -ForegroundColor Yellow
}

# Tauri copies bundle.resources into target/release/resources. Keep this check
# fail-closed: an installer without the application pack would only fail after launch.
$TauriResources = Join-Path $TauriTarget "resources"
$TauriRuntime = Join-Path $TauriResources "runtime"
if (Test-Path $TauriRuntime) { Remove-Item $TauriRuntime -Recurse -Force }
New-Item -ItemType Directory -Path $TauriResources -Force | Out-Null
Copy-Item $RuntimeRoot $TauriRuntime -Recurse -Force
Assert-ApplicationRuntime $TauriRuntime

# Collect bundle artifacts
$copied = @()
if (Test-Path $BundleDir) {
    Get-ChildItem -Path $BundleDir -Recurse -File | ForEach-Object {
        $ext = $_.Extension.ToLowerInvariant()
        if ($ext -in @(".exe", ".msi", ".nsis.zip", ".zip")) {
            # skip obvious non-installer huge pdbs
        }
        if ($ext -in @(".exe", ".msi") -or $_.Name -like "*.nsis.zip" -or ($ext -eq ".zip" -and $_.FullName -match "bundle")) {
            $destName = $_.Name
            if ($ext -eq ".exe" -and $_.Name -notlike "FigureSmith-Setup*") {
                $destName = "FigureSmith-Setup-x64-$Version.exe"
            }
            if ($ext -eq ".msi") {
                $destName = "FigureSmith-Setup-x64-$Version.msi"
            }
            $dest = Join-Path $distDesktop $destName
            Copy-Item $_.FullName $dest -Force
            $copied += $dest
            Write-Host "Copied installer-like artifact: $dest"
        }
    }
} else {
    Write-Warning "No Tauri bundle dir at $BundleDir — portable pack will still be assembled from sources/scripts."
}

# Portable zip must contain the actual Tauri executable. A source/script-only
# directory is not a publishable desktop artifact.
$portableName = "FigureSmith-Portable-x64-$Version"
$portableDir = Join-Path $distDesktop $portableName
# Prefer release exe if present
$releaseExe = Join-Path $TauriTarget "FigureSmith.exe"
if (-not (Test-Path $releaseExe)) {
    $cand = Get-ChildItem -Path $TauriTarget -Filter "*.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^(FigureSmith|figuresmith-desktop)\.exe$" } |
        Select-Object -First 1
    if ($cand) { $releaseExe = $cand.FullName }
}
if (-not (Test-Path $releaseExe -PathType Leaf)) {
    $portableZip = Join-Path $distDesktop "$portableName.zip"
    if (Test-Path $portableDir) { Remove-Item -Recurse -Force $portableDir }
    if (Test-Path $portableZip) { Remove-Item -Force $portableZip }
    throw "No FigureSmith release executable found under $TauriTarget; refusing to create a placeholder Portable artifact."
}

if (Test-Path $portableDir) { Remove-Item -Recurse -Force $portableDir }
New-Item -ItemType Directory -Path $portableDir | Out-Null

foreach ($f in @("LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "README.md", "README_ZH.md", "VERSION", "CHANGELOG.md")) {
    $src = Join-Path $RepoRoot $f
    if (Test-Path $src) { Copy-Item $src (Join-Path $portableDir $f) -Force }
}

Copy-Item $releaseExe (Join-Path $portableDir "FigureSmith.exe") -Force
Write-Host "Included FigureSmith.exe in portable pack"

# The packaged Tauri resource directory contains application code and the
# dependency contract. The executable creates/uses a separate user environment
# from a supported base Python; it never writes packages into that base.
Copy-Item $TauriResources (Join-Path $portableDir "resources") -Recurse -Force
Assert-ApplicationRuntime (Join-Path $portableDir "resources\runtime")

@"
# FigureSmith Portable

- Product: FigureSmith / 图匠
- Version: $Version
- The target machine supplies a supported Python 3.10-3.12 base. FigureSmith creates its isolated environment under `%LOCALAPPDATA%\FigureSmith\python-env` and installs bootstrap packages there without modifying the base Python.
- Model packages remain optional; the welcome page reports their status and provides a command for the isolated environment.
- Import SAM3/RMBG model weights in the app.
- Backend must bind 127.0.0.1 only (desktop sidecar enforces this).

See docs in the full repository: docs/phase6-delivery.md, docs/release.md
"@ | Set-Content (Join-Path $portableDir "README-PORTABLE.md") -Encoding utf8

$portableZip = Join-Path $distDesktop "$portableName.zip"
if (Test-Path $portableZip) { Remove-Item $portableZip -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($portableDir, $portableZip)
Write-Host "Portable zip: $portableZip" -ForegroundColor Green

# Refuse weight contamination in dist-desktop tree
$bad = Get-ChildItem -Path $distDesktop -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension.ToLowerInvariant() -in @(".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin")
}
if ($bad) {
    Write-Error "Weight-like files in dist-desktop:`n$($bad.FullName -join "`n")"
}

& (Join-Path $PSScriptRoot "write-checksums.ps1") -Path $distDesktop -OutFile (Join-Path $distDesktop "checksums.txt")

Write-Host "Desktop packaging done -> $distDesktop" -ForegroundColor Green
