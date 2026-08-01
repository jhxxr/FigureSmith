# Runtime Contract and Dependency Locks

## Goal

Freeze and prove the exact Windows Python/cu128/SAM3 runtime inputs before
building installers, including hashes, licenses, import compatibility, runtime
schema, and measured distribution cost.

## Dependencies

No implementation dependency. It consumes the approved self-contained-runtime
scope from `07-31-safe-beta-windows-runtime` and provides immutable contracts to
`07-31-runtime-assembly-sidecar-resolver`.

## Requirements

- Define versioned Runtime Directory and `runtime-manifest.json` schemas.
- Pin CPython 3.12 win-x64 embeddable, SAM3 application code/assets, all exact
  cu128/runtime wheels, and offline prerequisite inputs by SHA-256.
- Separate runtime dependencies from build and test tools; reject unpinned URLs,
  ranges, sdists, and local compilation in the release input set.
- Produce machine-readable source/license provenance and wheelhouse inventory.
- Build a disposable probe runtime and execute the full import/native-DLL matrix
  on a clean supported Windows runner with no model weights.
- Measure size, compression, build time, disk peak, WebView2/VC needs, and the
  configured release channel's ability to carry the complete payload.

## Acceptance Criteria

- [ ] Regenerating locks from declared direct inputs produces no unexplained
      diff and every runtime file source has an expected hash.
- [ ] Probe imports backend/vendor/SAM3/ML/native modules under isolated Python
      without user-site, system Python, model weights, or network access.
- [ ] SAM3 non-weight assets and license are identified; no checkpoint/cache is
      present.
- [ ] A complete license/source inventory and manifest schema validation pass.
- [ ] Measured size/time/disk/prerequisite report is committed to task research.
- [ ] Any channel/compatibility failure blocks downstream assembly and records
      evidence; dependencies are not dropped automatically.

## Out of Scope

- Building the canonical runtime tree or changing sidecar resolution.
- Producing Setup/Portable artifacts.
- Selecting a new distribution channel if measured limits fail; that requires a
  separately reviewed plan update.
