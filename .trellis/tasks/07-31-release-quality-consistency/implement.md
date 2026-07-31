# Release Quality and Consistency Implementation Plan

- [ ] Fix Rust fmt/clippy and promote them to required checks.
- [ ] Add composed backend, frontend/type, Tauri, security, packaging, and
      artifact smoke jobs to PR/release workflows with correct dependencies.
- [ ] Add real-build packaging tests and fail-closed placeholder/weight checks.
- [ ] Implement one version parser/checker across Python/npm/Cargo/Tauri/docs/
      manifest/artifact names.
- [ ] Validate runtime/build/test locks, source hashes, licenses, SBOM, and
      checksums from the actual manifest.
- [ ] Close manual dispatch/tag/ref/version bypasses.
- [ ] Align English/Chinese READMEs, release/development docs, limitations, and
      unsigned/deferred-risk statements.
- [ ] Remove NUL/control/binary artifacts from text docs and add a CI scan.
- [ ] Record signing as a production gate without requiring a certificate in
      this task.
- [ ] Run the final release rehearsal from a clean ref and artifact digest.

## Validation

```powershell
python -m pytest tests -q
npm --prefix apps/desktop run build
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --check
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets --locked -- -D warnings
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Also run the Windows clean-artifact workflow and inspect generated version,
legal, SBOM, checksum, and docs reports.

## Risky files

- `.github/workflows/ci.yml`, `release-windows.yml`.
- `scripts/ci/sync-version.ps1` and all product version sources.
- `scripts/build-runtime.ps1`, `build-desktop.ps1`, real packaging tests.
- README/docs/release/legal metadata.

## Rollback points

- Land version checker before changing source values.
- Land PR gates before tightening release publication.
- Keep unsigned Beta explicit; never silently claim production signing.
