# FigureSmith Desktop (Tauri 2)

Phase 4 desktop shell for **FigureSmith / 图匠**.

The Tauri process:

1. Finds a free TCP port on `127.0.0.1`
2. Spawns `apps/backend/main.py` as a Python **sidecar**
3. Passes a one-time `FIGURESMITH_SESSION_TOKEN` (memory/env only)
4. Waits for authenticated `GET /api/desktop/ready`
5. Registers a port-specific Tauri capability and loads the vendor Web UI in a remote `main` window
6. On exit: `POST /api/shutdown`, then force-kills the process tree if needed

## Prerequisites

| Tool | Notes |
|------|--------|
| **Rust** | `rustup` + `cargo` (MSVC toolchain on Windows) |
| **Node.js** | 20+ with `npm` |
| **WebView2** | Preinstalled on modern Windows 11; bootstrapper used if missing |
| **Python base** | User-installed Python 3.10-3.12; desktop scans available installations and uses one only to create the isolated FigureSmith environment |
| **Managed environment** | `%LOCALAPPDATA%\FigureSmith\python-env` by default; bootstrap packages are installed here, never into the base Python |

Optional env:

| Variable | Purpose |
|----------|---------|
| `FIGURESMITH_PYTHON` | Optional absolute path to the base Python used to create the isolated environment |
| `FIGURESMITH_MANAGED_PYTHON_DIR` | Optional isolated environment directory; defaults to `%LOCALAPPDATA%\FigureSmith\python-env` |
| `FIGURESMITH_REPO_ROOT` | Override monorepo root detection |
| `FIGURESMITH_DATA_DIR` | Explicit app data root (forwarded to sidecar; must be writable) |
| `FIGURESMITH_DEV_MODE` | Explicit source-development mode; repository data is never inferred in release mode |

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

Release packaging includes application code and dependency guidance only. It does not bundle Python, pip, PyTorch, CUDA, SAM3, or model weights. On first launch the desktop selects a supported user-installed Python as a base, creates a dedicated environment under LocalAppData, and installs only the bootstrap service packages there. Model packages remain optional and are reported in the welcome page.

## Tauri commands

| Command | Role |
|---------|------|
| `prepare_managed_python_environment` | One-click creation/repair of the isolated user environment, then restart |
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

- **Sidecar startup failure**: use the splash action to create/repair the isolated environment. It uses a supported base Python but does not install into that base.
- **Model environment incomplete**: the editor can still open; install the reported Torch/torchvision/SAM3 packages into the isolated environment before running local inference.
- **Sidecar health timeout**: ensure a supported base Python is installed and the bootstrap requirements can be reached by the isolated environment setup.
- **Auth 401 in browser-only mode**: browser dev should use `./scripts/run-backend.ps1` without a session token, or set `FIGURESMITH_DISABLE_AUTH=1` (tests only).
- **Orphan Python after crash**: startup and exit paths own a cleanup guard and use `taskkill /T` as a final fallback.
