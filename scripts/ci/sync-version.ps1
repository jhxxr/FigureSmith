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

# 4) apps/desktop/package.json root version
$desktopPackage = Join-Path $RepoRoot "apps\desktop\package.json"
if (Test-Path $desktopPackage) {
    $t = Get-FileText $desktopPackage
    $match = [regex]::Match($t, '(?m)^\s{2}"version"\s*:\s*"([^"]+)"')
    if ($match.Success) {
        $cur = $match.Groups[1].Value
        if ($CheckOnly) {
            if ($cur -ne $Version) { $errors.Add("package.json version='$cur' != VERSION '$Version'") | Out-Null }
        } else {
            $replacement = '${1}' + $Version + '${2}'
            $t2 = [regex]::Replace($t, '(?m)^(\s{2}"version"\s*:\s*")[^"]+("\s*,?)$', $replacement, 1)
            Set-FileText $desktopPackage $t2
            Write-Host "Updated package.json -> $Version"
        }
    } else {
        $errors.Add("package.json: root version field not found") | Out-Null
    }
} else {
    $errors.Add("missing $desktopPackage") | Out-Null
}

# 5) apps/desktop/package-lock.json root and application package versions
$desktopLock = Join-Path $RepoRoot "apps\desktop\package-lock.json"
if (Test-Path $desktopLock) {
    $t = Get-FileText $desktopLock
    $top = [regex]::Match($t, '(?m)^\s{2}"version"\s*:\s*"([^"]+)"')
    $app = [regex]::Match(
        $t,
        '(?ms)"packages"\s*:\s*\{\s*\r?\n\s{4}""\s*:\s*\{\s*\r?\n\s{6}"name"\s*:\s*"figuresmith-desktop",\s*\r?\n\s{6}"version"\s*:\s*"([^"]+)"'
    )
    if (-not $top.Success -or -not $app.Success) {
        $errors.Add("package-lock.json: root application version fields not found") | Out-Null
    } elseif ($CheckOnly) {
        if ($top.Groups[1].Value -ne $Version) { $errors.Add("package-lock.json root version='$($top.Groups[1].Value)' != VERSION '$Version'") | Out-Null }
        if ($app.Groups[1].Value -ne $Version) { $errors.Add("package-lock.json application version='$($app.Groups[1].Value)' != VERSION '$Version'") | Out-Null }
    } else {
        $replacement = '${1}' + $Version + '${2}'
        $t = [regex]::Replace($t, '(?m)^(\s{2}"version"\s*:\s*")[^"]+("\s*,?)$', $replacement, 1)
        $t = [regex]::Replace($t, '(?ms)("packages"\s*:\s*\{\s*\r?\n\s{4}""\s*:\s*\{\s*\r?\n\s{6}"name"\s*:\s*"figuresmith-desktop",\s*\r?\n\s{6}"version"\s*:\s*")[^"]+(")', $replacement, 1)
        Set-FileText $desktopLock $t
        Write-Host "Updated package-lock.json -> $Version"
    }
} else {
    $errors.Add("missing $desktopLock") | Out-Null
}

# 6) apps/desktop/src-tauri/Cargo.toml package version
$cargoToml = Join-Path $RepoRoot "apps\desktop\src-tauri\Cargo.toml"
if (Test-Path $cargoToml) {
    $t = Get-FileText $cargoToml
    $match = [regex]::Match($t, '(?m)^version\s*=\s*"([^"]+)"')
    if ($match.Success) {
        $cur = $match.Groups[1].Value
        if ($CheckOnly) {
            if ($cur -ne $Version) { $errors.Add("Cargo.toml version='$cur' != VERSION '$Version'") | Out-Null }
        } else {
            $replacement = '${1}' + $Version + '${2}'
            $t2 = [regex]::Replace($t, '(?m)^(version\s*=\s*")[^"]+("\s*)$', $replacement, 1)
            Set-FileText $cargoToml $t2
            Write-Host "Updated Cargo.toml -> $Version"
        }
    } else {
        $errors.Add("Cargo.toml: package version field not found") | Out-Null
    }
} else {
    $errors.Add("missing $cargoToml") | Out-Null
}

# 7) apps/desktop/src-tauri/Cargo.lock application package version
$cargoLock = Join-Path $RepoRoot "apps\desktop\src-tauri\Cargo.lock"
if (Test-Path $cargoLock) {
    $t = Get-FileText $cargoLock
    $match = [regex]::Match($t, '(?ms)\[\[package\]\]\s*\r?\nname\s*=\s*"figuresmith-desktop"\s*\r?\nversion\s*=\s*"([^"]+)"')
    if ($match.Success) {
        $cur = $match.Groups[1].Value
        if ($CheckOnly) {
            if ($cur -ne $Version) { $errors.Add("Cargo.lock figuresmith-desktop version='$cur' != VERSION '$Version'") | Out-Null }
        } else {
            $replacement = '${1}' + $Version + '${2}'
            $t2 = [regex]::Replace($t, '(?ms)(\[\[package\]\]\s*\r?\nname\s*=\s*"figuresmith-desktop"\s*\r?\nversion\s*=\s*")[^"]+(")', $replacement, 1)
            Set-FileText $cargoLock $t2
            Write-Host "Updated Cargo.lock -> $Version"
        }
    } else {
        $errors.Add("Cargo.lock: figuresmith-desktop package version not found") | Out-Null
    }
} else {
    $errors.Add("missing $cargoLock") | Out-Null
}

# 8) Ensure VERSION file matches when not CheckOnly
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
