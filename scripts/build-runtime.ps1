# FigureSmith - build the application-only Windows Runtime Pack.
#
# The pack contains FigureSmith source, legal metadata, dependency guidance,
# and an integrity manifest. It deliberately does not contain Python, pip,
# PyTorch, CUDA wheels, SAM3, model weights, caches, or user data. The desktop
# resolver scans a supported base Python and creates a separate user environment.

param(
    [string]$Version = "",
    [switch]$Zip,
    [switch]$SkipZip,
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($Version)) {
    $versionFile = Join-Path $RepoRoot "VERSION"
    $Version = if (Test-Path $versionFile) { (Get-Content $versionFile -Raw).Trim() } else { "0.0.0-dev" }
}

$distRoot = Join-Path $RepoRoot "dist-runtime"
$packName = "FigureSmith-Runtime-Windows-$Version"
$packDir = Join-Path $distRoot $packName
if (Test-Path $packDir) { Remove-Item -Recurse -Force $packDir }
New-Item -ItemType Directory -Path $packDir -Force | Out-Null

Write-Host "=== FigureSmith application Runtime Pack ===" -ForegroundColor Cyan
Write-Host "Version : $Version"
Write-Host "Output  : $packDir"

function Test-IsExcluded([string]$fullPath, [string]$root) {
    $extension = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()
    if ($extension -in @(".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin")) {
        return $true
    }
    $relative = $fullPath.Substring($root.Length).TrimStart("\", "/")
    $parts = $relative -split "[\\/]" | ForEach-Object { $_.ToLowerInvariant() }
    $skip = @("__pycache__", ".venv", "venv", "node_modules", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", "outputs", "uploads", "target", ".staging", ".trash")
    foreach ($part in $parts) {
        if ($skip -contains $part) { return $true }
    }
    if ($parts.Count -ge 2 -and $parts[0] -eq "resources" -and $parts[1] -eq "models") {
        return $true
    }
    return $false
}

function Copy-FilteredTree([string]$source, [string]$destination) {
    if (-not (Test-Path $source -PathType Container)) {
        throw "Required application source directory is missing: $source"
    }
    $sourceRoot = (Resolve-Path $source).Path
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Get-ChildItem -LiteralPath $sourceRoot -Recurse -File | ForEach-Object {
        if (Test-IsExcluded $_.FullName $sourceRoot) { return }
        $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart("\", "/")
        $target = Join-Path $destination $relative
        $parent = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}

$appDir = Join-Path $packDir "app"
Copy-FilteredTree (Join-Path $RepoRoot "apps\backend") (Join-Path $appDir "backend")
Copy-FilteredTree (Join-Path $RepoRoot "vendor\autofigure_edit") (Join-Path $appDir "vendor\autofigure_edit")
Copy-FilteredTree (Join-Path $RepoRoot "vendor\svg_edit") (Join-Path $appDir "vendor\svg_edit")
Copy-FilteredTree (Join-Path $RepoRoot "resources") (Join-Path $appDir "resources")

foreach ($file in @("LICENSE", "NOTICE.md", "THIRD_PARTY_NOTICES.md", "VERSION")) {
    $source = Join-Path $RepoRoot $file
    if (Test-Path $source -PathType Leaf) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $packDir $file) -Force
    }
}

$requirementsFiles = @("requirements-runtime.txt", "requirements-bootstrap.txt", "requirements-models.txt")
foreach ($requirementsFile in $requirementsFiles) {
    $requirementsSource = Join-Path $RepoRoot "scripts\runtime\$requirementsFile"
    if (-not (Test-Path $requirementsSource -PathType Leaf)) {
        throw "Runtime dependency guidance is missing: $requirementsSource"
    }
    Copy-Item $requirementsSource (Join-Path $packDir $requirementsFile) -Force
}

$manifest = [ordered]@{
    schema = 1
    product = "FigureSmith"
    version = $Version
    platform = "Windows"
    arch = "x86_64"
    application_only = $true
    python_required = "external"
    runtime_complete = $false
    contains_weights = $false
    contains_cache = $false
    python_policy = "Use a supported user-installed Python 3.10-3.12 only as the base for the isolated FigureSmith environment under LocalAppData."
    requirements_file = "requirements-runtime.txt"
    model_policy = "Torch, torchvision, SAM3, CUDA, and model weights remain user-managed."
} | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText(
    (Join-Path $packDir "MANIFEST.json"),
    $manifest,
    [System.Text.UTF8Encoding]::new($false)
)

$buildPython = if (-not [string]::IsNullOrWhiteSpace($PythonExecutable)) {
    if (-not (Test-Path $PythonExecutable -PathType Leaf)) { throw "PythonExecutable does not exist: $PythonExecutable" }
    (Resolve-Path $PythonExecutable).Path
} else {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw "Python is required on the build machine to generate the application manifest" }
    $command.Source
}

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $RepoRoot "apps\backend"
    $manifestCode = "import sys; from pathlib import Path; from figuresmith.runtime.manifest import write_runtime_manifest; write_runtime_manifest(Path(sys.argv[1]), version=sys.argv[2], platform='Windows', arch='x86_64', runtime_complete=False)"
    & $buildPython -c $manifestCode $packDir $Version
    if ($LASTEXITCODE -ne 0) { throw "Application runtime-manifest.json generation failed" }
    $verifyCode = "import sys; from pathlib import Path; from figuresmith.runtime.manifest import verify_runtime_manifest; verify_runtime_manifest(Path(sys.argv[1]), Path(sys.argv[2]), require_complete=False); print('application manifest verification: OK')"
    & $buildPython -c $verifyCode (Join-Path $packDir "runtime-manifest.json") $packDir
    if ($LASTEXITCODE -ne 0) { throw "Application runtime-manifest.json verification failed" }
} finally {
    if ($null -eq $oldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $oldPythonPath
    }
}

$readme = @"
# FigureSmith Runtime Pack (Windows)

This archive contains the FigureSmith application and its dependency guidance.
It intentionally does **not** contain Python, pip, PyTorch, CUDA, SAM3, model
weights, caches, or user data.

## First launch

The desktop app scans supported Python installations, uses one only as a base, and
creates a dedicated environment under `%LOCALAPPDATA%\FigureSmith\python-env`.
The first launch installs bootstrap service packages only into that environment;
it never modifies the base Python installation.

For local SAM3 inference, install a CUDA-compatible PyTorch/torchvision pair
and the remaining model packages into the isolated environment:

    python -m pip install -r requirements-models.txt

The app reports the isolated environment path and missing model packages. The
base Python and existing environments are left unchanged.
The backend remains loopback-only and strict-offline by default. A supported
NVIDIA driver is required for CUDA inference; the application itself does not
install drivers or change the system Python installation.

See `runtime-manifest.json` for the immutable application inventory and the
license files for source notices.
"@
$readme | Set-Content (Join-Path $packDir "README-RUNTIME.md") -Encoding utf8

# README-RUNTIME.md is part of the immutable application pack, so regenerate
# the inventory after all package metadata has been written.
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $RepoRoot "apps\backend"
    $manifestCode = "import sys; from pathlib import Path; from figuresmith.runtime.manifest import write_runtime_manifest; write_runtime_manifest(Path(sys.argv[1]), version=sys.argv[2], platform='Windows', arch='x86_64', runtime_complete=False)"
    & $buildPython -c $manifestCode $packDir $Version
    if ($LASTEXITCODE -ne 0) { throw "Final application runtime-manifest.json generation failed" }
    $verifyCode = "import sys; from pathlib import Path; from figuresmith.runtime.manifest import verify_runtime_manifest; verify_runtime_manifest(Path(sys.argv[1]), Path(sys.argv[2]), require_complete=False); print('final application manifest verification: OK')"
    & $buildPython -c $verifyCode (Join-Path $packDir "runtime-manifest.json") $packDir
    if ($LASTEXITCODE -ne 0) { throw "Final application runtime-manifest.json verification failed" }
} finally {
    if ($null -eq $oldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $oldPythonPath
    }
}

$embedded = Get-ChildItem -LiteralPath $packDir -Recurse -File | Where-Object {
    $_.Name -ieq "python.exe" -or $_.Name -like "python*.dll" -or $_.Extension -ieq ".whl"
}
if ($embedded) {
    throw "Refusing to publish application Runtime Pack: Python or dependency artifacts found:`n$($embedded.FullName -join "`n")"
}

$bad = Get-ChildItem -LiteralPath $packDir -Recurse -File | Where-Object {
    $_.Extension.ToLowerInvariant() -in @(".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin")
}
if ($bad) {
    throw "Refusing to publish Runtime Pack: weight-like files found:`n$($bad.FullName -join "`n")"
}

Write-Host "Application Runtime tree ready: $packDir" -ForegroundColor Green
if ($Zip -or -not $SkipZip) {
    $zipPath = Join-Path $distRoot "$packName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($packDir, $zipPath)
    Write-Host "Zip: $zipPath" -ForegroundColor Green
}

& (Join-Path $PSScriptRoot "write-checksums.ps1") -Path $distRoot -OutFile (Join-Path $distRoot "checksums.txt")
Write-Host "Done. application_only=true; python_required=external; contains_weights=false" -ForegroundColor Green
