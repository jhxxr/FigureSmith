# Changelog

All notable changes to FigureSmith are documented in this file.

## [0.2.0] — 2026-07-27

### Phase 2 — Local SAM3/RMBG loading & strict offline

- Add `figuresmith.security.offline` with `apply_strict_offline_env` and spoof-resistant `validate_offline_endpoint`.
- Add model path registry/resolvers, bilingual error codes (`SAM3_MODEL_MISSING`, `RMBG_MODEL_MISSING`, `REMOTE_SAM_DISABLED`, …).
- Add pure helpers `sam3_loader` / `rmbg_loader` enforcing `load_from_HF=False` and `local_files_only=True`.
- Patch vendor `autofigure2.py` for explicit local SAM3 checkpoint loading and strict no-remote SAM.
- Patch vendor RMBG path to use `local_files_only=True` and block HF download under strict offline.
- Extend CLI with `--sam_checkpoint_path`, `--sam_bpe_path`, `--strict_offline`.
- Extend `RunRequest` with `strict_offline`; server injects model paths from env/registry only (no client path trust).
- FigureSmith launcher / `run-backend.ps1` default `FIGURESMITH_STRICT_OFFLINE=1`.
- Fill `resources/model-manifest.json` with sam3 + rmbg-2.0 skeleton entries.
- Add offline/model contract unit tests (no GPU/weights required).
- Document delivery in `docs/phase2-delivery.md`.

### Known non-goals in this release

- No model import wizard / ZIP UI (Phase 3).
- No Tauri desktop app (Phase 4).
- No runtime pack / installer (Phase 6).
- No model weights distributed in git.

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
