# FigureSmith — write SHA-256 checksums for release artifacts
#
# Usage:
#   ./scripts/write-checksums.ps1 -Path dist-desktop
#   ./scripts/write-checksums.ps1 -Path dist-runtime -OutFile dist-runtime/checksums.txt

param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Path)) {
    Write-Error "Path not found: $Path"
}

$target = Resolve-Path $Path
if ([string]::IsNullOrWhiteSpace($OutFile)) {
    if (Test-Path $target -PathType Container) {
        $OutFile = Join-Path $target "checksums.txt"
    } else {
        $OutFile = Join-Path (Split-Path $target -Parent) "checksums.txt"
    }
}

$files = @()
if (Test-Path $target -PathType Leaf) {
    $files = @(Get-Item $target)
} else {
    $files = Get-ChildItem -Path $target -File -Recurse | Where-Object {
        $_.Name -ne "checksums.txt"
    }
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# FigureSmith SHA-256 checksums")
$lines.Add("# Generated: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))")
$lines.Add("")

foreach ($f in $files | Sort-Object FullName) {
    $hash = Get-FileHash -Algorithm SHA256 -Path $f.FullName
    $rel = $f.FullName
    if (Test-Path $target -PathType Container) {
        $rel = $f.FullName.Substring($target.Path.Length).TrimStart("\", "/")
    } else {
        $rel = $f.Name
    }
    $rel = $rel -replace "\\", "/"
    $lines.Add("$($hash.Hash.ToLowerInvariant())  $rel")
}

$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
}
$lines | Set-Content -Path $OutFile -Encoding utf8
Write-Host "Wrote $($files.Count) checksum(s) -> $OutFile" -ForegroundColor Green
