# FigureSmith — build runtime pack (PLACEHOLDER)
#
# Phase: planned for Phase 2 / packaging phases (not implemented in Phase 1)
#
# Intended future responsibilities:
# - Assemble a Runtime Pack with Python runtime + wheels + model pack layout
# - Exclude secrets and never embed gated weights without explicit user import
# - Produce a verifiable directory for offline desktop use
#
# Phase 1: no-op with guidance only.

$ErrorActionPreference = "Stop"

Write-Host "build-runtime.ps1 is a Phase 1 placeholder." -ForegroundColor Yellow
Write-Host "Runtime pack building is not implemented yet."
Write-Host "See docs/phase1-delivery.md and the overall multi-phase plan."
Write-Host "Handoff targets: apps/backend/figuresmith/runtime/, resources/model-manifest.json"
exit 1
