# Split release assets that exceed the GitHub Release per-asset limit.
# The original file is removed only after every part has been written and
# hashed. A companion PowerShell joiner reconstructs the original artifact.

param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [string]$Prefix = "FigureSmith-Release",
    [long]$MaxBytes = 1900000000
)

$ErrorActionPreference = "Stop"
if ($MaxBytes -lt 1MB) { throw "MaxBytes is too small" }
if (-not (Test-Path $Path -PathType Container)) { throw "Asset directory not found: $Path" }
$root = (Resolve-Path $Path).Path

function Get-Relative([string]$FullName) {
    return $FullName.Substring($root.Length).TrimStart("\", "/") -replace "\\", "/"
}

$records = New-Object System.Collections.Generic.List[object]
$files = Get-ChildItem -LiteralPath $root -File | Where-Object {
    $_.Name -notin @("checksums.txt", "$Prefix-parts.json", "$Prefix-Join-Assets.ps1") -and
    $_.Name -notmatch "\.part\d+$"
}

foreach ($file in $files) {
    if ($file.Length -le $MaxBytes) { continue }
    Write-Host "Splitting $($file.Name) ($($file.Length) bytes)" -ForegroundColor DarkCyan
    $parts = New-Object System.Collections.Generic.List[object]
    $inputStream = [System.IO.File]::OpenRead($file.FullName)
    try {
        $buffer = New-Object byte[] (8MB)
        $partIndex = 1
        $remaining = $file.Length
        while ($remaining -gt 0) {
            $partName = "$($file.Name).part$('{0:D3}' -f $partIndex)"
            $partPath = Join-Path $root $partName
            if (Test-Path $partPath) { Remove-Item $partPath -Force }
            $partStream = [System.IO.File]::Open($partPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $partRemaining = [Math]::Min($MaxBytes, $remaining)
                while ($partRemaining -gt 0) {
                    $requested = [int][Math]::Min($buffer.Length, $partRemaining)
                    $read = $inputStream.Read($buffer, 0, $requested)
                    if ($read -le 0) { throw "Unexpected EOF while splitting $($file.Name)" }
                    $partStream.Write($buffer, 0, $read)
                    $partRemaining -= $read
                    $remaining -= $read
                }
            } finally {
                $partStream.Dispose()
            }
            $partHash = (Get-FileHash -Algorithm SHA256 -Path $partPath).Hash.ToLowerInvariant()
            $parts.Add([ordered]@{
                path = $partName
                size_bytes = (Get-Item $partPath).Length
                sha256 = $partHash
            }) | Out-Null
            $partIndex++
        }
    } finally {
        $inputStream.Dispose()
    }
    $records.Add([ordered]@{
        output = $file.Name
        original_size_bytes = $file.Length
        original_sha256 = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash.ToLowerInvariant()
        parts = @($parts)
    }) | Out-Null
    Remove-Item $file.FullName -Force
}

$manifestName = "$Prefix-parts.json"
$manifest = [ordered]@{
    schema = 1
    product = "FigureSmith"
    max_part_bytes = $MaxBytes
    files = @($records)
    file_count = $records.Count
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $root $manifestName) -Encoding utf8

$joinerName = "$Prefix-Join-Assets.ps1"
$joiner = @'
param([string]$Root = "")
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Root)) { $Root = Split-Path -Parent $MyInvocation.MyCommand.Path }
$Root = (Resolve-Path $Root).Path
$manifestPath = Join-Path $Root "__MANIFEST_NAME__"
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
foreach ($entry in @($manifest.files)) {
    $output = Join-Path $Root $entry.output
    if (Test-Path $output) { Remove-Item $output -Force }
    $stream = [System.IO.File]::Open($output, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        foreach ($part in @($entry.parts)) {
            $partPath = Join-Path $Root $part.path
            if (-not (Test-Path $partPath -PathType Leaf)) { throw "Missing asset part: $partPath" }
            if ((Get-Item $partPath).Length -ne [int64]$part.size_bytes) { throw "Asset part size mismatch: $partPath" }
            $hash = (Get-FileHash -Algorithm SHA256 -Path $partPath).Hash.ToLowerInvariant()
            if ($hash -ne $part.sha256) { throw "Asset part SHA-256 mismatch: $partPath" }
            $input = [System.IO.File]::OpenRead($partPath)
            try { $input.CopyTo($stream) } finally { $input.Dispose() }
        }
    } finally {
        $stream.Dispose()
    }
    if ((Get-Item $output).Length -ne [int64]$entry.original_size_bytes) { throw "Reconstructed asset size mismatch: $output" }
    $hash = (Get-FileHash -Algorithm SHA256 -Path $output).Hash.ToLowerInvariant()
    if ($hash -ne $entry.original_sha256) { throw "Reconstructed asset SHA-256 mismatch: $output" }
    Write-Host "Reconstructed $($entry.output)" -ForegroundColor Green
}
Write-Host "All release assets reconstructed." -ForegroundColor Green
'@.Replace("__MANIFEST_NAME__", $manifestName)
$joiner | Set-Content (Join-Path $root $joinerName) -Encoding utf8

& (Join-Path (Split-Path -Parent $PSScriptRoot) "write-checksums.ps1") -Path $root -OutFile (Join-Path $root "checksums.txt")
Write-Host "Wrote $($records.Count) split asset record(s) under $root" -ForegroundColor Green
