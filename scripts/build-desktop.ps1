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

function Assert-RuntimeV1([string]$Root) {
    if (-not (Test-Path $Root -PathType Container)) {
        throw "Runtime V1 directory is missing: $Root"
    }
    $manifestPath = Join-Path $Root "runtime-manifest.json"
    if (-not (Test-Path $manifestPath -PathType Leaf)) {
        throw "Runtime V1 manifest is missing: $manifestPath"
    }

    # Use the runtime's embedded interpreter and the canonical Python manifest
    # verifier. This checks schema-2 metadata, every inventoried path/size/hash,
    # required locks and entry points, extra files, symlinks, and content policy.
    $python = Join-Path $Root "python\python.exe"
    $backend = Join-Path $Root "app\backend"
    $verify = "import sys; sys.path.insert(0, sys.argv[1]); from figuresmith.runtime.manifest import verify_runtime_manifest; verify_runtime_manifest(sys.argv[2], sys.argv[3])"
    if (-not (Test-Path $python -PathType Leaf)) {
        throw "Runtime V1 embedded interpreter is missing: $python"
    }
    & $python -B -c $verify $backend $manifestPath $Root
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime V1 manifest verification failed: $Root"
    }

    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.version -ne $Version) {
        throw "Runtime V1 version does not match desktop version $Version"
    }
}
Assert-RuntimeV1 $RuntimeRoot
Write-Host "Using self-contained Runtime V1 companion pack: $RuntimeRoot" -ForegroundColor DarkGreen

# NSIS/MSI build only the shell. The multi-gigabyte runtime is deliberately not
# a Tauri resource; installed shells locate a separately delivered companion
# `runtime` directory beside the executable. Portable assembly below carries it.
# Keep the staged source directory intact until Portable assembly has copied it.
# The empty `bundle.resources` list above is what keeps it out of the installers.


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

# The installed shell intentionally has no embedded runtime. It fails closed
# until the separately delivered companion `runtime` directory is installed
# beside FigureSmith.exe. Portable assembly carries the selected full variant.
$TauriResources = Join-Path $TauriTarget "resources"
if (Test-Path (Join-Path $TauriResources "runtime")) {
    Remove-Item (Join-Path $TauriResources "runtime") -Recurse -Force
}

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
# Remove an old display directory through a short name before touching the deep
# runtime tree. New builds publish only the ZIP, never this expanded directory.
if (Test-Path $portableDir) {
    $oldPortableTrash = Join-Path $distDesktop ".trash-old-$PID"
    if (Test-Path $oldPortableTrash) { Remove-Item -LiteralPath $oldPortableTrash -Recurse -Force }
    Move-Item -LiteralPath $portableDir -Destination $oldPortableTrash
    Remove-Item -LiteralPath $oldPortableTrash -Recurse -Force
}
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

$portableStage = Join-Path $distDesktop ".portable-stage-$PID"
$portableZip = Join-Path $distDesktop "$portableName.zip"
$portableZipStage = "$portableZip.partial"
$portablePublished = $false

foreach ($path in @($portableStage, $portableZipStage)) {
    if (Test-Path $path) { Remove-Item -LiteralPath $path -Recurse -Force }
}
if (Test-Path $portableZip) { Remove-Item -LiteralPath $portableZip -Force }

try {
    New-Item -ItemType Directory -Path $portableStage | Out-Null

    foreach ($f in @("LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "README.md", "README_ZH.md", "VERSION", "CHANGELOG.md")) {
        $src = Join-Path $RepoRoot $f
        if (Test-Path $src) { Copy-Item $src (Join-Path $portableStage $f) -Force }
    }

    Copy-Item $releaseExe (Join-Path $portableStage "FigureSmith.exe") -Force
    Write-Host "Included FigureSmith.exe in portable pack"

    # Keep the 4.5 GiB Torch tree under a short staging root for every recursive
    # operation. robocopy handles long Windows paths more reliably than
    # Copy-Item -Recurse; its success exit codes are 0 through 7.
    $portableRuntime = Join-Path $portableStage "runtime"
    New-Item -ItemType Directory -Path $portableRuntime | Out-Null
    & robocopy.exe $RuntimeRoot $portableRuntime /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Runtime V1 copy failed with robocopy exit code $LASTEXITCODE"
    }
    Assert-RuntimeV1 $portableRuntime

    @"
# FigureSmith Portable

- Product: FigureSmith / 图匠
- Version: $Version
- This Portable archive includes a self-contained Runtime V1 pack. FigureSmith uses only `runtime\python\python.exe`; no system Python, pip, venv creation, or network installation is used.
- Python packages are preinstalled and verified before launch. Model weights remain external and are imported through the app.
- Import SAM3/RMBG model weights in the app.
- Backend must bind 127.0.0.1 only (desktop sidecar enforces this).

See docs in the full repository: docs/phase6-delivery.md, docs/release.md
"@ | Set-Content (Join-Path $portableStage "README-PORTABLE.md") -Encoding utf8

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($portableStage, $portableZipStage)
    Move-Item -LiteralPath $portableZipStage -Destination $portableZip
    Write-Host "Portable zip: $portableZip" -ForegroundColor Green

    & (Join-Path $PSScriptRoot "write-checksums.ps1") -Path $distDesktop -OutFile (Join-Path $distDesktop "checksums.txt")
    $portablePublished = $true
} finally {
    if (Test-Path $portableStage) {
        # Rename to an even shorter path before recursive deletion so cleanup
        # does not strand deep Torch license paths.
        $trash = Join-Path $distDesktop ".trash-$PID"
        if (Test-Path $trash) { Remove-Item -LiteralPath $trash -Recurse -Force }
        Move-Item -LiteralPath $portableStage -Destination $trash
        Remove-Item -LiteralPath $trash -Recurse -Force
    }
    if (Test-Path $portableZipStage) { Remove-Item -LiteralPath $portableZipStage -Force }
    if (-not $portablePublished -and (Test-Path $portableZip)) {
        Remove-Item -LiteralPath $portableZip -Force
    }
}

Write-Host "Desktop packaging done -> $distDesktop" -ForegroundColor Green
