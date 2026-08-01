# Setup, Portable, and Artifact Smoke

## Goal

Produce Setup and Portable from one verified desktop payload and make an
artifact-only clean Windows smoke a mandatory release gate, including negative
proof that incomplete/corrupt builds cannot be published.

## Dependencies

- `07-31-runtime-assembly-sidecar-resolver` supplies the verified Runtime
  Directory and release resolver.
- `07-31-safe-beta-runtime-integration`,
  `07-31-safe-beta-security-boundary`, and
  `07-31-writable-application-data` must pass before final payload assembly.

This task is the terminal gate for the Safe Windows Beta milestone.

## Requirements

- Stage one immutable payload containing executable, complete runtime, and
  legal/runtime metadata; validate it before publishing.
- Build Portable and Setup from the same payload and runtime-manifest digest.
- Provide/validate an offline-compatible WebView2 and VC/UCRT strategy on a
  clean supported Windows image.
- Remove placeholder artifact success. Missing, corrupt, mismatched, unlisted,
  or weight-bearing content fails nonzero and leaves no publishable archive.
- Add redacted noninteractive desktop self-test using real resource resolution,
  authenticated backend/native flows, data-root behavior, and process cleanup.
- Run artifact-only checks without source checkout from hostile paths, including
  Setup install/start/uninstall and Portable launch.
- Require checksums, manifest verification, positive smoke, and negative
  corruption matrix before release creation, including manual dispatch.

## Acceptance Criteria

- [ ] Setup and Portable contain the same version/runtime-manifest digest and a
      complete executable/runtime payload with no weights/caches/user data.
- [ ] A clean artifact-only runner launches both without Python, pip, checkout,
      or dependency network access.
- [ ] Self-test proves authenticated health/model/system/vendor APIs, approved
      native commands, writable-data selection, shutdown, and no surviving PID.
- [ ] Setup succeeds under read-only install permissions and uninstalls cleanly;
      Portable uses writable adjacent data when available.
- [ ] Paths with spaces and non-ASCII characters pass.
- [ ] Removing executable/Python DLL/backend/manifest, corrupting a hash/archive,
      or injecting an unlisted weight makes build or startup fail closed.
- [ ] Release workflow cannot upload a placeholder or bypass gates on manual run.

## Out of Scope

- Code signing, updater/delta delivery, CDN/channel changes, and macOS/Linux.
- Bundled model weights or full representative GPU inference qualification.
