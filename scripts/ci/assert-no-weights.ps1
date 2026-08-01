# Assert that a directory / zip tree contains no model weight files.
# Usage:
#   ./scripts/ci/assert-no-weights.ps1 -Path dist-runtime
#   ./scripts/ci/assert-no-weights.ps1 -Path dist-desktop

param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Path)) {
    Write-Error "Path not found: $Path"
}

$weightExt = @(
    ".pt", ".pth", ".onnx", ".safetensors", ".gguf", ".ckpt", ".h5", ".pb", ".bin"
)

$bad = New-Object System.Collections.Generic.List[string]

function Test-WeightName([string]$name) {
    $n = $name.ToLowerInvariant()
    $ext = [System.IO.Path]::GetExtension($n)
    if ($weightExt -contains $ext) { return $true }
    if ($n -eq "model.safetensors" -or $n -like "model-*.safetensors") { return $true }
    return $false
}

# 1) Plain files under Path
Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    if (Test-WeightName $_.Name) {
        $bad.Add($_.FullName) | Out-Null
    }
}

# 2) Inspect zip members (do not extract)
Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
Get-ChildItem -Path $Path -Recurse -File -Filter "*.zip" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($_.FullName)
        try {
            foreach ($entry in $zip.Entries) {
                $entryName = $entry.FullName
                $base = [System.IO.Path]::GetFileName($entryName)
                if (Test-WeightName $base) {
                    $bad.Add(("$($_.FullName) :: $entryName")) | Out-Null
                }
            }
        } finally {
            $zip.Dispose()
        }
    } catch {
        Write-Warning "Could not scan zip $($_.FullName): $($_.Exception.Message)"
    }
}

if ($bad.Count -gt 0) {
    Write-Host "ERROR: weight-like files found under $Path" -ForegroundColor Red
    $bad | Select-Object -First 40 | ForEach-Object { Write-Host "  - $_" }
    if ($bad.Count -gt 40) {
        Write-Host "  ... and $($bad.Count - 40) more"
    }
    exit 1
}

Write-Host "OK: no model weights under $Path" -ForegroundColor Green
exit 0
