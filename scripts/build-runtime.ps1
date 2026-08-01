# FigureSmith — build Runtime Pack (no model weights)
#
# Produces:
#   dist-runtime/FigureSmith-Runtime-Windows-NVIDIA-<CudaTag>-<Version>/
#   dist-runtime/FigureSmith-Runtime-Windows-NVIDIA-<CudaTag>-<Version>.zip (optional)
#   dist-runtime/checksums.txt
#
# Does NOT download or embed sam3.pt / model.safetensors / gated weights.

param(
    [string]$CudaTag = "cu128",
    [string]$Version = "",
    [switch]$Zip,
    [switch]$SkipZip
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

$distRoot = Join-Path $RepoRoot "dist-runtime"
$packName = "FigureSmith-Runtime-Windows-NVIDIA-$CudaTag-$Version"
$packDir = Join-Path $distRoot $packName

Write-Host "=== FigureSmith build-runtime ===" -ForegroundColor Cyan
Write-Host "Version : $Version"
Write-Host "CUDA tag: $CudaTag"
Write-Host "Output  : $packDir"

if (Test-Path $packDir) {
    Remove-Item -Recurse -Force $packDir
}
New-Item -ItemType Directory -Path $packDir | Out-Null

function Test-IsWeightOrExcluded([string]$fullPath, [string]$root) {
    $name = [System.IO.Path]::GetFileName($fullPath).ToLowerInvariant()
    $ext = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()
    $weightExt = @(".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin")
    if ($weightExt -contains $ext) { return $true }

    $rel = $fullPath.Substring($root.Length).TrimStart("\", "/").ToLowerInvariant()
    $parts = $rel -split "[\\/]"
    $skip = @("__pycache__", ".venv", "venv", "node_modules", ".git", "outputs", "uploads", "target", ".staging", ".trash")
    foreach ($p in $parts) {
        if ($skip -contains $p) { return $true }
    }
    # resources/models weight staging
    if ($parts -contains "resources" -and $parts -contains "models") { return $true }
    # vendor gallery bloat optional skip
    if ($parts -contains "img" -and $parts -contains "case") { return $true }
    return $false
}

function Copy-FilteredTree([string]$Src, [string]$Dst) {
    if (-not (Test-Path $Src)) {
        Write-Warning "Skip missing source: $Src"
        return
    }
    $srcFull = (Resolve-Path $Src).Path
    Get-ChildItem -Path $srcFull -Recurse -File | ForEach-Object {
        if (Test-IsWeightOrExcluded $_.FullName $srcFull) {
            return
        }
        $rel = $_.FullName.Substring($srcFull.Length).TrimStart("\", "/")
        $destPath = Join-Path $Dst $rel
        $destParent = Split-Path -Parent $destPath
        if (-not (Test-Path $destParent)) {
            New-Item -ItemType Directory -Path $destParent -Force | Out-Null
        }
        Copy-Item -Path $_.FullName -Destination $destPath -Force
    }
}

# App code
$appDir = Join-Path $packDir "app"
New-Item -ItemType Directory -Path $appDir | Out-Null
Copy-FilteredTree (Join-Path $RepoRoot "apps\backend") (Join-Path $appDir "backend")
Copy-FilteredTree (Join-Path $RepoRoot "vendor\autofigure_edit") (Join-Path $appDir "vendor\autofigure_edit")
Copy-FilteredTree (Join-Path $RepoRoot "vendor\svg_edit") (Join-Path $appDir "vendor\svg_edit")
Copy-FilteredTree (Join-Path $RepoRoot "resources") (Join-Path $appDir "resources")

# Compliance
foreach ($f in @("LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "VERSION")) {
    $src = Join-Path $RepoRoot $f
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $packDir $f) -Force
    }
}

# Requirements
$reqSrc = Join-Path $RepoRoot "apps\backend\requirements.txt"
$reqDst = Join-Path $packDir "requirements-runtime.txt"
if (Test-Path $reqSrc) {
    $header = @(
        "# FigureSmith Runtime requirements (Windows NVIDIA $CudaTag)",
        "# Install torch/vision from the official CUDA index for your driver, e.g.:",
        "#   pip install torch torchvision --index-url https://download.pytorch.org/whl/$CudaTag",
        "# Then:",
        "#   pip install -r requirements-runtime.txt",
        "# SAM3 is installed separately per upstream docs (no weights bundled).",
        "#"
    )
    $body = Get-Content $reqSrc
    ($header + $body) | Set-Content -Path $reqDst -Encoding utf8
}

# Scripts inside pack
$packScripts = Join-Path $packDir "scripts"
New-Item -ItemType Directory -Path $packScripts | Out-Null

@'
# Install runtime Python deps into local .venv (no model weights).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv 2>$null
    if (-not (Test-Path ".venv")) { python -m venv .venv }
}
$py = Join-Path $Root ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
Write-Host "Install CUDA torch separately if needed, then:"
Write-Host "  .\.venv\Scripts\python -m pip install -r requirements-runtime.txt"
'@ | Set-Content (Join-Path $packScripts "install-deps.ps1") -Encoding utf8

@'
# Run FigureSmith backend from this Runtime Pack (loopback only).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$(Join-Path $Root 'app\backend');$(Join-Path $Root 'app\vendor\autofigure_edit')"
$env:FIGURESMITH_STRICT_OFFLINE = if ($env:FIGURESMITH_STRICT_OFFLINE) { $env:FIGURESMITH_STRICT_OFFLINE } else { "1" }
$env:FIGURESMITH_INSTALL_ROOT = if ($env:FIGURESMITH_INSTALL_ROOT) { $env:FIGURESMITH_INSTALL_ROOT } else { $Root }
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py (Join-Path $Root "app\backend\main.py") @args
'@ | Set-Content (Join-Path $packScripts "run-backend.ps1") -Encoding utf8

# MANIFEST
$manifest = @{
    product            = "FigureSmith"
    version            = $Version
    platform           = "Windows"
    arch               = "x86_64"
    cuda_tag           = $CudaTag
    contains_weights   = $false
    contains_sam3_pt   = $false
    contains_rmbg      = $false
    notes              = @(
        "Model weights are NOT included. Import SAM3/RMBG via the app Models page or CLI.",
        "Source license (MIT) does not grant rights to third-party model weights."
    )
} | ConvertTo-Json -Depth 5
$manifestPath = Join-Path $packDir "MANIFEST.json"
[System.IO.File]::WriteAllText($manifestPath, $manifest, [System.Text.UTF8Encoding]::new($false))

# Generate the structured inventory consumed by the desktop resolver. This
# dependency-install pack is intentionally marked incomplete because it does
# not contain the isolated CPython runtime; the complete assembly pipeline
# uses the same helper with runtime_complete=true after Python is staged.
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    throw "Python is required to generate runtime-manifest.json"
}
$previousPyPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $RepoRoot "apps\backend"
    $manifestCode = "import sys; from pathlib import Path; from figuresmith.runtime.manifest import write_runtime_manifest; write_runtime_manifest(Path(sys.argv[1]), version=sys.argv[2], platform='Windows', arch='x86_64', runtime_complete=False)"
    & $pythonCommand.Source -c $manifestCode $packDir $Version
    if ($LASTEXITCODE -ne 0) {
        throw "runtime-manifest.json generation failed"
    }
} finally {
    if ($null -eq $previousPyPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $previousPyPath
    }
}
Write-Host "Structured manifest: $(Join-Path $packDir 'runtime-manifest.json')" -ForegroundColor DarkGreen

@'
# FigureSmith Runtime Pack (Windows / NVIDIA)

This archive provides **application code + dependency install scripts** for offline-friendly setups.

## Not included

- `sam3.pt` or any SAM checkpoint
- RMBG `model.safetensors` / gated weights
- CUDA drivers

## Quick start

1. Install NVIDIA driver + CUDA-compatible PyTorch for your GPU.
2. `./scripts/install-deps.ps1` then `pip install -r requirements-runtime.txt`
3. Optionally install the `sam3` Python package per upstream docs.
4. `./scripts/run-backend.ps1` → http://127.0.0.1:8765/
5. Import models in the UI (`/models.html`) or via `python -m figuresmith.models.cli`

## Desktop shell

Use the separate FigureSmith desktop installer/portable build; point it at this runtime Python via `FIGURESMITH_PYTHON` if needed.

## License

See LICENSE, NOTICE.md, THIRD_PARTY_NOTICES.md.
Source code license ≠ third-party model weight licenses.
'@ | Set-Content (Join-Path $packDir "README-RUNTIME.md") -Encoding utf8

# Safety scan: fail if any weight slipped in
$bad = Get-ChildItem -Path $packDir -Recurse -File | Where-Object {
    $ext = $_.Extension.ToLowerInvariant()
    $ext -in @(".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin")
}
if ($bad) {
    Write-Error "Refusing to publish Runtime Pack: weight-like files found:`n$($bad.FullName -join "`n")"
}

Write-Host "Runtime tree ready: $packDir" -ForegroundColor Green

if ($Zip -or -not $SkipZip) {
    $zipPath = Join-Path $distRoot "$packName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    # Compress-Archive cannot always handle very long paths; use .NET
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($packDir, $zipPath)
    Write-Host "Zip: $zipPath" -ForegroundColor Green
}

& (Join-Path $PSScriptRoot "write-checksums.ps1") -Path $distRoot -OutFile (Join-Path $distRoot "checksums.txt")

Write-Host "Done. contains_weights=false" -ForegroundColor Green
