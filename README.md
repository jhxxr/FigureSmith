# FigureSmith / 图匠

Local-first scientific figure generation, segmentation, vectorization, and SVG editing.

**FigureSmith is an independent open-source project based on AutoFigure-Edit. It is not affiliated with or endorsed by ResearAI.**

> Chinese README: [README_ZH.md](./README_ZH.md)

## Status (Phase 2)

Phase 2 delivers **local model loading contracts** and **strict offline defaults**:

- Vendored AutoFigure-Edit baseline under `vendor/` with minimal FigureSmith patches
- Local SAM3 load requires explicit checkpoint (`load_from_HF=False`)
- Local RMBG load uses `local_files_only=True` (no HF fallback under strict mode)
- FigureSmith package helpers for offline endpoint validation and model path registry
- Windows setup / run / verify-offline scripts
- Contract tests that pass **without GPU or weight files**

**Not yet:** model import wizard (Phase 3), Tauri shell (Phase 4), runtime pack/installer, or shipping model weights.

### Local model environment variables

| Variable | Purpose |
|----------|---------|
| `FIGURESMITH_STRICT_OFFLINE` | Default `1` — block remote SAM + HF download fallbacks |
| `FIGURESMITH_SAM3_CHECKPOINT` | Path to local SAM3 `.pt` checkpoint |
| `FIGURESMITH_SAM3_BPE` | Optional BPE vocab path |
| `FIGURESMITH_RMBG_MODEL_PATH` | Path to local RMBG-2.0 model directory |
| `FIGURESMITH_DATA_DIR` | Optional app-data root override |

See [docs/phase2-delivery.md](./docs/phase2-delivery.md) and [docs/development.md](./docs/development.md).

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
# 1) Setup venv + backend deps
./scripts/setup-dev.ps1

# 2) Optional: configure OpenAI-compatible keys
copy .env.example .env

# 3) Run backend (loopback only)
./scripts/run-backend.ps1
```

Then open:

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
│   └── desktop/           # Tauri placeholder (Phase 4)
├── vendor/
│   ├── autofigure_edit/   # AutoFigure-Edit baseline
│   └── svg_edit/          # svg-edit boundary copy
├── resources/             # model-manifest shell, licenses, notices
├── scripts/               # setup-dev, run-backend, future build/verify stubs
├── docs/                  # development, licenses, phase1 delivery
└── tests/                 # smoke tests
```

## Development docs

- [docs/development.md](./docs/development.md) — setup, run, model paths, tests
- [docs/phase2-delivery.md](./docs/phase2-delivery.md) — Phase 2 file list, commands, limits
- [docs/phase1-delivery.md](./docs/phase1-delivery.md) — Phase 1 file list and limits
- [docs/licenses.md](./docs/licenses.md) — license map
- [CHANGELOG.md](./CHANGELOG.md)

## Tests

```powershell
$env:PYTHONPATH = "apps\backend"
python -m pytest tests -q
python -c "import figuresmith; print(figuresmith.__version__)"
```

## Phase roadmap (high level)

| Phase | Focus |
|-------|--------|
| 1 | Repo scaffold, vendor import, branding, compliance, dev entry |
| 2 (this) | Local SAM3/RMBG loading, strict offline, model path registry |
| 3+ | Model import UI, hardening, security, packaging preparation |
| 4 | Tauri desktop shell |

## Citation / upstream

If you use the underlying AutoFigure methods, please also follow citation guidance in:

- `vendor/autofigure_edit/CITATION.cff`
- `vendor/autofigure_edit/CITATION_AND_ATTRIBUTION.md`

## License

- FigureSmith code: MIT — see [LICENSE](./LICENSE)
- Vendored AutoFigure-Edit: MIT — see `vendor/autofigure_edit/LICENSE`
- Third-party notes: [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)
