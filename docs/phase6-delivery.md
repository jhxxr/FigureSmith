# Phase 6 Delivery — Windows packaging

**Date:** 2026-07-28  
**Product:** FigureSmith / 图匠  
**Version:** 0.6.2 (see root `VERSION`)<br>
**Task:** `.trellis/tasks/07-28-figuresmith-phase6-windows-packaging`

## Packaging baseline

Ship **packaging scripts and release documentation** for Windows x86_64:

| Artifact intent | Script |
|-----------------|--------|
| Setup / portable desktop | `scripts/build-desktop.ps1` → `dist-desktop/` |
| Runtime Pack (no weights) | `scripts/build-runtime.ps1` → `dist-runtime/` |
| SHA-256 list | `scripts/write-checksums.ps1` |
| CI draft | `.github/workflows/release-windows.yml` |

**Model weights are never packaged.** `MANIFEST.json` sets `contains_weights: false`. Copy filters exclude `*.pt` / `*.safetensors` / etc.

## Commands

```powershell
# Runtime pack (safe, no huge CUDA download required for skeleton)
./scripts/build-runtime.ps1

# Desktop: full tauri build (needs Rust/Node) or repackage only
./scripts/build-desktop.ps1
./scripts/build-desktop.ps1 -SkipBuild

# Checksums only
./scripts/write-checksums.ps1 -Path dist-runtime
```

## Layout

- `FigureSmith-Runtime-Windows-<version>/`
  - `app/backend`, `app/vendor/*`, `app/resources` (filtered application source)
  - `requirements-runtime.txt`, `requirements-bootstrap.txt`, `requirements-models.txt`
  - `app/backend/figuresmith/runtime/dependencies.json`
  - `README-RUNTIME.md`, `MANIFEST.json`, `runtime-manifest.json`, licenses
  - no Python interpreter, dependency wheels, CUDA runtime, SAM3 source, model weights, caches, or user data
- Optional `.zip` + `checksums.txt`

### dist-desktop/

- `FigureSmith-Setup-x64-<ver>.exe` (when tauri bundle exists)
- `FigureSmith-Portable-x64-<ver>.zip`
- `checksums.txt`

## Safety

- Python helper: `figuresmith.runtime.packaging` + `tests/test_packaging_excludes.py`
- build-runtime **errors** if any weight-like file is found in the pack tree
- `dist-desktop/` and `dist-runtime/` are gitignored

## Known limitations

- Full NSIS/MSVC installer binary requires a successful `tauri build` on the builder machine
- The Runtime Pack deliberately does not vendor Python or the ML stack. On first launch the desktop selects a supported user-installed Python 3.10-3.12 only as a base, creates `%LOCALAPPDATA%\FigureSmith\python-env`, and installs bootstrap packages into that isolated environment. The base Python remains unchanged.
- `requirements-runtime.txt` is the combined user-environment guidance; model packages remain optional and are installed into the isolated environment only when local inference is needed.
- The welcome page exposes the isolated environment path, missing model packages, copyable commands, and visual model import/verification progress.
- The pack and desktop build fail if model weights, caches, wheels, Python executables, or dependency DLLs are present.
- `build-desktop.ps1` fails when the Tauri executable is missing; it never emits
  a source-only Portable placeholder.
- Code signing not configured (optional future hook)
- GitHub Actions publishes only successful tag builds; manual dispatch is a packaging trial and never publishes

## Related docs

- `docs/release.md` — release checklist
- `docs/phase5-delivery.md` — UX baseline this pack ships
