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
| **Rust** | `rustup` + `cargo` (MSVC toolchain on Windows; development/build only) |
| **Node.js** | 20+ with `npm` (development/build only) |
| **WebView2** | Preinstalled on modern Windows 11; bootstrapper used if missing |
| **Runtime V1** | Releases provide MSI/Setup installers plus a separate verified CPU Runtime V1 archive to place beside `FigureSmith.exe` |

Optional env:

| Variable | Purpose |
|----------|---------|
| `FIGURESMITH_PYTHON` | Development-only explicit Python override; ignored by release Runtime V1 resolution |
| `FIGURESMITH_REPO_ROOT` | Development-only monorepo root override |
| `FIGURESMITH_DATA_DIR` | Explicit writable app-data root forwarded to the sidecar |
| `FIGURESMITH_DEV_MODE` | Explicit source-development mode; release never falls back to repository/system Python |

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

Release MSI/Setup artifacts contain the desktop shell and fail closed until a
verified schema-2 CPU Runtime V1 companion from the separate Runtime archive is
installed beside `FigureSmith.exe`. That archive contains embedded CPython 3.12,
hash-locked site-packages, and native DLLs. No target-machine pip, venv creation,
system Python, or online dependency installation is used. Model weights remain
external and are imported through the Models page. The cu128 lock is retained for
manual maintainer builds, but is not part of the published release.

## Tauri commands

| Command | Role |
|---------|------|
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

- **Sidecar startup failure**: confirm that the verified CPU `runtime` companion is beside `FigureSmith.exe`; release mode never falls back to system Python.
- **Model environment incomplete**: the editor can still open; import the required model weights through the Models page.
- **Sidecar health timeout**: verify the Runtime V1 manifest and checksum before retrying.
- **Auth 401 in browser-only mode**: browser dev should use `./scripts/run-backend.ps1` without a session token, or set `FIGURESMITH_DISABLE_AUTH=1` (tests only).
- **Orphan Python after crash**: startup and exit paths own a cleanup guard and use `taskkill /T` as a final fallback.
