# FigureSmith Phase 3 — import local model packs via CLI
param(
    [string]$Sam3 = "",
    [string]$Rmbg = "",
    [ValidateSet("auto", "zip", "dir")]
    [string]$RmbgKind = "auto",
    [string]$DataDir = "",
    [int]$Sam3MinBytes = -1,
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
if ($DataDir) {
    $env:FIGURESMITH_DATA_DIR = $DataDir
}

function Invoke-ModelCli {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)
    $all = @("-m", "figuresmith.models.cli")
    if ($DataDir) {
        $all += @("--data-dir", $DataDir)
    }
    $all += $CliArgs
    & $Python @all
    return $LASTEXITCODE
}

if ($ListOnly -or (-not $Sam3 -and -not $Rmbg)) {
    exit (Invoke-ModelCli list)
}

if ($Sam3) {
    $samArgs = @("import-sam3", "--source", $Sam3)
    if ($Sam3MinBytes -ge 0) {
        $samArgs += @("--min-bytes", "$Sam3MinBytes")
    }
    $code = Invoke-ModelCli @samArgs
    if ($code -ne 0) { exit $code }
}

if ($Rmbg) {
    $code = Invoke-ModelCli @("import-rmbg", "--source", $Rmbg, "--kind", $RmbgKind)
    if ($code -ne 0) { exit $code }
}

exit (Invoke-ModelCli list)
