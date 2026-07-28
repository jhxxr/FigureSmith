# Changelog

All notable changes to FigureSmith are documented in this file.

## [0.6.0] — 2026-07-28

### Phase 6 — Windows packaging & release tooling

- Add root `VERSION` and align package/desktop version to **0.6.0**.
- Implement `scripts/build-runtime.ps1` Runtime Pack (app code + deps scripts, **no weights**).
- Extend `scripts/build-desktop.ps1` to publish `dist-desktop/` Setup/Portable naming + checksums (`-SkipBuild` supported).
- Add `scripts/write-checksums.ps1` (SHA-256).
- Add `figuresmith.runtime.packaging` weight-exclusion helpers + unit tests.
- Add `docs/phase6-delivery.md`, `docs/release.md`, and draft `.github/workflows/release-windows.yml`.
- Gitignore `dist-runtime/` (and existing `dist-desktop/`).

### Known non-goals in this release

- No model weights in any artifact.
- No mandatory code signing.
- No macOS/Linux installers.
- Full Tauri installer binary still requires a local/CI `tauri build`.

## [0.5.0] — 2026-07-28

### Phase 5 — Desktop UX (wizard / models / local SAM UI)

- Add welcome page + skippable onboarding wizard (`/welcome.html`) with `POST /api/system/onboarding`.
- Add `GET /api/system/status` (GPU/CUDA probe, model flags, bilingual missing-GPU messages; never crashes without CUDA).
- Add models management page (`/models.html`) using Phase 3 APIs and Tauri import commands when available.
- Brand vendor web as **FigureSmith / 图匠**; add nav links to Welcome/Models.
- Force Local SAM3 in formal create/import UI; remove selectable fal/Roboflow SAM options and HF_TOKEN fields.
- Add log redaction helpers (`figuresmith/security/redact.py`) and UI log scrubbing in `app.js`.
- Add tests: system status, redact, UI branding contracts.
- Document delivery in `docs/phase5-delivery.md`.

### Known non-goals in this release

- No full React redesign.
- No installer / runtime pack (Phase 6).
- No model weights in git.

## [0.4.0] — 2026-07-27

### Phase 4 — Tauri desktop shell + Python sidecar

- Scaffold Tauri 2 app under `apps/desktop/` (productName **FigureSmith**, identifier `app.figuresmith.desktop`).
- Spawn Python sidecar on **127.0.0.1** with free port, `FIGURESMITH_SESSION_TOKEN`, and strict offline env.
- Add Bearer session-token middleware for `/api/*` (`figuresmith/security/auth.py`); `/healthz` remains public.
- Add `POST /api/shutdown` for graceful sidecar exit; Tauri force-kills process tree on timeout.
- Add Tauri commands: `get_session`, `import_sam3_model`, `import_rmbg_archive`, `import_rmbg_folder`, `open_models_directory`.
- Inject in-memory session + `/figuresmith-bridge.js` fetch wrapper for vendor UI API calls.
- Add `scripts/run-desktop.ps1` and implement `scripts/build-desktop.ps1` (no model weights).
- Add auth/shutdown unit tests; `FIGURESMITH_DISABLE_AUTH=1` keeps Phase 3 TestClient suites green.
- Document delivery in `docs/phase4-delivery.md`.

### Known non-goals in this release

- No full first-run wizard / hardware page polish (Phase 5).
- No runtime pack / polished installer (Phase 6).
- No macOS/Linux packaging commitment.
- No model weights distributed in git.

## [0.3.0] — 2026-07-27

### Phase 3 — Model manager (import / verify / delete / rollback)

- Add staging + atomic promote + trash restore so failed imports never destroy a working pack.
- Add SAM3 checkpoint import (`import_sam3.py`) with extension/size/SHA-256/metadata checks.
- Add RMBG ZIP/folder import (`import_rmbg.py`) with Zip Slip guards, required-file checks, and trust_remote_code warnings.
- Add manifest pin policy (`manifest.py`): mismatch rejects by default; `FIGURESMITH_ALLOW_UNPINNED_MODELS=1` allows unpinned dev imports.
- Add `ModelManager` facade and FastAPI routes under `/api/models/*` (local absolute `source_path` only; no multi-GB multipart).
- Mount model routes from `apps/backend/main.py` onto the vendor app.
- Add developer CLI: `python -m figuresmith.models.cli` and `scripts/import-model.ps1`.
- Extend `resources/model-manifest.json` with Phase 3 pin/import fields (official pins may remain null).
- Add unit tests for checksums, Zip Slip, SAM3/RMBG rollback, pin policy, and API TestClient flows (no real multi-GB weights).
- Document delivery in `docs/phase3-delivery.md`.

### Known non-goals in this release

- No Tauri native file picker / full desktop UI (Phase 4).
- No runtime pack / installer (Phase 6).
- No model weights distributed in git.
- Official release pins may still be null until weight hashing is finalized.

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
