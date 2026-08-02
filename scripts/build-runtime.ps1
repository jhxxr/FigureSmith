# FigureSmith — build a self-contained Windows Runtime V1 pack.
#
# Acquisition and assembly are separate. This wrapper never resolves or fetches
# a dependency: it consumes committed locks plus a pre-acquired wheelhouse, and
# assemble_runtime.py installs them with --no-index/--require-hashes/--no-deps.

param(
    [ValidateSet("cpu", "cu128")]
    [string]$Variant = "cpu",
    [string]$Version = "",
    [string]$Wheelhouse = "",
    [string]$LockRoot = "",
    [string]$PythonExecutable = "",
    [string]$BuilderPython = "",
    [switch]$Zip,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($Version)) {
    $versionFile = Join-Path $RepoRoot "VERSION"
    $Version = if (Test-Path $versionFile) { (Get-Content $versionFile -Raw).Trim() } else { "0.0.0-dev" }
}
if ([string]::IsNullOrWhiteSpace($LockRoot)) {
    $LockRoot = Join-Path $RepoRoot "locks"
}
if ([string]::IsNullOrWhiteSpace($Wheelhouse)) {
    $Wheelhouse = Join-Path $RepoRoot "build\wheelhouse-$Variant"
}
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "Build-machine Python is required to run the assembler"
    }
    $PythonExecutable = $command.Source
}
if ([string]::IsNullOrWhiteSpace($BuilderPython)) {
    $BuilderPython = $PythonExecutable
}
if (-not (Test-Path $BuilderPython -PathType Leaf)) {
    throw "BuilderPython does not exist: $BuilderPython"
}
if (-not (Test-Path $PythonExecutable -PathType Leaf)) {
    throw "PythonExecutable does not exist: $PythonExecutable"
}
if (-not (Test-Path $LockRoot -PathType Container)) {
    throw "LockRoot does not exist: $LockRoot"
}
if (-not (Test-Path $Wheelhouse -PathType Container)) {
    throw "Wheelhouse does not exist: $Wheelhouse"
}

$distRoot = Join-Path $RepoRoot "dist-runtime"
$variantLabel = if ($Variant -eq "cu128") { "NVIDIA-cu128" } else { "CPU" }
$packName = "FigureSmith-Runtime-Windows-$variantLabel-$Version"
$packDir = Join-Path $distRoot $packName
# pip still uses legacy Win32 path handling for parts of wheel installation.
# Assemble under a short name on the destination volume, then rename the
# completed top-level directory without traversing its deep Torch children.
$stageDir = Join-Path $distRoot ".stage-$Variant"
$trashDir = Join-Path $distRoot ".trash-$Variant"
$zipPath = Join-Path $distRoot "$packName.zip"
$zipStagePath = "$zipPath.partial"
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
if (Test-Path $stageDir) { Remove-Item -LiteralPath $stageDir -Recurse -Force }
if (Test-Path $trashDir) { Remove-Item -LiteralPath $trashDir -Recurse -Force }
if (Test-Path $zipStagePath) { Remove-Item -LiteralPath $zipStagePath -Force }
if (Test-Path $packDir) {
    # Shorten the root before recursive deletion. Deleting the long display
    # path directly can exceed Win32 MAX_PATH in Torch's nested license tree.
    Rename-Item -LiteralPath $packDir -NewName (Split-Path $trashDir -Leaf)
    Remove-Item -LiteralPath $trashDir -Recurse -Force
}

Write-Host "=== FigureSmith Runtime V1 ===" -ForegroundColor Cyan
Write-Host "Version    : $Version"
Write-Host "Variant    : $Variant"
Write-Host "Wheelhouse : $Wheelhouse"
Write-Host "Output     : $packDir"

$published = $false
try {
    & $PythonExecutable `
        (Join-Path $RepoRoot "scripts\runtime\assemble_runtime.py") `
        --variant $Variant `
        --lock-root $LockRoot `
        --wheelhouse $Wheelhouse `
        --out $stageDir `
        --version $Version `
        --python $BuilderPython
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime V1 assembly failed"
    }

    # Verify while the path is still short. Traversing the renamed display path
    # can hit Win32 MAX_PATH inside Torch's deeply nested license inventory even
    # though the top-level Rename-Item itself succeeds without traversing it.
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $RepoRoot "apps\backend"
        & $PythonExecutable -m figuresmith.runtime.manifest `
            (Join-Path $stageDir "runtime-manifest.json") $stageDir
        if ($LASTEXITCODE -ne 0) {
            throw "Runtime manifest verification failed"
        }
    } finally {
        if ($null -eq $oldPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONPATH = $oldPythonPath
        }
    }

    if (-not (Test-Path (Join-Path $stageDir "python\python.exe") -PathType Leaf)) {
        throw "Refusing to publish Runtime V1: embedded python.exe is missing"
    }

    # Zip the short staging tree before the rename for the same MAX_PATH reason.
    if ($Zip -or -not $SkipZip) {
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($stageDir, $zipStagePath)
    }

    # The manifest writer already rejects loose wheels, model weights, caches,
    # mutable data, and unexpected inventory entries. Rename only after every
    # recursive operation has passed; this does not traverse deep children.
    Rename-Item -LiteralPath $stageDir -NewName $packName
    if ($Zip -or -not $SkipZip) {
        Move-Item -LiteralPath $zipStagePath -Destination $zipPath
        Write-Host "Zip: $zipPath" -ForegroundColor Green
    }

    $checksumTarget = if ($Zip -or -not $SkipZip) {
        Join-Path $distRoot "$packName.zip"
    } else {
        # The manifest already hashes every file in the unpacked tree. Rewalking the
        # long display path here both duplicates that work and can hit MAX_PATH in
        # Torch's nested license inventory, so a no-zip build checksums the manifest
        # itself as the root of trust.
        Join-Path $packDir "runtime-manifest.json"
    }
    & (Join-Path $PSScriptRoot "write-checksums.ps1") `
        -Path $checksumTarget `
        -OutFile (Join-Path $distRoot "checksums.txt")
    $published = $true
} catch {
    if (Test-Path $stageDir) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $zipStagePath) {
        Remove-Item -LiteralPath $zipStagePath -Force -ErrorAction SilentlyContinue
    }
    if (-not $published -and (Test-Path $zipPath)) {
        Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
    }
    if (-not $published -and (Test-Path $packDir)) {
        # A checksum/publication failure after rename must not leave a tree that
        # looks publishable. Shorten before deletion to avoid MAX_PATH failures.
        if (Test-Path $trashDir) {
            Remove-Item -LiteralPath $trashDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        Rename-Item -LiteralPath $packDir -NewName (Split-Path $trashDir -Leaf) -ErrorAction SilentlyContinue
        if (Test-Path $trashDir) {
            Remove-Item -LiteralPath $trashDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    throw
}

Write-Host "Runtime tree ready: $packDir" -ForegroundColor Green
Write-Host "Done. schema=2; variant=$Variant; runtime_complete=true; contains_weights=false" -ForegroundColor Green
