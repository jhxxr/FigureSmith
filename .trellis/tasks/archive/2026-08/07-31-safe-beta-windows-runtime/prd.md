# Safe Beta Windows Runtime Distribution

## Goal

Ship Windows Setup and Portable artifacts that contain one complete, verified
FigureSmith application runtime and start without a repository checkout, system
Python, pip, or online dependency installation. Model weights and caches remain
strictly excluded.

## Background

- Release startup currently requires source-style `apps/backend/main.py`
  (`apps/desktop/src-tauri/src/sidecar.rs:46`).
- Tauri bundle configuration contains no backend, vendor tree, or Python
  runtime, while existing build scripts assemble a different layout.
- `scripts/build-desktop.ps1:104` can report success and create a Portable zip
  with no executable; the current local placeholder artifact demonstrates it.
- Python dependencies are range-based, SAM3 application code is installed
  separately, and the existing Runtime Pack performs online pip setup.

## Dependencies

This task is a coordinator with three implementation children:

1. `07-31-runtime-contract-dependency-locks` has no code dependency and freezes
   compatibility, hashes, licensing, and measured size.
2. `07-31-runtime-assembly-sidecar-resolver` depends on child 1 plus the runtime
   integration and writable-data contracts.
3. `07-31-setup-portable-artifact-smoke` depends on children 1-2 and completed
   runtime-integration, security, and writable-data Safe Beta gates.

The Safe Windows Beta milestone is not reached until child 3 passes.

## Requirements

### R1. Reproducible runtime inputs

- Pin the exact CPython 3.12 Windows x64 embeddable archive and SHA-256.
- Pin exact Windows/cu128 Python wheels with hashes, including the full ML
  stack and all native dependencies required by the shipped application.
- Pin a buildable SAM3 application source/wheel commit and hash; include its
  required non-weight assets and license while excluding checkpoints/caches.
- Separate runtime, build, and test dependencies. Runtime assembly may consume
  only committed locks and verified sources.
- Record dependency licenses and source provenance.

### R2. Canonical immutable Runtime Directory

- Define one versioned layout and `runtime-manifest.json` used by standalone
  runtime checks, Tauri resources, Setup, and Portable.
- Include CPython, standard library, locked site-packages/native DLLs, backend,
  vendor app/editor, resources, legal notices, and lock metadata.
- Configure isolated Python paths with no user-site, registry, PATH Python, or
  repository influence.
- Exclude all model weights, model caches, user data, keys, and generated output.
- Verify every shipped file's size/hash against the manifest before packaging.

### R3. Offline assembly and release resolution

- Split acquisition from assembly. Assembly runs offline against a verified
  wheel/source cache using hash enforcement and no source builds.
- Release sidecar resolution must use the Tauri packaged resource contract and
  validate manifest/version/entry points before spawn.
- Release mode must not fall back to PATH Python, current directory,
  `CARGO_MANIFEST_DIR`, or a repository layout.
- Explicit development mode remains available through a separate resolver.

### R4. Complete Setup and Portable payloads

- Setup and Portable must consume the same validated immutable payload.
- Each artifact includes a working desktop executable, full Runtime Directory,
  and an offline-compatible WebView2/VC runtime strategy validated on a clean
  supported Windows image.
- No target-machine pip, online bootstrap, or manual combination of companion
  packages is permitted.
- A missing executable/runtime/manifest/hash/import or unexpected weight causes
  non-zero failure and no publishable artifact.

### R5. Clean artifact smoke and release gate

- Validate from an artifact-only Windows job with no source checkout and with
  Python/FigureSmith overrides cleared.
- Launch from paths containing spaces and non-ASCII characters, authenticate,
  probe health/model/system/vendor APIs, exercise native command ACL, and shut
  down with no surviving process.
- Test both writable Portable-adjacent data and read-only Setup install fallback.
- Negative smoke must corrupt/remove key components and prove fail-closed
  behavior.
- Release publishing must require the smoke and manifest/checksum gates.

## Acceptance Criteria

- [ ] Committed source/dependency locks reproduce an importable Python 3.12
      win-x64/cu128 runtime from an empty staging directory.
- [ ] SAM3 application code and required assets import locally without model
      weights or a network call.
- [ ] Runtime manifest verification covers every file and reports
      `contains_weights: false`; independent scans find no weights/caches.
- [ ] Isolated Python ignores user site, system Python, registry, and arbitrary
      current-directory packages.
- [ ] Raw runtime, Portable, and installed Setup all reach authenticated ready
      state without a checkout or online install.
- [ ] Setup and Portable contain the same runtime-manifest digest and product
      version.
- [ ] Missing executable, Python DLL, backend entry, manifest, or mismatched
      hash fails before navigation and produces no placeholder release archive.
- [ ] Clean-artifact workflow covers launch, API/native flows, data-root
      behavior, shutdown, process cleanup, checksums, and negative corruption.
- [ ] Full compressed/uncompressed size and build time are recorded. If the
      accepted release channel cannot carry the complete payload, publishing is
      blocked for a separately reviewed delivery decision; dependencies are not
      silently removed.

## Out of Scope

- SAM3/RMBG or other model weights and caches.
- NVIDIA display/compute driver redistribution.
- macOS/Linux artifacts.
- Code signing, automatic updates, delta patches, and CDN selection.
- Full GPU inference certification on every supported card; representative
  hardware smoke is a later release qualification.

## Technical Notes

- CPython's embeddable package intentionally lacks pip; this is desirable on
  target machines because all packages are preassembled.
- Weight detection must be manifest-aware because legitimate Python packaging
  can include `.pth` files and non-model `.bin` resources.
