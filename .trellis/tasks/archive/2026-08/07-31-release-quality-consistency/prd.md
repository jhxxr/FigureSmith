# Release Quality and Consistency

## Goal

Turn the verified Beta implementation into a repeatable release process whose
CI, dependency metadata, versions, documentation, and legal/checksum claims all
describe the same artifact.

## Background

- PR CI omits composed backend, frontend, Rust, Tauri, and unpacked-artifact
  checks (`.github/workflows/ci.yml:21`).
- `cargo fmt --check` and strict clippy currently fail despite basic tests.
- Python runtime inputs are range-based and package metadata omits the full ML
  stack (`apps/backend/requirements.txt:21`, `apps/backend/pyproject.toml:26`).
- VERSION/Python/Tauri are 0.6.0 while npm/Cargo are 0.4.0 and CHANGELOG starts
  with 0.6.1 (`package.json:4`, `Cargo.toml:3`, `CHANGELOG.md:5`).
- English/Chinese README status differs, development docs contain a NUL byte,
  and manual release dispatch can publish without tag/version gates.

## Dependencies

Depends on the completed Windows runtime distribution and job/model lifecycle
children. It is the final quality gate and does not relax their fail-closed
contracts.

## Requirements

### R1. Required CI gates

- PR CI runs composed backend tests, frontend build/type checks, Rust fmt/clippy/
  tests, security fixtures, packaging invariants, and artifact smoke where
  Windows is required.
- Release workflow consumes the exact tested commit/artifact and cannot bypass
  version, checksum, weight, or smoke gates through manual dispatch.
- Failures leave diagnostics but no public release.

### R2. Reproducible metadata

- One authoritative `VERSION` is checked against Python, npm, Cargo, Tauri,
  runtime manifest, changelog, artifact names, and both READMEs.
- Runtime/build/test dependency locks, source hashes, legal notices, SBOM or
  equivalent inventory, and checksums are generated and verified.
- Package/build scripts and tests validate the actual assembly path, not only a
  helper with different filters.

### R3. Documentation and release claims

- English and Chinese current-state docs agree on phase, installation,
  runtime/weight boundary, driver/offline limits, and known Beta risks.
- Stale phase claims and binary/control characters are removed.
- Unsigned Beta versus signed production artifact status is explicit.

## Acceptance Criteria

- [ ] A pull request fails when any composed/UI/Rust/security/package check fails,
      including fmt and clippy.
- [ ] A release cannot publish from an arbitrary manual ref without passing the
      same version/artifact/smoke gates as a tag.
- [ ] All product/version/manifest/filename/docs sources agree on one value.
- [ ] Fresh lock/source/license/SBOM/checksum validation passes and real build
      scripts are covered by tests.
- [ ] English/Chinese docs render/read consistently and contain no NUL/binary
      control artifacts.
- [ ] Release notes explicitly state no model weights, driver prerequisite,
      offline dependency boundary, unsigned status, and deferred hardening.

## Out of Scope

- Procuring a code-signing certificate or changing the distribution channel.
- Automatic updater, delta patch, CDN, and telemetry design.
- New product capabilities.
