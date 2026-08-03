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

function Test-WeightName([string]$name, [string]$relativePath = "") {
    $n = $name.ToLowerInvariant()
    $relative = $relativePath.Replace("\", "/").TrimStart("/").ToLowerInvariant()
    $ext = [System.IO.Path]::GetExtension($n)
    # Runtime V1 legitimately carries import hooks and CUDA payloads with
    # these suffixes inside site-packages. Real checkpoints remain forbidden,
    # including when they happen to be installed under site-packages.
    $inSitePackages = $relative -match "(^|/)python/lib/site-packages/"
    if ($inSitePackages -and $ext -in @(".pth", ".bin")) { return $false }
    if ($weightExt -contains $ext) { return $true }
    if ($n -eq "model.safetensors" -or $n -like "model-*.safetensors") { return $true }
    return $false
}

# 1) Plain files under Path
$rootPath = (Resolve-Path $Path).Path
Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    $relative = $_.FullName.Substring($rootPath.Length).TrimStart("\", "/")
    if (Test-WeightName $_.Name $relative) {
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
                if (Test-WeightName $base $entryName) {
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
