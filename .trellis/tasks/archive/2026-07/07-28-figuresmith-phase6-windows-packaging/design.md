# Design: Phase 6 Windows Packaging

## Overview

```text
build-desktop.ps1
  → npm/tauri build
  → copy bundle → dist-desktop/FigureSmith-Setup-x64-<ver>.exe (or msi)
  → zip portable → dist-desktop/FigureSmith-Portable-x64-<ver>.zip
  → checksums

build-runtime.ps1
  → create dist-runtime/FigureSmith-Runtime-Windows-NVIDIA-<tag>/
  → embed/copy apps/backend + vendor (no weights)
  → python embed or document external python
  → requirements-runtime.txt + install-runtime.ps1
  → README-RUNTIME.md
  → checksums
```

## Desktop artifacts

Prefer Tauri 2 bundle outputs under `apps/desktop/src-tauri/target/release/bundle/`.

Rename/copy to:

| Artifact | Name pattern |
|----------|----------------|
| Installer | `FigureSmith-Setup-x64-<version>.exe` |
| Portable | `FigureSmith-Portable-x64-<version>.zip` |

Version from `apps/desktop/src-tauri/tauri.conf.json` / pyproject / single `VERSION` file.

## Runtime Pack layout

```text
FigureSmith-Runtime-Windows-NVIDIA-cu128/
  README-RUNTIME.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  python/                    # optional embed; or use system + venv
  site-packages/ or .venv/   # if built online
  app/
    backend/                 # figuresmith + main.py
    vendor/autofigure_edit/  # needed modules only if possible
  scripts/
    install-deps.ps1
    run-backend.ps1
  requirements-runtime.txt
  MANIFEST.json              # version, cuda tag, excludes weights: true
```

**Hard exclude globs:** `*.pt`, `*.safetensors`, `*.onnx`, `models/**` weight dirs.

## Checksums

```powershell
Get-FileHash -Algorithm SHA256 dist-desktop/* | ...
→ dist-desktop/checksums.txt
```

## CI

`.github/workflows/release-windows.yml` (draft):

- on tag `v*`
- setup node/rust/python
- run build-desktop (may need longer runners)
- upload artifacts
- **never** cache user model dirs

If CI too heavy for free runners, keep workflow as `workflow_dispatch` manual.

## Security / compliance

- Installer display name FigureSmith
- Include notices
- README: source license ≠ model weight license
- No HF token baked in

## Testing

- Unit: packaging path exclude filter tests (pure python)
- Script dry-run mode: `-WhatIf` / `-SkipTauriBuild` to validate folder assembly without full compile
- Full tauri build optional on agent machine

## Risks

| Risk | Mitigation |
|------|------------|
| CUDA wheel size / network | document offline fetch; don't commit wheels |
| tauri build time/timeouts | scripts + skip flags; local manual build |
| Signing | optional hook |
