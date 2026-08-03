# Phase 4 delivery — Tauri desktop shell + Python sidecar

## Goal

Ship a **runnable Windows desktop process lifecycle** for FigureSmith:

- Tauri 2 shell under `apps/desktop/`
- Local Python sidecar bound to **`127.0.0.1` only**
- One-time **session token** Bearer auth on `/api/*`, installed before remote
  page code runs
- Native file pickers for Phase 3 model import APIs
- Clean exit (shutdown endpoint + process-tree kill)

The first-run wizard and hardware pages are delivered in Phase 5. Runtime-pack
tooling is delivered in Phase 6; clean-machine packaged startup remains a
release-hardening gate.

## What was delivered

### Python backend

| Item | Path / detail |
|------|----------------|
| Session auth middleware | `apps/backend/figuresmith/security/auth.py` |
| Shutdown route | `POST /api/shutdown` via `figuresmith/api/system_routes.py` |
| Desktop fetch bridge | Rust document-start bridge; `/figuresmith-bridge.js` is a no-token browser compatibility loader |
| Entrypoint wiring | `apps/backend/main.py` mounts routes + middleware |
| Test bypass | `FIGURESMITH_DISABLE_AUTH=1` (default in `tests/conftest.py`) |
| Auth / shutdown tests | `tests/test_auth_middleware.py`, `tests/test_shutdown.py` |

Auth policy:

- Enabled when `FIGURESMITH_SESSION_TOKEN` is set **and** `FIGURESMITH_DISABLE_AUTH` is not truthy
- `/healthz` public
- `/api/*` requires `Authorization: Bearer <token>`
- `/api/events/*` also accepts scoped query `fs_token` / `token` (browser `EventSource` cannot set headers; desktop bridge only)
- Token is never printed by launcher logs (only “token mode” / length); never written to disk / localStorage

### Tauri desktop (`apps/desktop/`)

| Item | Detail |
|------|--------|
| Product | **FigureSmith** (`app.figuresmith.desktop`) |
| Sidecar | Free port on 127.0.0.1 → spawn `main.py --host 127.0.0.1 --port <p>` |
| Env to child | `FIGURESMITH_SESSION_TOKEN`, `FIGURESMITH_STRICT_OFFLINE=1`, HF offline flags, `PYTHONPATH` |
| Commands | `import_sam3_model`, `import_rmbg_archive`, `import_rmbg_folder`, `open_models_directory` (session is Rust-private) |
| Remote capability | Dynamic exact `http://127.0.0.1:<port>/*` grant for `main`; unrelated origins and new windows denied |
| Exit | `POST /api/shutdown` then wait ~3s then `taskkill /F /T` on Windows |
| Icons | Placeholder teal PNGs/ICO (not upstream logo) |

### Scripts / docs

| Item | Detail |
|------|--------|
| `scripts/run-desktop.ps1` | Dev launch (`npm run tauri -- dev`) |
| `scripts/build-desktop.ps1` | Release build entry |
| `apps/desktop/README.md` | Prerequisites + security notes |
| This file | Delivery record |
| `CHANGELOG.md` | 0.6.0 |

## Build prerequisites (Windows x86_64)

1. Python 3.10+ and `./scripts/setup-dev.ps1`
2. Rust (`rustup` + MSVC) — verified with cargo 1.96 in this delivery environment
3. Node.js 20+ / npm
4. WebView2 runtime

If Rust/Node are missing on a machine, the scaffold still lives in git; build simply cannot run until tools are installed.

## How to run

```powershell
./scripts/setup-dev.ps1
./scripts/run-desktop.ps1
```

Backend-only (browser, no token):

```powershell
./scripts/run-backend.ps1
# open http://127.0.0.1:8765/
```

## Manual GUI checklist

1. App window opens; splash then vendor UI on loopback.
2. Menu **Models → Import SAM3 Checkpoint…** opens a native file dialog.
3. With a small dummy `.pt` (or real checkpoint), import hits `/api/models/sam3/import` with Bearer token.
4. DevTools/network: `/api/*` without Authorization returns **401** when token mode is on.
5. Quit the app; confirm no leftover `python.exe` for FigureSmith (Task Manager / `Get-Process python`).
6. Confirm bind is loopback only (sidecar args always `--host 127.0.0.1`).

## Exit cleanup verification

Implemented:

1. `POST /api/shutdown` (token required in desktop mode) schedules `os._exit` after response flush.
2. Tauri `Exit` / window close calls `SidecarState::shutdown`.
3. If the child is still alive after ~3s, Windows `taskkill /F /T /PID <pid>` kills the tree.

Manual check after quit:

```powershell
Get-Process python -ErrorAction SilentlyContinue | Format-Table Id,Path
```

## Tests run in this delivery

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
```

Plus `cargo check` in `apps/desktop/src-tauri` and `npm install` in `apps/desktop`.

## Explicit non-goals (still later)

- Clean-machine Setup/MSI startup smoke and full Tauri artifact verification
- Graceful job cancellation and broader model/runtime supply-chain hardening
- macOS / Linux packaging commitments
- Shipping model weights

## Follow-up hardening

- First-run experience when models are missing
- Hardware / capability page
- Stronger secret storage for API keys (not session token — that stays ephemeral)
- Optional deeper vendor UI branding (FigureSmith product name in pages without claiming AutoFigure identity)
