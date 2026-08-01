# Writable Application Data Implementation Plan

## Ordered checklist

### 1. Characterize resolution

- [ ] Add tests for writable adjacent, read-only adjacent, explicit invalid,
      LocalAppData failure, release mode, and explicit development mode.
- [x] Strengthen the write/replace/delete probe and stable errors.
- [x] Introduce immutable `AppPaths` and resolve it once during the production
      launcher startup.

### 2. Integrate backend paths

- [x] Put `AppPaths` in the composed application state/lifespan.
- [x] Pass the canonical root to model/settings/onboarding/system routes and
      bind vendor mutable roots to the verified layout.
- [x] Move uploads, outputs, job temp, logs, and SVG-cache roots under it;
      generation children inherit the same root and scratch directory.
- [x] Add resolved containment and probe-cleanup assertions for the managed
      subtrees.

### 3. Integrate desktop startup

- [x] Stop forcing adjacent data as `FIGURESMITH_DATA_DIR`.
- [x] Pass explicit install root and release/development mode.
- [x] Return resolved public paths in authenticated readiness metadata.
- [x] Make native open-directory behavior consume readiness metadata.
- [x] Surface startup failures through the existing local splash error path;
      backend uses stable `DATA_DIR_NOT_WRITABLE` text.

### 4. Atomic writes and compatibility

- [x] Centralize temp-and-replace for settings/small metadata.
- [x] Keep staging on the data volume and clean interrupted temp files.
- [x] Preserve root `settings.json` and explicit override/CLI compatibility.
- [x] Preserve existing external model directories as valid import sources.

### 5. Cross-layer validation

- [ ] Run the complete onboarding/import/upload/generation/history workflow with
      a read-only install tree and temporary LocalAppData.
- [ ] Snapshot the install/runtime tree before and after; assert no mutation.
- [ ] Repeat Portable against a writable adjacent data root.
- [ ] Cover spaces, non-ASCII paths, and Windows reparse/sibling escapes.
- [ ] Run full Python, frontend, and Rust regression checks.

## Validation commands

```powershell
python -m pytest tests -q
npm --prefix apps/desktop run build
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

The packaged runtime child adds clean-artifact Setup/Portable variants of the
same assertions after this contract lands.

## Risky files

- `apps/backend/figuresmith/models/paths.py`: authoritative resolution.
- Backend app factory/state: one-time `AppPaths` construction.
- Model/settings/system route helpers: duplicated resolution removal.
- `vendor/autofigure_edit/server.py`: source-relative mutable globals.
- `apps/desktop/src-tauri/src/sidecar.rs` and `commands.rs`: launch metadata and
  native directory behavior.

Do not overlap with security-child edits to vendor artifact routes without
rebasing on its sanitizer/output contract.

## Rollback points

- Land resolver/probe tests before moving vendor paths.
- Move one mutable subtree at a time while retaining one authoritative root.
- Do not delete or auto-copy existing model data during rollback.
- Do not restore an ignored writability result or production repo fallback.

## Pre-start checks

- [ ] Runtime-integration readiness metadata interface is stable.
- [ ] Security child output/cache requirements are accounted for.
- [ ] Context manifests contain the parent audit and this technical research.
- [ ] Task validation and latest planning approval remain valid.

## Evidence (2026-08-01)

- `tests/test_model_paths.py` covers writable adjacent/install fallback,
  explicit unwritable override, explicit development mode, canonical layout,
  atomic probe cleanup, and stable `DATA_DIR_NOT_WRITABLE`.
- `tests/test_production_app_composition.py` verifies readiness `models_dir`,
  vendor APP/JOBS/TEMP/LOGS/SVG cache roots, and out-of-root override rejection.
- Production startup resolves `AppPaths` before importing vendor `server.py`;
  generation children run from the data-root temp directory with `TMP*` and
  path envs bound to that root.
- Validation: Python `251 passed`, desktop Vite build, Rust `cargo clippy
  --all-targets -D warnings`, Rust tests (`6 passed`), bridge Node tests (`3
  passed`), `compileall`, `git diff --check`, and Trellis context validation.

The clean-install Setup/Portable workflow and a real Tauri/WebView cold-start
trace remain release-gate work for the next task phase.
