# FigureSmith Desktop (Tauri 2)

Phase 4 desktop shell for **FigureSmith / 图匠**.

The Tauri process:

1. Finds a free TCP port on `127.0.0.1`
2. Spawns `apps/backend/main.py` as a Python **sidecar**
3. Passes a one-time `FIGURESMITH_SESSION_TOKEN` (memory/env only)
4. Waits for `GET /healthz`
5. Loads the vendor Web UI from the sidecar
6. On exit: `POST /api/shutdown`, then force-kills the process tree if needed

## Prerequisites

| Tool | Notes |
|------|--------|
| **Rust** | `rustup` + `cargo` (MSVC toolchain on Windows) |
| **Node.js** | 20+ with `npm` |
| **WebView2** | Preinstalled on modern Windows 11; bootstrapper used if missing |
| **Python** | Project venv via `./scripts/setup-dev.ps1` |

Optional env:

| Variable | Purpose |
|----------|---------|
| `FIGURESMITH_PYTHON` | Absolute path to Python interpreter for the sidecar |
| `FIGURESMITH_REPO_ROOT` | Override monorepo root detection |
| `FIGURESMITH_DATA_DIR` | App data root (forwarded to sidecar) |

## Develop

From repo root (recommended):

```powershell
./scripts/setup-dev.ps1   # once
./scripts/run-desktop.ps1
```

Or from this directory:

```powershell
npm install
npm run tauri -- dev
```

## Build

```powershell
./scripts/build-desktop.ps1
# or: npm run tauri -- build
```

Release packaging / runtime pack polish is **Phase 6**. Model weights are **never** bundled.

## Tauri commands

| Command | Role |
|---------|------|
| `get_session` | `{ port, api_base, token, ready }` (token not persisted) |
| `import_sam3_model` | Native file picker → `POST /api/models/sam3/import` |
| `import_rmbg_archive` | ZIP picker → RMBG import |
| `import_rmbg_folder` | Folder picker → RMBG import |
| `open_models_directory` | Shell-open models dir from `/api/models/paths` |

Menu: **Models → Import SAM3 / RMBG…**

## Security notes

- Sidecar bind host is hard-coded to **`127.0.0.1`** (never `0.0.0.0`).
- Session token is random 32 bytes hex; only in child env + Tauri memory.
- Token is **not** written to disk, logs, or `localStorage`.
- `/healthz` is public; all `/api/*` require `Authorization: Bearer` when token is set.
- Child always gets `FIGURESMITH_STRICT_OFFLINE=1` and HF offline flags.

## Icons

Placeholder solid-color icons under `src-tauri/icons/` (not the upstream AutoFigure-Edit logo).

## Troubleshooting

- **Sidecar health timeout**: ensure `./scripts/setup-dev.ps1` succeeded and `python apps/backend/main.py` works alone.
- **Auth 401 in browser-only mode**: browser dev should use `./scripts/run-backend.ps1` without a session token, or set `FIGURESMITH_DISABLE_AUTH=1` (tests only).
- **Orphan Python after crash**: Task Manager → end `python.exe` for FigureSmith; exit path uses `taskkill /T` as fallback.
