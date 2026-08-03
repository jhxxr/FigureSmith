# Phase 6 Delivery — Windows packaging

**Date:** 2026-07-28  
**Product:** FigureSmith / 图匠  
**Version:** 0.6.3 (see root `VERSION`)<br>
**Task:** `.trellis/tasks/07-28-figuresmith-phase6-windows-packaging`

## Packaging baseline

Ship **packaging scripts and release documentation** for Windows x86_64. Runtime
V1 uses these tools to publish a self-contained CPU runtime:

| Artifact intent | Script |
|-----------------|--------|
| Setup / portable desktop | `scripts/build-desktop.ps1` → `dist-desktop/` |
| CPU Runtime V1 Pack | `scripts/build-runtime.ps1` → `dist-runtime/` |
| SHA-256 list | `scripts/write-checksums.ps1` |
| CI draft | `.github/workflows/release-windows.yml` |

**Model weights are never packaged.** `runtime-manifest.json` sets
`contains_weights: false`. Copy filters exclude `*.pt` / `*.safetensors` / etc.

## Commands

The build machine needs x64 CPython 3.12 and the archive helper:

```powershell
python -m pip install zstandard
```

This tooling prerequisite is not shipped to or required on the target machine.

```powershell
# Acquire and assemble the CPU Runtime V1 pack
python scripts/runtime/fetch_wheelhouse.py --variant cpu --lock-root locks --out build/wheelhouse-cpu
python scripts/runtime/assemble_runtime.py --variant cpu --lock-root locks --cache build/source-cache --fetch-sources
./scripts/build-runtime.ps1 -Variant cpu -Wheelhouse build/wheelhouse-cpu

# Desktop: full tauri build (needs Rust/Node) or repackage only
./scripts/build-desktop.ps1
./scripts/build-desktop.ps1 -SkipBuild

# Checksums only
./scripts/write-checksums.ps1 -Path dist-runtime
```

## Layout

- `FigureSmith-Runtime-Windows-CPU-<version>/`
  - embedded `python/` with CPython 3.12 and resolved CPU site-packages
  - `app/backend`, `app/vendor/*`, `app/resources` (filtered application source)
  - `locks/` with the exact consumed CPU inputs and generated requirements
  - `runtime-manifest.json` and licenses
  - no loose wheels, SAM3/RMBG model weights, caches, or user data
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
- The published Runtime Pack vendors CPython and the CPU runtime stack. On first launch it does not create a venv, invoke pip, or require system Python.
- Model weights remain external and are imported through the Models page.
- The pack and desktop build fail if model weights, caches, or loose wheels are present.
- The cu128 lock and manual assembly path remain available but are not published by the release workflow.
- `build-desktop.ps1` fails when the Tauri executable is missing; it never emits
  a source-only Portable placeholder.
- Code signing not configured (optional future hook)
- GitHub Actions publishes only successful tag builds; manual dispatch is a packaging trial and never publishes

## Related docs

- `docs/release.md` — release checklist
- `docs/phase5-delivery.md` — UX baseline this pack ships
