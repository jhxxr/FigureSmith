# Extract a CHANGELOG.md section for the given version into a release notes file.
# Usage:
#   ./scripts/ci/extract-changelog.ps1 -Version 0.6.1 -OutFile release-notes.md

param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$OutFile = "release-notes.md",
    [string]$ChangelogPath = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($ChangelogPath)) {
    $ChangelogPath = Join-Path $RepoRoot "CHANGELOG.md"
}
if (-not (Test-Path $ChangelogPath)) {
    Write-Error "CHANGELOG not found: $ChangelogPath"
}

$Version = $Version.Trim()
if ($Version.StartsWith("v") -or $Version.StartsWith("V")) {
    $Version = $Version.Substring(1)
}

$text = Get-Content $ChangelogPath -Raw
# Match ## [0.6.1] ... until next ## [ or EOF
$pattern = "(?ms)^## \[$([regex]::Escape($Version))\].*?(?=^## \[|\z)"
$match = [regex]::Match($text, $pattern)

$utf8NoBom = New-Object System.Text.UTF8Encoding $false

if ($match.Success) {
    $body = $match.Value.Trim() + "`n"
    $header = @"
## FigureSmith v$Version

"@
    # If section already starts with ## [ver], keep it; also add product line for GH release
    $out = "FigureSmith **v$Version** automatic release.`n`n" + $body + "`n`n---\n\nModel weights are **not** included. Import SAM3 / RMBG after install.\n"
    [System.IO.File]::WriteAllText((Join-Path $RepoRoot $OutFile), $out, $utf8NoBom)
    Write-Host "Wrote changelog section for $Version -> $OutFile" -ForegroundColor Green
    exit 0
}

$fallback = @"
## FigureSmith v$Version

Automated release from tag ``v$Version``.

See [CHANGELOG.md](./CHANGELOG.md) for details.

### Artifacts

- Desktop Setup / Portable (Windows x64)
- Runtime Pack (Windows NVIDIA) — **no model weights**

### Notes

- Source license (MIT) does not grant rights to third-party model weights.
- Import SAM3 / RMBG via the Models page or CLI after install.
"@
[System.IO.File]::WriteAllText((Join-Path $RepoRoot $OutFile), $fallback, $utf8NoBom)
Write-Warning "No CHANGELOG section for $Version; wrote fallback notes -> $OutFile"
exit 0
