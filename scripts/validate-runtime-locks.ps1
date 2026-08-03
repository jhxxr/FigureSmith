# Validate committed FigureSmith runtime locks and an acquired wheelhouse.

param(
    [Parameter(Mandatory = $true)]
    [string]$LockRoot,

    [ValidateSet("cpu", "cu128")]
    [string]$Variant = "",

    [string]$Wheelhouse = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Python) {
    throw "Python is required to validate runtime locks"
}

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $RepoRoot "apps\backend"
    $arguments = @("-m", "figuresmith.runtime.locks", $LockRoot)
    if (-not [string]::IsNullOrWhiteSpace($Variant)) {
        $arguments += @("--variant", $Variant)
    }
    if (-not [string]::IsNullOrWhiteSpace($Wheelhouse)) {
        $arguments += @("--wheelhouse", $Wheelhouse)
    }
    & $Python.Source @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime lock validation failed"
    }
} finally {
    if ($null -eq $oldPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $oldPythonPath
    }
}
