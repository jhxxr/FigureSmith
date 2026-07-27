# Phase 1 Delivery — FigureSmith repository scaffold

**Date:** 2026-07-27  
**Product:** FigureSmith / 图匠  
**Task:** `.trellis/tasks/07-27-figuresmith-phase1-repo-scaffold`

## Goal achieved

Imported AutoFigure-Edit as a tracked vendor baseline, established the FigureSmith monorepo boundary, compliance/branding docs, Windows dev scripts, and minimal tests — **without** rewriting SAM3/RMBG inference or adding model weights.

## Startup commands

```powershell
cd G:\0JHX-code\Project\FigureSmith

# One-time (or when deps change)
./scripts/setup-dev.ps1
copy .env.example .env   # optional provider keys

# Run backend (127.0.0.1:8765)
./scripts/run-backend.ps1

# Smoke tests
$env:PYTHONPATH = "apps\backend"
python -m pytest tests -q
python -c "import figuresmith; print(figuresmith.__version__)"
```

Expected health endpoint: `http://127.0.0.1:8765/healthz`

**Bind policy:** backend defaults to **127.0.0.1 only** (see `apps/backend/main.py`, `scripts/run-backend.ps1`, `docs/development.md`).

## File / directory inventory

### Root

| Path | Notes |
|------|-------|
| `LICENSE` | FigureSmith MIT |
| `NOTICE.md` | Attribution + independence |
| `THIRD_PARTY_NOTICES.md` | Third-party inventory |
| `CHANGELOG.md` | Phase 1 entry 2026-07-27 |
| `README.md` / `README_ZH.md` | Branding + ResearAI independence disclaimer |
| `.gitignore` | venv, outputs, weights, `.env`, IDE/OS junk |
| `.env.example` | OpenAI-compatible placeholders; HF not primary path |
| `.git/` | Repository initialized |

### Vendor

| Path | Notes |
|------|-------|
| `vendor/autofigure_edit/` | Upstream snapshot (core py, server, web, docs, docker, releases, img without `case/`) |
| `vendor/autofigure_edit/UPSTREAM.md` | Source path, 2026-07-27, preserve-as-baseline |
| `vendor/svg_edit/` | Boundary copy of svg-edit |
| `vendor/svg_edit/UPSTREAM.md` | Dual-copy policy |
| `vendor/autofigure_edit/web/vendor/svg-edit/` | Runtime path retained for relative URLs |

### Apps

| Path | Notes |
|------|-------|
| `apps/desktop/README.md` | Tauri placeholder |
| `apps/backend/figuresmith/` | Package `__version__ = "0.1.0"` |
| `apps/backend/figuresmith/{api,pipeline,models,runtime,security}/` | Subpackages + docstrings |
| `apps/backend/figuresmith/pipeline/vendor_bridge.py` | Vendor root helpers |
| `apps/backend/main.py` | Import vendor `server:app`, bind 127.0.0.1 |
| `apps/backend/requirements.txt` | Based on upstream; SAM3 separate; pytest included |
| `apps/backend/pyproject.toml` | name `figuresmith`, `requires-python >=3.10,<3.13` |

### Resources / scripts / docs / tests

| Path | Notes |
|------|-------|
| `resources/model-manifest.json` | Empty schema shell for Phase 2 |
| `resources/licenses/.gitkeep` | Placeholder |
| `resources/notices/.gitkeep` | Placeholder |
| `scripts/setup-dev.ps1` | venv + pip install requirements |
| `scripts/run-backend.ps1` | loopback backend launcher |
| `scripts/build-runtime.ps1` | Phase 2+ stub (exits 1) |
| `scripts/build-desktop.ps1` | Phase 4 stub (exits 1) |
| `scripts/verify-offline.ps1` | Phase 2+ stub (exits 1) |
| `docs/development.md` | Dev guide |
| `docs/licenses.md` | License map |
| `docs/phase1-delivery.md` | This file |
| `tests/test_package_import.py` | Import + vendor bridge |
| `tests/test_repo_layout.py` | Required paths, disclaimer, no weights |

### Intentionally untouched tool dirs

- `.trellis/`, `.claude/`, `.agents/`, `.codex/`, `.opencode/`

## Deviations / notes vs implement plan

1. **`img/case/` not copied** (~95MB gallery). Documented in `vendor/autofigure_edit/UPSTREAM.md`. Not required to start the server.
2. **Python requirement:** `pyproject.toml` uses `>=3.10,<3.13` for practical scaffold work, with an explicit note that the overall plan prefers 3.12.
3. **Vendor business code** left unchanged aside from adding `UPSTREAM.md` (and dual-copy of svg-edit outside the runtime tree).
4. Upstream vendor `server.py` still contains its own `__main__` path that can bind `0.0.0.0`; **FigureSmith entrypoints** (`main.py` / `run-backend.ps1`) force/default **127.0.0.1**.
5. **Check-phase hardening:** `vendor_bridge` resolves the monorepo root via directory markers (not only fixed `parents[N]`), and `pyproject.toml` declares `py-modules = ["main"]` so the `figuresmith-backend` console script remains importable if the backend package is installed.

## Known limitations (Phase 1)

- No claim of offline segmentation.
- No local `checkpoint_path` / `local_files_only` rewrites yet (Phase 2).
- No Tauri UI (Phase 4).
- No runtime pack / installer.
- No model weights in git; SAM3 install is manual/optional.
- Full ML dependency install (torch, etc.) is heavy and machine-specific; smoke tests only need `figuresmith` import + pytest (fastapi not required for layout tests).
- Token auth and hardened security controls are later phases.
- Optional cloud SAM paths remain in vendor baseline for traceability.

## Phase 2 handoff points (not implemented here)

- `vendor/autofigure_edit/autofigure2.py` — `segment_with_sam3` / RMBG loader behavior
- `apps/backend/figuresmith/models/`
- `apps/backend/figuresmith/runtime/`
- `apps/backend/figuresmith/security/`
- `resources/model-manifest.json` (fill real entries)
- `scripts/verify-offline.ps1` / `build-runtime.ps1`

## Validation checklist

- [x] Directory skeleton present
- [x] Vendor core files present + UPSTREAM docs
- [x] Compliance + bilingual README independence statement
- [x] `figuresmith` importable with version
- [x] Layout tests cover required paths and weight absence
- [x] No SAM3/RMBG inference rewrite in vendor
- [x] Backend documented/defaulted to 127.0.0.1

## Independence statement (canonical)

> FigureSmith is an independent open-source project based on AutoFigure-Edit. It is not affiliated with or endorsed by ResearAI.
