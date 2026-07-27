# Development guide — FigureSmith (Phase 2)

## Prerequisites

- Windows 10/11 (primary target for scripts)
- Python **3.10+** (prefer **3.12** for GPU/SAM3 work)
- Git
- Optional: CUDA GPU + installed `sam3` package + local checkpoints for real segmentation

## Repository map

| Path | Role |
|------|------|
| `apps/backend/figuresmith/` | FigureSmith-owned package (security, models, runtime, pipeline) |
| `apps/backend/main.py` | Dev entry: strict offline + vendor FastAPI |
| `apps/desktop/` | Tauri placeholder (Phase 4) |
| `vendor/autofigure_edit/` | Upstream baseline + **minimal FIGURESMITH patches** |
| `vendor/svg_edit/` | Boundary copy of svg-edit static assets |
| `resources/` | Model manifest skeleton, licenses, notices (**no weights**) |
| `scripts/` | setup-dev, run-backend, verify-offline |
| `docs/` | Developer and compliance docs |
| `tests/` | Layout + Phase 2 offline/model contract tests |

## Setup

```powershell
cd G:\0JHX-code\Project\FigureSmith
./scripts/setup-dev.ps1
copy .env.example .env
```

Notes:

- Setup does **not** download model weights.
- SAM3 package install is optional and separate.
- Desktop path does **not** require `HF_TOKEN`.

## Local model paths

Resolution order: **CLI > env > settings.json > default app-data layout**.

| Env var | Meaning |
|---------|---------|
| `FIGURESMITH_STRICT_OFFLINE` | Default `1` for launcher; blocks remote SAM + HF fallback |
| `FIGURESMITH_SAM3_CHECKPOINT` | Path to local `sam3.pt` (or equivalent) |
| `FIGURESMITH_SAM3_BPE` | Optional BPE vocab path |
| `FIGURESMITH_RMBG_MODEL_PATH` | Local RMBG-2.0 directory (`config.json`, weights, …) |
| `FIGURESMITH_DATA_DIR` | Override app data root |

Default Windows layout:

```text
%LOCALAPPDATA%\FigureSmith\
  settings.json
  models\
    sam3\sam3.pt
    rmbg-2.0\   # Transformers snapshot dir
```

Dev settings (optional): `.figuresmith/settings.json` — see `resources/model-manifest.json` example.

**Server policy:** HTTP clients cannot force arbitrary host filesystem model paths. Only env/registry paths are injected into job subprocesses.

## Run backend (loopback + strict offline)

```powershell
./scripts/run-backend.ps1
```

Defaults:

- Host: `127.0.0.1`
- Port: `8765`
- `FIGURESMITH_STRICT_OFFLINE=1`
- Health: `http://127.0.0.1:8765/healthz`

Disable strict offline for experimental cloud/HF workflows (not recommended for desktop):

```powershell
$env:FIGURESMITH_STRICT_OFFLINE = "0"
.\.venv\Scripts\python.exe apps\backend\main.py --no-strict-offline
```

## Tests

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
.\.venv\Scripts\python.exe -m pytest tests -q
./scripts/verify-offline.ps1
```

All Phase 2 contract tests pass **without GPU and without weight files**.

## Vendor policy

- Prefer logic in `apps/backend/figuresmith/`.
- Vendor edits must stay **minimal** and marked with `FIGURESMITH-BEGIN` / `FIGURESMITH-END`.
- Do not reintroduce silent HF / fal / roboflow fallback on the FigureSmith strict path.
- See `vendor/autofigure_edit/UPSTREAM.md` and `docs/phase2-delivery.md`.

## Scripts

| Script | Status |
|--------|--------|
| `scripts/setup-dev.ps1` | Dev venv + deps |
| `scripts/run-backend.ps1` | Loopback backend, strict offline default |
| `scripts/verify-offline.ps1` | Phase 2 offline contract tests |
| `scripts/build-runtime.ps1` | Phase 6 placeholder |
| `scripts/build-desktop.ps1` | Phase 4 placeholder |

## Branding

Product name: **FigureSmith / 图匠**.  
Do not present AutoFigure-Edit as the FigureSmith product name, package name, or primary logo.
