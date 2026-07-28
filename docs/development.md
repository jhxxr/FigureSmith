# Development guide — FigureSmith (Phase 4)

## Prerequisites

- Windows 10/11 (primary target for scripts)
- Python **3.10+** (prefer **3.12** for GPU/SAM3 work)
- Git
- Optional desktop: **Rust** (`cargo`), **Node.js 20+**, **WebView2**
- Optional: CUDA GPU + installed `sam3` package + local checkpoints for real segmentation

## Repository map

| Path | Role |
|------|------|
| `apps/backend/figuresmith/` | FigureSmith-owned package (security, models, runtime, pipeline, api) |
| `apps/backend/main.py` | Dev entry: strict offline + vendor FastAPI + `/api/models` + auth/shutdown |
| `apps/desktop/` | Tauri 2 desktop shell (Phase 4) |
| `vendor/autofigure_edit/` | Upstream baseline + **minimal FIGURESMITH patches** |
| `vendor/svg_edit/` | Boundary copy of svg-edit static assets |
| `resources/` | Model manifest (pins optional), licenses, notices (**no weights**) |
| `scripts/` | setup-dev, run-backend, run-desktop, import-model, build-desktop |
| `docs/` | Developer and compliance docs |
| `tests/` | Layout + offline/model/import/auth contract tests |

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
- Desktop also needs Rust + Node (see `apps/desktop/README.md`).

## Local model paths

Resolution order: **CLI > env > settings.json > default app-data layout**.

| Env var | Meaning |
|---------|---------|
| `FIGURESMITH_STRICT_OFFLINE` | Default `1` for launcher; blocks remote SAM + HF fallback |
| `FIGURESMITH_SAM3_CHECKPOINT` | Path to local `sam3.pt` (or equivalent) |
| `FIGURESMITH_SAM3_BPE` | Optional BPE vocab path |
| `FIGURESMITH_RMBG_MODEL_PATH` | Local RMBG-2.0 directory (`config.json`, weights, …) |
| `FIGURESMITH_DATA_DIR` | Override app data root |
| `FIGURESMITH_ALLOW_UNPINNED_MODELS` | Dev: allow imports that do not match official pins |
| `FIGURESMITH_SAM3_MIN_BYTES` | Override SAM3 minimum size gate (tests/dev) |
| `FIGURESMITH_SESSION_TOKEN` | Desktop Bearer token (set by Tauri; never commit) |
| `FIGURESMITH_DISABLE_AUTH` | `1` disables Bearer checks (tests / legacy browser) |
| `FIGURESMITH_PYTHON` | Python used by desktop sidecar |

Default Windows layout:

```text
%LOCALAPPDATA%\FigureSmith\
  settings.json
  models\
    sam3\sam3.pt
    rmbg-2.0\   # Transformers snapshot dir
```

Dev settings (optional): `.figuresmith/settings.json` — see `resources/model-manifest.json` example.

**Server policy:** HTTP job clients cannot force arbitrary host filesystem model paths for runs. Model **import** APIs accept only absolute local `source_path` values (for desktop picker handoff); they copy into app data.

## Import models (Phase 3 + desktop Phase 4)

### CLI

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"

python -m figuresmith.models.cli import-sam3 --source C:\weights\sam3.pt
python -m figuresmith.models.cli import-rmbg --source C:\weights\RMBG-2.0 --kind dir
python -m figuresmith.models.cli list
```

Or: `./scripts/import-model.ps1 -Sam3 C:\weights\sam3.pt`

### HTTP (loopback backend)

```powershell
./scripts/run-backend.ps1
# POST http://127.0.0.1:8765/api/models/sam3/import
# {"source_path":"C:/weights/sam3.pt"}
```

### Desktop native pickers

```powershell
./scripts/run-desktop.ps1
# Menu: Models → Import SAM3 Checkpoint… / Import RMBG ZIP… / Import RMBG Folder…
```

Failed imports use staging + trash restore and **do not** overwrite a previously verified pack.

RMBG ZIP extraction enforces Zip Slip guards. Manifest pin mismatches are rejected unless `FIGURESMITH_ALLOW_UNPINNED_MODELS=1`.

See [docs/phase3-delivery.md](./phase3-delivery.md) and [docs/phase4-delivery.md](./phase4-delivery.md).

## Run backend (loopback + strict offline)

```powershell
./scripts/run-backend.ps1
```

Defaults:

- Host: `127.0.0.1`
- Port: `8765`
- `FIGURESMITH_STRICT_OFFLINE=1`
- Health: `http://127.0.0.1:8765/healthz`
- Models: `http://127.0.0.1:8765/api/models`
- Shutdown: `POST /api/shutdown` (Bearer required when token auth is on)

Disable strict offline for experimental cloud/HF workflows (not recommended for desktop):

```powershell
$env:FIGURESMITH_STRICT_OFFLINE = "0"
.\.venv\Scripts\python.exe apps\backend\main.py --no-strict-offline
```

## Run desktop (Phase 4)

```powershell
./scripts/run-desktop.ps1
```

Requires Rust + Node + WebView2. The shell allocates a free loopback port, spawns Python with a random session token and strict offline env, waits for `/healthz`, loads the vendor UI, and on quit calls shutdown + process-tree kill if needed.

## Session auth notes

| Mode | Behavior |
|------|----------|
| No `FIGURESMITH_SESSION_TOKEN` | Auth off (browser `run-backend.ps1` default) |
| Token set | `/api/*` requires `Authorization: Bearer …`; `/healthz` public |
| `FIGURESMITH_DISABLE_AUTH=1` | Bypass (pytest default via `tests/conftest.py`) |

**Never** log or commit the session token.

## Tests

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
.\.venv\Scripts\python.exe -m pytest tests -q
./scripts/verify-offline.ps1
```

All Phase 2/3/4 contract tests pass **without GPU and without multi-GB weight files**.

Desktop compile check:

```powershell
cd apps/desktop
npm install
cd src-tauri
cargo check
```

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
| `scripts/run-desktop.ps1` | Tauri dev + sidecar (Phase 4) |
| `scripts/verify-offline.ps1` | Offline/model contract tests |
| `scripts/import-model.ps1` | Phase 3 CLI wrapper for SAM3/RMBG import |
| `scripts/build-runtime.ps1` | Phase 6 placeholder |
| `scripts/build-desktop.ps1` | Phase 4 Tauri build |

## Branding

Product name: **FigureSmith / 图匠**.  
Do not present AutoFigure-Edit as the FigureSmith product name, package name, or primary logo.
