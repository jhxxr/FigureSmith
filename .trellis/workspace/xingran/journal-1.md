# Journal - xingran (Part 1)

> AI development session journal
> Started: 2026-07-27

---



## Session 1: FigureSmith Phase 1 scaffold

**Date**: 2026-07-27
**Task**: FigureSmith Phase 1 scaffold
**Branch**: `master`

### Summary

Completed Phase 1: imported AutoFigure-Edit into vendor/, created figuresmith package boundary, loopback backend launcher, compliance docs, Windows scripts, 46 smoke tests. Commit ac9e9f9. Ready for Phase 2 local SAM3/RMBG offline loading.

### Git Commits

| Hash | Message |
|------|---------|
| `ac9e9f9` | (see git log) |

### Status

[OK] **Completed**


## Session 2: FigureSmith Phase 2 local models

**Date**: 2026-07-27
**Task**: FigureSmith Phase 2 local models
**Branch**: `master`

### Summary

Phase 2: local SAM3 checkpoint + load_from_HF=False, RMBG local_files_only, strict offline env/endpoint validation, registry paths, 122 tests. Fixed gitignore models/ package exclusion. Commit b5a5d6c.

### Git Commits

| Hash | Message |
|------|---------|
| `b5a5d6c` | (see git log) |

### Status

[OK] **Completed**


## Session 3: FigureSmith Phase 3 model manager

**Date**: 2026-07-27
**Task**: FigureSmith Phase 3 model manager
**Branch**: `master`

### Summary

Phase 3: SAM3/RMBG import manager with staging/atomic promote, Zip Slip+bomb guards, pin policy, API/CLI, 164 tests. Commit 858245a. Ready for Phase 4 Tauri desktop shell.

### Git Commits

| Hash | Message |
|------|---------|
| `858245a` | (see git log) |

### Status

[OK] **Completed**


## Session 4: FigureSmith Phase 4 Tauri sidecar

**Date**: 2026-07-28
**Task**: FigureSmith Phase 4 Tauri sidecar
**Branch**: `master`

### Summary

Phase 4: Tauri 2 desktop shell, loopback Python sidecar, Bearer session token auth, native model import commands, shutdown cleanup. 186 tests. Commit e37ec65. Next: Phase 5 desktop UX.

### Git Commits

| Hash | Message |
|------|---------|
| `e37ec65` | (see git log) |

### Status

[OK] **Completed**


## Session 5: FigureSmith Phase 5 desktop UX

**Date**: 2026-07-28
**Task**: FigureSmith Phase 5 desktop UX
**Branch**: `master`

### Summary

Phase 5: welcome wizard, models page, system status API, log redaction, FigureSmith brand + local-only SAM UI. 203 tests. Commit a5a4454. Ready for Phase 6 Windows packaging.

### Git Commits

| Hash | Message |
|------|---------|
| `a5a4454` | (see git log) |

### Status

[OK] **Completed**


## Session 6: FigureSmith Phase 6 Windows packaging

**Date**: 2026-07-28
**Task**: FigureSmith Phase 6 Windows packaging
**Branch**: `master`

### Summary

Phase 6 complete: Runtime Pack + desktop dist scripts, weight exclusion, checksums, release docs, CI draft. VERSION 0.6.0. 212 tests. Full FigureSmith phases 1-6 delivered.

### Git Commits

| Hash | Message |
|------|---------|
| `13e5776` | (see git log) |

### Status

[OK] **Completed**


## Session 7: FigureSmith GitHub Actions packaging

**Date**: 2026-07-28
**Task**: FigureSmith GitHub Actions packaging
**Branch**: `master`

### Summary

Phase 6 CI: added assert-no-weights.ps1, sync-version.ps1, extract-changelog.ps1, ci.yml, release-windows.yml. Tag v* now auto-builds and releases. 212 tests passed.

### Git Commits

| Hash | Message |
|------|---------|
| `63df3aa` | (see git log) |

### Status

[OK] **Completed**


## Session 8: Complete CPU-only Runtime V1 release channel

**Date**: 2026-08-03
**Task**: Complete CPU-only Runtime V1 release channel
**Branch**: `master`

### Summary

Selected and implemented the CPU-only Windows Runtime V1 release channel. CI validates both lock bundles but acquires/builds/uploads only CPU; cu128 remains a deterministic maintainer/manual path and split-large-assets stays unwired by decision. Updated schema-2 workflow contracts, docs, changelog, runtime spec, and measurements. Added a CPython 3.12 build-interpreter guard with zstandard documentation. Verified 315 Python tests, Rust 12 tests, frontend build, YAML/PowerShell parsing, lock validation, and an embedded clean-runner health/ready/system/shutdown smoke with no surviving process.

### Git Commits

| Hash | Message |
|------|---------|
| `ecc4ab8` | (see git log) |

### Status

[OK] **Completed**


## Session 9: Publish CPU Runtime and MSI Setup Release

**Date**: 2026-08-03
**Task**: Publish CPU Runtime and MSI Setup Release
**Branch**: `master`

### Summary

Fixed the desktop packaging lifecycle, removed Portable packaging per user request, updated release workflow/docs/contracts to publish only CPU Runtime plus MSI and Setup EXE, and verified GitHub Actions run 30810339787 created the public v0.6.4 Release with six non-Portable assets.

### Git Commits

| Hash | Message |
|------|---------|
| `b514eb7` | (see git log) |
| `cd31001` | (see git log) |

### Status

[OK] **Completed**
