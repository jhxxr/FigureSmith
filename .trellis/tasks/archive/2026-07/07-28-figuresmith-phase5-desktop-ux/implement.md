# Implement: Phase 5 Desktop UX

## Pre-flight

- [x] Phase 4 committed `e37ec65`
- [ ] Inventory vendor web pages and SAM-related UI in app.js
- [ ] Confirm models API + Tauri commands still match

## Checklist

### 1. System status API

- [ ] `figuresmith/api/system_routes.py` extend with `GET /api/system/status`
- [ ] `POST /api/system/onboarding` optional
- [ ] GPU/CUDA probe safe without torch/GPU
- [ ] Tests `tests/test_system_status.py`

### 2. Log redaction helper

- [ ] `figuresmith/security/redact.py`
- [ ] Unit tests
- [ ] Wire into event streaming if low-cost; else use in any new log UI path

### 3. New UI pages (static)

- [ ] `welcome.html` (+ css/js) 欢迎与向导
- [ ] `models.html` 模型管理卡片
- [ ] Mount from main.py (StaticFiles or routes)
- [ ] Desktop detect → invoke Tauri imports

### 4. Brand + SAM convergence on vendor web

- [ ] index/import/history/canvas/guide: brand FigureSmith
- [ ] Remove/hide fal/roboflow SAM options; force local
- [ ] Remove HF_TOKEN UI if present
- [ ] Update i18n strings in app.js (FIGURESMITH markers)
- [ ] Favicon/brand image not upstream product logo

### 5. Create/run UX polish

- [ ] Pipeline step labels 本地化
- [ ] Model-missing errors surface link to models page
- [ ] Strict offline base URL hint

### 6. History + SVG

- [ ] History page brand + ensure artifacts open
- [ ] Canvas/svg-edit path still resolves
- [ ] Clear export / open folder affordances if missing

### 7. Docs / version

- [ ] docs/phase5-delivery.md
- [ ] development.md, README, CHANGELOG
- [ ] figuresmith version 0.5.0

## Validation

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
```

Manual desktop:
```powershell
./scripts/run-desktop.ps1
# welcome → models import → create page has no fal/roboflow
```

## Review Gates

1. No Roboflow/fal as selectable SAM backend in formal UI
2. No HF_TOKEN field in desktop UI
3. Brand FigureSmith everywhere user-facing in patched pages
4. system/status never throws on missing CUDA
5. Python tests green
6. Token/auth still intact

## Defaults

- Incremental vendor web patch + new static pages (not full React rewrite)
- API keys: do not add new plaintext settings.json key storage in this phase
- Onboarding skippable
