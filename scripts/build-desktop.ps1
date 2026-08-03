# FigureSmith — build desktop app (Phase 6 packaging)
#
# Outputs (under dist-desktop/):
#   FigureSmith-Setup-x64-<ver>.*     (from Tauri bundle when present)
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
    if ($manifest.variant -ne "cpu") {
        throw "Desktop installers require the CPU Runtime V1 variant"
    }
}
Assert-RuntimeV1 $RuntimeRoot
Write-Host "Using self-contained Runtime V1 resource: $RuntimeRoot" -ForegroundColor DarkGreen

# Tauri resources are resolved relative to src-tauri. CI already stages the
# CPU pack here; copy an explicitly supplied RuntimeRoot into the same source
# for local/reproducible builds.
$TauriRuntimeSource = Join-Path $Desktop "src-tauri\runtime"
$runtimeRootFull = (Resolve-Path -LiteralPath $RuntimeRoot).Path.TrimEnd("\")
$runtimeSourceFull = [IO.Path]::GetFullPath($TauriRuntimeSource).TrimEnd("\")
if ($runtimeRootFull -ine $runtimeSourceFull) {
    if (Test-Path -LiteralPath $TauriRuntimeSource) {
        Remove-Item -LiteralPath $TauriRuntimeSource -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TauriRuntimeSource -Force | Out-Null
    Get-ChildItem -LiteralPath $RuntimeRoot -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $TauriRuntimeSource $_.Name) -Recurse -Force
    }
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

$TauriResources = Join-Path $TauriTarget "resources"
$PackagedRuntime = Join-Path $TauriResources "runtime"
if (-not (Test-Path (Join-Path $PackagedRuntime "runtime-manifest.json") -PathType Leaf)) {
    throw "Tauri bundle is missing the embedded Runtime V1 resource: $PackagedRuntime"
}
if (-not (Test-Path (Join-Path $PackagedRuntime "python\python.exe") -PathType Leaf)) {
    throw "Tauri bundle is missing the embedded Runtime V1 interpreter"
}
& (Join-Path $PSScriptRoot "ci\assert-no-weights.ps1") -Path $PackagedRuntime

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
    Write-Warning "No Tauri bundle dir at $BundleDir — installer artifacts will be missing."
}

# Remove stale artifacts from older builds so this command never leaves or
# checksums a Portable package after the release channel was simplified to
# installers plus the separately published Runtime V1 archive.
Get-ChildItem -LiteralPath $distDesktop -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "FigureSmith-Portable-*" -or $_.Name -like "README-PORTABLE*" } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

$installerExtensions = @($copied | ForEach-Object { [IO.Path]::GetExtension($_).ToLowerInvariant() })
if (".exe" -notin $installerExtensions -or ".msi" -notin $installerExtensions) {
    throw "Expected both NSIS (.exe) and MSI (.msi) installer artifacts under $BundleDir"
}

& (Join-Path $PSScriptRoot "write-checksums.ps1") -Path $distDesktop -OutFile (Join-Path $distDesktop "checksums.txt")
Write-Host "Desktop packaging done -> $distDesktop" -ForegroundColor Green
