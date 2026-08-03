# Fix packaged runtime startup flow

## Goal

Make the Windows release start-up path understandable and self-contained:
users install the Setup/MSI package once, the CPU Runtime V1 is installed with
it, and the first launch visibly progresses through the required integrity
check before starting the local backend. The application must never present a
static-looking splash while synchronously doing hidden work.

## Background / confirmed facts

- The current v0.6.4 release publishes a desktop shell and CPU Runtime ZIP as
  separate assets. The shell requires users to manually place a `runtime`
  directory beside `FigureSmith.exe`.
- `apps/desktop/src-tauri/tauri.conf.json` has an empty `bundle.resources` list,
  so the Runtime is not installed by MSI/NSIS.
- Release startup performs full Runtime V1 manifest validation over roughly
  23,476 files / 807 MB of extracted CPU Runtime content.
- The current path validates the same manifest twice: once while resolving the
  release root and again while constructing the sidecar layout. Both happen in
  the synchronous Tauri setup path, leaving the Splash with static text.
- Model weights remain external and must not be added to installers or Runtime
  resources. Portable packaging is out of scope and must remain unpublished.

## Requirements

1. **Automatic Runtime installation**
   - The CPU Runtime V1 tree must be included as a Tauri resource in the
     Windows MSI and Setup EXE.
   - Release startup must resolve the installed resource layout, including the
     Tauri nested-resource form, without requiring manual extraction or
     renaming by the user.
   - The CPU Runtime ZIP may remain a separately published repair/backup asset.

2. **Strict, single startup verification**
   - A release launch must complete the full Runtime V1 manifest/inventory/hash
     verification before spawning the Python backend.
   - One launch must invoke the full verification at most once; path discovery
     and sidecar layout construction must not repeat it.
   - Missing, extra, tampered, wrong-version, or incomplete Runtime content must
     still fail closed and must never fall back to system Python, PATH, or the
     repository.

3. **Visible startup state**
   - The local Splash must expose meaningful phases for locating the Runtime,
     verifying it, starting the backend, backend-ready, and startup failure.
   - The UI must not claim that the application is ready before verification and
     `/api/desktop/ready` succeed.
   - Verification/startup failures must provide a bounded, actionable message
     that distinguishes missing Runtime from modified/invalid Runtime.

4. **Release and contract consistency**
   - CI packaging must stage and bundle the CPU Runtime resource and continue to
     assert that no model weights are present.
   - Release documentation must describe the one-step installer flow and the
     optional Runtime ZIP repair path.
   - Rust, frontend, and workflow contract tests must cover the new resource
     layout and startup state contract.

## Acceptance Criteria

- [ ] A clean Windows MSI/Setup installation contains the CPU Runtime V1 tree;
      a user does not need to create or rename a sibling `runtime` directory.
- [ ] Release startup performs exactly one full Runtime V1 verification before
      starting the sidecar, and rejects a missing, tampered, extra-file,
      wrong-version, or incomplete Runtime.
- [ ] The Splash visibly transitions through verification and backend startup;
      it no longer remains on a static generic message during the long step.
- [ ] A successful launch opens the editor only after the authenticated
      `/api/desktop/ready` probe succeeds.
- [ ] CPU Runtime, MSI, Setup EXE, manifests, and checksums remain publishable;
      no Portable package or model weights are produced.
- [ ] Relevant Python tests, Rust tests, frontend build, PowerShell/YAML
      contracts, and packaging checks pass.

## Out of scope

- CUDA/cu128 Runtime inclusion in the Windows release.
- Downloading model weights or dependencies at first launch.
- Reintroducing Portable packaging.
- Removing the fail-closed integrity requirement or starting the backend before
  full verification.

## Planning status

All product decisions are resolved: the CPU Runtime is installed by Setup/MSI,
the ZIP remains an optional repair asset, verification is strict and happens
once before backend startup, and Portable packaging remains out of scope.
