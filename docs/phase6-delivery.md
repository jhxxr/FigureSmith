# Phase 6 Delivery — Windows packaging

**Date:** 2026-07-28  
**Product:** FigureSmith / 图匠  
**Version:** 0.6.0 (see root `VERSION`)  
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

### dist-runtime/FigureSmith-Runtime-Windows-NVIDIA-cu128-0.6.0/

- `app/backend`, `app/vendor/*`, `app/resources` (filtered)
- `requirements-runtime.txt`, `scripts/install-deps.ps1`, `scripts/run-backend.ps1`
- `README-RUNTIME.md`, `MANIFEST.json`, licenses
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
- Runtime Pack currently remains a dependency-install pack; it does **not** vendor
  the isolated CPython/locked CUDA wheelhouse required by the standalone desktop
  runtime. The release resolver rejects this incomplete pack.
- `build-desktop.ps1` fails when the Tauri executable is missing; it never emits
  a source-only Portable placeholder.
- Code signing not configured (optional future hook)
- GitHub Actions workflow is `workflow_dispatch` draft (may need larger runners for tauri)

## Related docs

- `docs/release.md` — release checklist
- `docs/phase5-delivery.md` — UX baseline this pack ships
