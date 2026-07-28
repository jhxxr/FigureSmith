# Sync version numbers from root VERSION into project files.
# Usage:
#   ./scripts/ci/sync-version.ps1
#   ./scripts/ci/sync-version.ps1 -CheckOnly
#   ./scripts/ci/sync-version.ps1 -Version 0.6.1

param(
    [string]$Version = "",
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($Version)) {
    $verFile = Join-Path $RepoRoot "VERSION"
    if (-not (Test-Path $verFile)) {
        Write-Error "VERSION file not found at repo root"
    }
    $Version = (Get-Content $verFile -Raw).Trim()
}

if ($Version -notmatch '^\d+\.\d+\.\d+([.-][A-Za-z0-9.-]+)?$') {
    Write-Error "Invalid version format: '$Version' (expected X.Y.Z or X.Y.Z-prerelease)"
}

Write-Host "Version: $Version (CheckOnly=$CheckOnly)"

function Get-FileText([string]$path) {
    return [System.IO.File]::ReadAllText($path)
}

function Set-FileText([string]$path, [string]$text) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($path, $text, $utf8NoBom)
}

$errors = New-Object System.Collections.Generic.List[string]

# 1) apps/backend/pyproject.toml  version = "x.y.z"
$pyproject = Join-Path $RepoRoot "apps\backend\pyproject.toml"
if (Test-Path $pyproject) {
    $t = Get-FileText $pyproject
    if ($t -match '(?m)^version\s*=\s*"([^"]+)"') {
        $cur = $Matches[1]
        if ($CheckOnly) {
            if ($cur -ne $Version) { $errors.Add("pyproject.toml version='$cur' != VERSION '$Version'") | Out-Null }
        } else {
            $t2 = [regex]::Replace($t, '(?m)^version\s*=\s*"[^"]+"', "version = `"$Version`"")
            Set-FileText $pyproject $t2
            Write-Host "Updated pyproject.toml -> $Version"
        }
    } else {
        $errors.Add("pyproject.toml: version field not found") | Out-Null
    }
} else {
    $errors.Add("missing $pyproject") | Out-Null
}

# 2) apps/backend/figuresmith/__init__.py  __version__ = "x.y.z"
$initPy = Join-Path $RepoRoot "apps\backend\figuresmith\__init__.py"
if (Test-Path $initPy) {
    $t = Get-FileText $initPy
    if ($t -match '__version__\s*=\s*"([^"]+)"') {
        $cur = $Matches[1]
        if ($CheckOnly) {
            if ($cur -ne $Version) { $errors.Add("__init__.py __version__='$cur' != VERSION '$Version'") | Out-Null }
        } else {
            $t2 = [regex]::Replace($t, '__version__\s*=\s*"[^"]+"', "__version__ = `"$Version`"")
            Set-FileText $initPy $t2
            Write-Host "Updated figuresmith/__init__.py -> $Version"
        }
    } else {
        $errors.Add("__init__.py: __version__ not found") | Out-Null
    }
} else {
    $errors.Add("missing $initPy") | Out-Null
}

# 3) apps/desktop/src-tauri/tauri.conf.json  "version": "x.y.z"
$tauri = Join-Path $RepoRoot "apps\desktop\src-tauri\tauri.conf.json"
if (Test-Path $tauri) {
    $t = Get-FileText $tauri
    if ($t -match '"version"\s*:\s*"([^"]+)"') {
        $cur = $Matches[1]
        if ($CheckOnly) {
            if ($cur -ne $Version) { $errors.Add("tauri.conf.json version='$cur' != VERSION '$Version'") | Out-Null }
        } else {
            # Replace only the first top-level-ish version occurrence (product version)
            $t2 = [regex]::Replace($t, '"version"\s*:\s*"[^"]+"', "`"version`": `"$Version`"", 1)
            Set-FileText $tauri $t2
            Write-Host "Updated tauri.conf.json -> $Version"
        }
    } else {
        $errors.Add("tauri.conf.json: version field not found") | Out-Null
    }
} else {
    Write-Warning "tauri.conf.json not found (skip)"
}

# 4) Ensure VERSION file matches when not CheckOnly
$verFile = Join-Path $RepoRoot "VERSION"
if (-not $CheckOnly) {
    Set-FileText $verFile ($Version + "`n")
    Write-Host "Updated VERSION -> $Version"
} else {
    $fileVer = (Get-Content $verFile -Raw).Trim()
    if ($fileVer -ne $Version) {
        $errors.Add("VERSION file='$fileVer' != expected '$Version'") | Out-Null
    }
}

if ($errors.Count -gt 0) {
    Write-Host "Version check/sync FAILED:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

Write-Host "OK: version $Version" -ForegroundColor Green
exit 0
