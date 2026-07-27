# FigureSmith — verify offline mode (Phase 2 control-flow checks)
#
# Runs pure-Python offline / model-path contract tests without requiring GPU
# or model weights. Exit 0 on success.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = Join-Path $RepoRoot ".venv\bin\python"
}
if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
}

$Backend = Join-Path $RepoRoot "apps\backend"
$Vendor = Join-Path $RepoRoot "vendor\autofigure_edit"
$env:PYTHONPATH = "$Backend;$Vendor"

Write-Host "=== FigureSmith verify-offline (Phase 2) ===" -ForegroundColor Cyan
Write-Host "Python     : $Python"
Write-Host "PYTHONPATH : $env:PYTHONPATH"
Write-Host ""

& $Python -m pytest tests/test_offline_endpoint.py tests/test_model_paths.py `
    tests/test_sam3_local_load_contract.py tests/test_rmbg_local_load_contract.py `
    tests/test_strict_offline_no_remote_fallback.py -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Offline contract tests FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Offline contract tests passed (no GPU/weights required)." -ForegroundColor Green
exit 0
