# Safe Beta Windows Runtime Distribution Implementation Plan

## Stage 1: Runtime contract and locks

- [ ] Finalize runtime/manifest schemas and platform ID.
- [ ] Pin and hash CPython 3.12 embeddable, SAM3 code/assets, cu128 wheels, all
      transitive runtime wheels, and offline prerequisite inputs.
- [ ] Separate runtime/build/test requirements and generate legal provenance.
- [ ] Build a probe runtime and run the complete import/native-DLL matrix.
- [ ] Measure compressed/uncompressed size, disk peak, build time, WebView2/VC
      needs, and release-channel fit.
- [ ] Stop for planning review if measurements require a different delivery
      shape; do not weaken the full-runtime contract.

## Stage 2: Runtime assembly and resolver

- [ ] Implement acquisition verification and disconnected assembly.
- [ ] Configure isolated CPython paths and copy backend/vendor/resources/legal.
- [ ] Replace divergent packaging filters with one manifest-aware implementation.
- [ ] Run isolated imports and composed-backend smoke from staging.
- [ ] Generate and independently verify the complete runtime manifest.
- [ ] Add separate Rust development/release resolvers using Tauri resources.
- [ ] Remove release fallback to system Python and repo layouts.
- [ ] Add missing/corrupt/version-mismatch resolver tests.

## Stage 3: Setup, Portable, and smoke

- [ ] Build one immutable desktop payload from the verified runtime.
- [ ] Configure offline-capable WebView2 and validated VC/UCRT handling.
- [ ] Produce Portable and Setup from the same payload/digest.
- [ ] Make all missing/corrupt/weight/version checks fail before publish output.
- [ ] Remove placeholder archive behavior and atomically promote artifacts.
- [ ] Add redacted desktop `--self-test` through production startup/shutdown.
- [ ] Add artifact-only clean Windows positive and negative smoke jobs.
- [ ] Require upstream runtime/security/data tests and artifact smoke before
      GitHub release publishing.

## Integration validation

```powershell
python -m pytest tests -q
npm --prefix apps/desktop run build
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --check
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets --locked -- -D warnings
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Packaging validation additionally runs acquisition/hash verification, offline
assembly, manifest verification, weight scan, Setup/Portable construction,
artifact-only self-test, install/uninstall, and negative corruption cases.

## Risky files and ownership

- Dependency/source lock files and runtime schema: nested child 1.
- `scripts/build-runtime.ps1` plus packaging helpers: nested child 2.
- `apps/desktop/src-tauri/src/sidecar.rs` and Tauri resource configuration:
  nested child 2 after runtime-integration changes land.
- `scripts/build-desktop.ps1` and release workflow: nested child 3.
- Writable data and security source files remain owned by their upstream tasks;
  packaging consumes their outputs and tests.

## Rollback points

- Never regenerate locks during a release build.
- Never generate a manifest before import/application smoke passes.
- Never promote artifact staging before positive and negative checks pass.
- Never treat a placeholder, online setup instruction, or system-Python fallback
  as a Beta artifact.

## Pre-start gate

- [ ] Start a nested child, not this coordinator.
- [ ] The nested child's explicit dependencies are complete.
- [ ] Its PRD/design/implement and context manifests pass validation.
- [ ] Latest planning summary remains user-approved.
