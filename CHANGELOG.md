# Changelog

All notable changes to FigureSmith are documented in this file.

## [0.1.0] — 2026-07-27

### Phase 1 — Repository scaffold

- Initialize independent **FigureSmith / 图匠** monorepo skeleton.
- Import AutoFigure-Edit baseline into `vendor/autofigure_edit/` (preserve-as-baseline; no SAM3/RMBG logic rewrite).
- Dual-copy svg-edit assets to `vendor/svg_edit/` while keeping runtime path under vendor web.
- Add FigureSmith package boundary `apps/backend/figuresmith/` with thin `pipeline/vendor_bridge.py`.
- Add development entry `apps/backend/main.py` that runs vendor FastAPI on **127.0.0.1:8765**.
- Add Windows scripts: `setup-dev.ps1`, `run-backend.ps1`, plus Phase 2/4 placeholders.
- Add compliance docs: `LICENSE`, `NOTICE.md`, `THIRD_PARTY_NOTICES.md`, `docs/licenses.md`.
- Add bilingual README with independence disclaimer (not affiliated with ResearAI).
- Add Phase 1 smoke tests for package import and repository layout.
- Exclude model weights from the repository via `.gitignore` and policy docs.

### Known non-goals in this release

- No offline-guaranteed local SAM3/RMBG loading.
- No Tauri desktop app.
- No runtime pack / installer.
- No model weights distributed in git.
