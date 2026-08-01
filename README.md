# FigureSmith / 图匠

Local-first scientific figure generation, segmentation, vectorization, and SVG editing.

**FigureSmith is an independent open-source project based on AutoFigure-Edit. It is not affiliated with or endorsed by ResearAI.**

> Chinese README: [README_ZH.md](./README_ZH.md)

## Status (Phase 6)

Phase 6 adds **Windows packaging tooling** on top of the Phase 5 desktop UX:

- `./scripts/build-runtime.ps1` — application-only Windows Runtime Pack (no Python, CUDA, dependency wheels, or model weights)
- `./scripts/build-desktop.ps1` — Setup/Portable outputs under `dist-desktop/`
- `./scripts/write-checksums.ps1` — SHA-256 `checksums.txt`
- Release docs: [docs/phase6-delivery.md](./docs/phase6-delivery.md), [docs/release.md](./docs/release.md)

The desktop shell scans available Python 3.10-3.12 installations, uses one only as a base, and creates a dedicated FigureSmith environment under the user's LocalAppData. Bootstrap packages are installed only into that isolated environment; PyTorch, CUDA, SAM3, and model weights are never installed automatically.

Also includes welcome/models UX, local-only SAM UI, Tauri sidecar on **127.0.0.1**, and session token auth.

**Not shipped in git/releases:** Python runtimes, dependency wheels, model weights
(`sam3.pt`, RMBG safetensors, etc.). The first desktop launch creates a per-user
isolated environment and installs `requirements-bootstrap.txt` there. Use the
reported isolated-Python command with `requirements-models.txt` only when local
inference is needed.

### Local model environment variables

| Variable | Purpose |
|----------|---------|
| `FIGURESMITH_STRICT_OFFLINE` | Default `1` — block remote SAM + HF download fallbacks |
| `FIGURESMITH_SAM3_CHECKPOINT` | Path to local SAM3 `.pt` checkpoint |
| `FIGURESMITH_SAM3_BPE` | Optional BPE vocab path |
| `FIGURESMITH_RMBG_MODEL_PATH` | Path to local RMBG-2.0 model directory |
| `FIGURESMITH_DATA_DIR` | Explicit app data root (models/settings/uploads/outputs). It must pass a writable create/flush/replace/delete probe; otherwise startup fails with `DATA_DIR_NOT_WRITABLE`. |
| `FIGURESMITH_DEV_MODE` | Set to `1` only for source development to allow repository `data/`; release/portable mode uses adjacent `data/` then LocalAppData fallback. |
| `FIGURESMITH_ALLOW_UNPINNED_MODELS` | Dev: allow imports that do not match official pins |
| `FIGURESMITH_SESSION_TOKEN` | Desktop sidecar Bearer token (set by Tauri; do not commit) |
| `FIGURESMITH_DISABLE_AUTH` | Test/dev bypass for auth middleware (`1` = off) |
| `FIGURESMITH_PYTHON` | Optional explicit base Python executable; the desktop creates its isolated environment from it without modifying it |
| `FIGURESMITH_MANAGED_PYTHON_DIR` | Optional override for the isolated environment directory; default is `%LOCALAPPDATA%\FigureSmith\python-env` |
See [docs/development.md](./docs/development.md).

## Relationship to AutoFigure-Edit

FigureSmith builds on [AutoFigure-Edit](vendor/autofigure_edit/) (MIT, Copyright 2026 Autofigure2 contributors; paper arXiv:2603.06674).

| Item | FigureSmith policy |
|------|-------------------|
| Product name | **FigureSmith / 图匠** (not AutoFigure-Edit) |
| Package name | `figuresmith` |
| Upstream code | Tracked under `vendor/autofigure_edit/` as a baseline snapshot |
| Logo | Do not use upstream AutoFigure-Edit / ResearAI logos as FigureSmith product logo |

See `NOTICE.md`, `THIRD_PARTY_NOTICES.md`, and `docs/licenses.md`.

## Important license note

**Source code license ≠ third-party model weight licenses.**

This repository does **not** include SAM3/RMBG (or other) model weights. Review each weight provider’s terms before any redistribution or commercial packaging.

## Quick start (Windows development)

```powershell
# 1) Setup venv + FigureSmith service packages
./scripts/setup-dev.ps1

# 2) Optional: configure OpenAI-compatible keys
copy .env.example .env

# 3a) Backend only (browser)
./scripts/run-backend.ps1

# 3b) Desktop shell (Tauri + sidecar) — requires Rust + Node + WebView2
./scripts/run-desktop.ps1
```

Then open (backend-only):

- UI: http://127.0.0.1:8765/
- Health: http://127.0.0.1:8765/healthz

### Backend bind policy

The development backend is intended for **local desktop use** and defaults to:

- Host: **`127.0.0.1` only**
- Port: `8765`

Do not expose the service on public interfaces for normal use.

## Repository layout

```text
FigureSmith/
├── apps/
│   ├── backend/           # figuresmith package + main.py
│   └── desktop/           # Tauri 2 shell (Phase 4)
├── vendor/
│   ├── autofigure_edit/   # AutoFigure-Edit baseline
│   └── svg_edit/          # svg-edit boundary copy
├── resources/             # model-manifest shell, licenses, notices
├── scripts/               # setup-dev, run-backend, run-desktop, build-desktop
├── docs/                  # development, licenses, phase delivery notes
└── tests/                 # contract + auth tests
```

## Development docs

- [docs/development.md](./docs/development.md) — setup, run, model paths, import, tests
- [docs/phase4-delivery.md](./docs/phase4-delivery.md) — Phase 4 Tauri + sidecar delivery
- [docs/phase3-delivery.md](./docs/phase3-delivery.md) — Phase 3 model manager delivery
- [apps/desktop/README.md](./apps/desktop/README.md) — desktop prerequisites
- [docs/phase2-delivery.md](./docs/phase2-delivery.md) — Phase 2 file list, commands, limits
- [docs/phase1-delivery.md](./docs/phase1-delivery.md) — Phase 1 file list and limits
- [docs/licenses.md](./docs/licenses.md) — license map
- [CHANGELOG.md](./CHANGELOG.md)

## Tests

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
python -c "import figuresmith; print(figuresmith.__version__)"
```

## Phase roadmap (high level)

| Phase | Focus |
|-------|--------|
| 1 | Repo scaffold, vendor import, branding, compliance, dev entry |
| 2 | Local SAM3/RMBG loading, strict offline, model path registry |
| 3 (this) | Model import/verify/delete, checksums, pin policy, rollback |
| 4 | Tauri desktop shell + native file picker |
| 6 | Runtime pack / installer |

## Citation / upstream

If you use the underlying AutoFigure methods, please also follow citation guidance in:

- `vendor/autofigure_edit/CITATION.cff`
- `vendor/autofigure_edit/CITATION_AND_ATTRIBUTION.md`

## License

- FigureSmith code: MIT — see [LICENSE](./LICENSE)
- Vendored AutoFigure-Edit: MIT — see `vendor/autofigure_edit/LICENSE`
- Third-party notes: [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)
