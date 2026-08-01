# Setup, Portable, and Artifact Smoke Design

## Canonical payload

Desktop build output and the verified Runtime Directory are copied into a fresh
payload stage. A payload manifest records desktop version, runtime digest,
executable/resource paths, prerequisite mode, legal/checksum inputs, and full
file inventory. Validation completes before any Setup/Portable output is named
or moved into the publish directory.

Portable is a deterministic archive of this stage. Setup installs the same
stage through Tauri's Windows bundler with offline WebView2/prerequisite inputs
selected by the measured lock task. Both report the same runtime digest.

## Fail-closed publication

Build outputs go to a non-publish staging root. Required-file, hash, version,
archive readability, runtime import, legal metadata, and weight/cache checks run
there. Only a full pass atomically promotes final artifacts and checksums.

No executable means failure. `BUILD_INSTRUCTIONS.txt` may exist only in developer
documentation, never as a substitute payload. Release jobs download/verify the
exact promoted artifacts and depend on smoke jobs.

## Desktop self-test

`FigureSmith.exe --self-test <result.json>` uses production Tauri Resource and
sidecar paths. It starts without showing the normal workflow, waits for
authenticated readiness, probes owned/vendor endpoints, validates exact native
ACL behavior and data-root mode, requests shutdown, waits/reaps the process tree,
then writes a versioned result with no tokens/keys/full sensitive paths.

## Artifact-only CI

One job builds and uploads artifacts. A separate clean job without checkout
downloads artifacts/checksums and runs from paths with spaces/non-ASCII text.
It clears Python/FigureSmith overrides and blocks dependency network access.
Setup is installed into a protected-style location, launched/self-tested, and
uninstalled; Portable is extracted and tested with adjacent writable data.

Negative tests operate on copies and cover missing/corrupt/unlisted cases. They
must fail before remote navigation and leave no child process.

## Rollback

Artifacts are immutable. A failed gate retains diagnostic staging/logs as CI
artifacts but never promotes release files. Rollback means publishing the last
fully gated version, not repairing a released archive.
