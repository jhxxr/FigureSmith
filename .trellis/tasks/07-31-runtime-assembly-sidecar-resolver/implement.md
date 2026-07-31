# Runtime Assembly and Sidecar Resolver Implementation Plan

- [ ] Add acquisition/cache verification and offline-mode test controls.
- [ ] Implement empty-stage CPython/package/SAM3/app/legal assembly.
- [ ] Configure isolated `_pth` and scrub Python/environment influence.
- [ ] Consolidate application copy/exclusion logic under one structured helper.
- [x] Add manifest-aware no-weight/no-cache validation.
- [ ] Run isolated import and production app-factory smoke from staging.
- [x] Generate and independently verify the full runtime manifest.
- [ ] Refactor Rust into explicit development/release resolver implementations.
- [x] Resolve release paths through Tauri Resource and validate identity/files.
- [ ] Add hostile PATH/current-dir and missing/corrupt/version tests.
- [ ] Run two clean offline assemblies and compare manifests.

## Validation

Run lock validators, offline assembly/import/app smoke, runtime manifest and
weight scans, resolver unit/integration tests, then full Python/frontend/Rust
checks. No network socket may open during assembly or runtime smoke.

## Risky areas

- Existing PowerShell/Python packaging filters and weight false positives.
- Native DLL lookup under CPython embeddable isolation.
- Tauri Resource paths across development test, raw exe, and bundle staging.
- Overlap with sidecar/data files from upstream children; rebase on their tested
  contracts rather than restoring old path heuristics.

Do not create desktop archives in this task; hand only a verified Runtime
Directory and resolver contract to the final nested child.
