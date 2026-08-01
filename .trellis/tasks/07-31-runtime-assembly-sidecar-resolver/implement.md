# Application Pack and Sidecar Resolver Implementation Plan

- [x] Replace complete-runtime assembly with application-only pack assembly.
- [x] Add structured dependency contract and user-facing requirements file.
- [x] Generate and independently verify application manifest hashes.
- [x] Add release-only Tauri Resource resolver with no repository fallback.
- [x] Probe all discoverable Python base candidates and create/verify the
      per-user isolated environment without modifying any base environment.
- [x] Separate model package/GPU diagnostics from bootstrap startup.
- [x] Isolate Torch/CUDA probing from the backend process.
- [x] Refresh welcome/splash UI, one-click environment repair, and visual model
      import progress without duplicate status requests.
- [x] Update CI, desktop packaging, release notes, and bilingual docs.
- [ ] Run Windows artifact smoke with multiple Python installations, verify
      isolated environment creation, and use a deliberately broken Torch
      environment.

## Validation

Run `PYTHONPATH=apps/backend;vendor/autofigure_edit python -m pytest tests -q`,
`cargo fmt --check`, `cargo test --lib`, Node syntax checks, PowerShell parser
checks, and an application pack build. Release smoke must confirm no Python,
wheel, weight, cache, or user-data files are present.

## Risky areas

- Python launcher command resolution on Windows and real `sys.executable` paths.
- Native Torch imports that abort instead of raising Python exceptions.
- Runtime-manifest inventory drift after README/metadata generation.
- Tauri Resource path shape in raw and bundled layouts.
