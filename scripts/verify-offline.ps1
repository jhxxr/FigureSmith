# FigureSmith — verify offline mode (PLACEHOLDER)
#
# Phase: Phase 2+ — not implemented in Phase 1
#
# Intended future responsibilities:
# - Confirm local SAM3/RMBG loads with local_files_only / no HF fallback
# - Fail closed when weights are missing
# - Optional network isolation smoke checks
#
# Phase 1: documents the future gate only.

$ErrorActionPreference = "Stop"

Write-Host "verify-offline.ps1 is a Phase 1 placeholder." -ForegroundColor Yellow
Write-Host "Strict offline verification requires Phase 2 local model loading work."
Write-Host "Phase 1 does NOT claim offline segmentation capability."
Write-Host "Handoff: figuresmith/models/, figuresmith/runtime/, vendor autofigure2 loaders"
exit 1
