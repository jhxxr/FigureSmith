# Runtime Assembly and Sidecar Resolver

## Goal

Build the canonical complete Runtime Directory offline from frozen inputs and
make release desktop startup resolve and validate only that packaged runtime.

## Dependencies

- `07-31-runtime-contract-dependency-locks` must provide passing schemas, locks,
  probe compatibility, and measurements.
- `07-31-safe-beta-runtime-integration` must provide the final sidecar lifecycle.
- `07-31-writable-application-data` must provide the immutable-resource versus
  mutable-data contract.

It provides a verified payload input to `07-31-setup-portable-artifact-smoke`.

## Requirements

- Acquire/download in a separate phase, then assemble from an empty directory
  with network disabled, hash enforcement, no sdists, and no local builds.
- Include isolated CPython, all locked packages/native DLLs, pinned SAM3 code and
  non-weight assets, backend/vendor/editor/resources, locks, and legal notices.
- Use one structured packaging implementation and one manifest-aware exclusion
  policy; no divergent script/helper filters.
- Run isolated imports and production app-factory smoke before generating and
  independently verifying the full runtime manifest.
- Add explicit Rust development and release resolvers. Release uses Tauri
  Resource paths and rejects missing/hash/version/entry mismatch before spawn.
- Release must never fall back to PATH Python, current directory, build paths,
  or repository layout.

## Acceptance Criteria

- [ ] Two clean offline assemblies from the same inputs have identical manifest
      file sets and hashes apart from explicitly normalized metadata.
- [ ] Staged Python imports the complete application under isolated path rules.
- [ ] Manifest verification covers every file and independent scanning confirms
      no weight/cache/user data.
- [ ] Production app factory reaches authenticated readiness from staged paths.
- [ ] Release resolver selects packaged Python/backend through Tauri Resource on
      raw/bundled test layouts and ignores hostile PATH/current-directory files.
- [ ] Missing/corrupt/wrong-version runtime fails on the local splash before a
      remote webview or backend child remains.

## Out of Scope

- Setup/Portable archive/installer construction and publish workflows.
- Runtime dependency/version changes outside the frozen lock child.
- Mutable data migration or model weights.
