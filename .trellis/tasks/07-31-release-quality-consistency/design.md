# Release Quality and Consistency Design

## Gate graph

```text
PR source/unit gates -> composed app + security -> runtime/package build
                                  |                     |
                                  +---------------------+--> clean artifact smoke
                                                               |
                                                               v
                                                    version/legal/docs publish gate
```

Every downstream job consumes an immutable upstream artifact/digest. A failed
check cannot be replaced with a manually uploaded or placeholder file.

## CI tiers

1. Fast PR tier: Python focused/full tests, frontend build/type, Rust fmt,
   clippy, tests, version/docs/control-character checks, and packaging filters.
2. Windows integration tier: composed app, Tauri capability/startup, runtime
   manifest/import, security canaries, Setup/Portable clean smoke, and process
   cleanup.
3. Release tier: exact version/tag relation, checksums, weight scan, legal/SBOM
   inventory, artifact digest, and publication.

The expensive runtime asset is cached by hash but never trusted solely because
it is cached. Jobs run with least privilege and retain redacted diagnostics.

## Version and metadata authority

`VERSION` is parsed once and compared to generated/declared Python, npm, Cargo,
Tauri, changelog, README, runtime manifest, and artifact names. CI has a check
mode and fails on drift. The release workflow receives a tag/ref, validates the
relation, and publishes only the artifact built from that commit.

## Documentation/legal consistency

Docs are checked for phase/status terms, weight/no-network/install boundaries,
driver/WebView2 prerequisites, unsigned status, and deferred risks. A control
character scan rejects NUL and binary artifacts in text documentation. Legal,
third-party, SBOM, source hash, and checksum files are generated from the same
runtime manifest and verified before publish.

## Compatibility and rollback

Existing local workflow commands remain available, but release jobs gain strict
checks. A failed quality gate publishes no release and preserves previous
artifacts. Reverting the gate changes does not make a stale/mismatched artifact
valid because consumers still verify manifest/version/checksum.

## Deferred production requirement

Code signing is represented as a documented release prerequisite and a future
CI gate; no private certificate or channel is invented in this task.
