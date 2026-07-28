# Phase 5 Delivery — Desktop UX

**Date:** 2026-07-28  
**Product:** FigureSmith / 图匠  
**Version:** 0.5.0  
**Task:** `.trellis/tasks/07-28-figuresmith-phase5-desktop-ux`

## Goal achieved

Deliver everyday desktop UX on top of the Phase 4 Tauri sidecar:

- Welcome page + skippable first-run wizard with persisted onboarding flag
- `GET /api/system/status` hardware/model probe (never crashes without CUDA)
- Models management page wired to Phase 3 APIs / Tauri import commands
- Vendor create/import/history/canvas/guide branded as **FigureSmith**
- SAM fixed to **Local SAM3** in formal UI (no fal/Roboflow selectable options, no HF_TOKEN field)
- Log redaction helpers for secrets and home paths

## Startup

```powershell
cd G:\0JHX-code\Project\FigureSmith
./scripts/setup-dev.ps1
./scripts/run-backend.ps1
# open http://127.0.0.1:8765/welcome.html
# models: http://127.0.0.1:8765/models.html

# Desktop
./scripts/run-desktop.ps1
```

## Key paths

| Path | Role |
|------|------|
| `apps/backend/figuresmith/api/system_routes.py` | `/api/system/status`, `/api/system/onboarding`, shutdown |
| `apps/backend/figuresmith/security/redact.py` | Log/UI redaction |
| `apps/backend/figuresmith/static/ui/` | welcome/models pages + assets |
| `apps/backend/main.py` | Mounts UI ahead of vendor static |
| `vendor/autofigure_edit/web/*` | Brand + local-SAM patches (FIGURESMITH markers) |
| `tests/test_system_status.py` | Status/onboarding API |
| `tests/test_redact.py` | Redaction unit tests |
| `tests/test_ui_branding_contract.py` | UI contract (local SAM, brand) |

## API

- `GET /api/system/status` — platform, GPU/CUDA probe, model install flags, onboarding, bilingual gpu_missing messages
- `POST /api/system/onboarding` — `{ "completed": true|false }`
- Existing `/api/models/*` used by models page

## UX policy

- Formal SAM backend: **local only** (`forceLocalSamBackend` in `app.js`)
- Remote fal/Roboflow are not selectable in create/import HTML
- No HF_TOKEN field on create/import pages
- Guide copy updated to direct users to Models page for missing weights

## Validation

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
```

## Known limitations

- Not a full React redesign; incremental vendor web + static pages
- API keys may still sit in sessionStorage from legacy vendor flows (not newly written to settings.json)
- Full GUI E2E (wizard click-through on Tauri) is manual
- Official model pins may still be null (Phase 3 policy)
- Installer / runtime pack remain Phase 6

## Phase 6 handoff

- Windows installer + runtime pack + checksums
- Stronghold / credential manager for provider API keys
- Optional deeper vendor UI de-AutoFigure residual strings in less-used paths
