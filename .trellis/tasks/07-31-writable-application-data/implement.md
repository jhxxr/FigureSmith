# Writable Application Data Implementation Plan

## Ordered checklist

### 1. Characterize resolution

- [ ] Add tests for writable adjacent, read-only adjacent, explicit invalid,
      LocalAppData failure, release mode, and explicit development mode.
- [ ] Strengthen the write/replace/delete probe and stable errors.
- [ ] Introduce immutable `AppPaths` and resolve it once during app startup.

### 2. Integrate backend paths

- [ ] Put `AppPaths` in the composed application state/lifespan.
- [ ] Pass it to model, settings, onboarding, system, and vendor routes.
- [ ] Move uploads, outputs, history/job temp, logs, and SVG cache under it.
- [ ] Add resolved containment and cleanup assertions for every subtree.

### 3. Integrate desktop startup

- [ ] Stop forcing adjacent data as `FIGURESMITH_DATA_DIR`.
- [ ] Pass explicit install root and release/development mode.
- [ ] Return resolved public paths in authenticated readiness metadata.
- [ ] Make native open-directory behavior consume readiness metadata.
- [ ] Surface `DATA_DIR_NOT_WRITABLE` on the local splash.

### 4. Atomic writes and compatibility

- [ ] Centralize temp-and-replace for settings/small metadata.
- [ ] Keep staging on the data volume and clean interrupted temp files.
- [ ] Preserve root `settings.json` and explicit override/CLI compatibility.
- [ ] Prove existing external model directories remain valid import sources.

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
