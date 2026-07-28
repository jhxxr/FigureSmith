# Assert git tag vX.Y.Z matches root VERSION (X.Y.Z).
# Usage (CI):
#   ./scripts/ci/assert-version-tag.ps1
#   ./scripts/ci/assert-version-tag.ps1 -Tag v0.6.1

param(
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($Tag)) {
    if ($env:GITHUB_REF_TYPE -eq "tag" -and $env:GITHUB_REF_NAME) {
        $Tag = $env:GITHUB_REF_NAME
    } elseif ($env:GITHUB_REF -match "refs/tags/(.+)$") {
        $Tag = $Matches[1]
    } else {
        Write-Host "Not a tag build; skip version-tag assert." -ForegroundColor Yellow
        exit 0
    }
}

$Tag = $Tag.Trim()
if (-not ($Tag -match '^v?\d+\.\d+\.\d+')) {
    Write-Error "Tag '$Tag' does not look like vX.Y.Z"
}

$verFromTag = $Tag.TrimStart("v", "V")
$fileVer = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim()

if ($verFromTag -ne $fileVer) {
    Write-Error "Tag version '$verFromTag' != VERSION file '$fileVer'. Bump VERSION/CHANGELOG before tagging."
}

Write-Host "OK: tag $Tag matches VERSION $fileVer" -ForegroundColor Green
exit 0
