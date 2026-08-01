# Setup, Portable, and Artifact Smoke Implementation Plan

- [ ] Create canonical payload and payload-manifest staging.
- [ ] Configure Tauri resources and measured offline WebView2/VC prerequisites.
- [ ] Build Portable and Setup from the identical verified stage.
- [ ] Replace placeholder behavior with required-file/hash/version/import gates.
- [ ] Add manifest-aware weight/cache and legal/checksum verification.
- [ ] Atomically promote only validated artifacts.
- [ ] Implement redacted noninteractive production self-test.
- [ ] Add artifact-only Portable and Setup clean Windows smoke with no checkout.
- [ ] Cover read-only Setup data fallback and writable Portable adjacent data.
- [ ] Add negative missing/corrupt/unlisted/weight/archive cases.
- [ ] Make PR/release workflows require build, smoke, and checksum results.
- [ ] Prove manual dispatch cannot bypass version/payload gates.

## Validation

Run upstream full Python/frontend/Rust checks, runtime manifest/import/weight
validation, payload construction, checksums, self-test, artifact-only Setup and
Portable smoke, uninstall, process-leak inspection, and every negative case.

## Risky areas

- `scripts/build-desktop.ps1` and current placeholder branch.
- Tauri resource/bundle/WebView2 configuration.
- Release workflow dependencies, manual dispatch, and publish staging.
- Windows install permissions, path encoding, process cleanup, and artifact size.

Do not publish or label a Safe Beta until every upstream dependency and this
task's artifact-only gate pass together.
