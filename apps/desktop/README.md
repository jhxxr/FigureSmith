# FigureSmith Desktop (placeholder)

This directory is reserved for the **Tauri** desktop shell (Phase 4).

## Phase 1 status

- No Tauri project is scaffolded yet.
- Local development uses the Python backend + vendor web UI:

  ```powershell
  ./scripts/run-backend.ps1
  ```

  Then open `http://127.0.0.1:8765/`.

## Planned later

- Tauri app packaging under this tree
- Localhost-only backend lifecycle managed by the desktop process
- Installer / runtime pack integration (see `scripts/build-desktop.ps1`)

Do not treat this folder as a runnable desktop product until Phase 4.
