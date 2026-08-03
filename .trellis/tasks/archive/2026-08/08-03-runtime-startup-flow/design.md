# Design — packaged Runtime startup flow

## Goal

Make a clean Windows Setup/MSI installation self-contained for the CPU
Runtime, while keeping the existing fail-closed Runtime V1 integrity boundary.
The local Splash must remain responsive and identify the expensive operation
instead of appearing frozen.

## Boundaries and data flow

```text
GitHub Actions CPU Runtime artifact
  → apps/desktop/src-tauri/runtime (build staging)
  → Tauri bundle.resources = ["runtime"]
  → installed Tauri resource directory/runtime/
  → locate manifest root
  → one manifest + inventory + hash verification
  → embedded python/python.exe
  → authenticated /api/desktop/ready
  → remote main editor window
```

Model weights and mutable user data remain outside this flow. No Portable
artifact, system Python, PATH fallback, venv creation, pip install, or startup
network download is introduced.

## Resource contract

`tauri.conf.json` will declare `"resources": ["runtime"]`. The existing CI
staging step remains the source of truth for the resource contents and the
installed layout is expected to be:

```text
<Tauri resource directory>/runtime/runtime-manifest.json
<Tauri resource directory>/runtime/python/python.exe
<Tauri resource directory>/runtime/app/backend/main.py
<Tauri resource directory>/runtime/app/vendor/autofigure_edit/server.py
```

The resolver will continue accepting a resource directory whose manifest is
directly at its root for compatibility with unpacked/test layouts, as well as
the nested Tauri layout. It will not inspect a sibling directory beside the
executable or fall back to repository/PATH locations in release mode.

## Startup state machine

The Tauri `setup()` callback will only configure menus. A global Tauri
page-load hook schedules startup after the local Splash page has loaded, so
its event listener is ready even when Runtime discovery fails immediately. It
will not perform manifest hashing, spawn Python, or wait for readiness.

```text
locating
  → verifying (with checked/total file progress)
  → starting (embedded Python has passed verification)
  → ready (authenticated /api/desktop/ready succeeded)
  → main window shown
```

The worker will use `tauri::async_runtime::spawn_blocking` because manifest
inventory/hash work and the current sidecar readiness loop are blocking. Once
the sidecar is ready, `AppHandle::run_on_main_thread` will:

1. register `SidecarState` with the application;
2. start its post-ready liveness monitor; and
3. create the hidden remote `main` window.

The existing `on_page_load` rule remains the final visibility gate: the editor
is shown and the Splash is closed only after the authenticated sidecar page
loads. A failed worker or main-thread handoff leaves the Splash visible with a
bounded error.

## Cross-layer startup event contract

Rust will emit one typed `startup-status` event shape:

```json
{
  "phase": "locating | verifying | starting | ready | error",
  "code": "runtime-missing | runtime-invalid | backend-failed | null",
  "checked_files": 1234,
  "total_files": 23476,
  "detail": "bounded diagnostic or null"
}
```

`checked_files` and `total_files` are optional and are used only during
verification. The frontend owns bilingual presentation and maps `code` to
actionable text:

- `runtime-missing`: rerun the FigureSmith Setup/MSI installer; the optional
  CPU Runtime ZIP is the repair asset.
- `runtime-invalid`: the installed Runtime is incomplete or modified; rerun
  the installer or replace it with the matching verified CPU Runtime ZIP.
- `backend-failed`: Runtime verification passed, but the local backend did not
  become ready; retry after checking the bounded detail.

The event detail is truncated in Rust before emission and must not contain
session credentials. The legacy `sidecar-error` event may remain as a
compatibility emission, but the Splash will consume `startup-status` as its
single source of truth.

## Single verification owner

`resolve_release_runtime_root()` will perform only cheap candidate/root
discovery. `resolve_application_layout()` will validate structure and select
paths, but will not hash the Runtime. `SidecarState::start_with_progress()`
will call the progress-capable manifest verifier exactly once for release
layouts, then emit `starting` immediately before spawning Python.

The existing no-progress verifier remains as a test/build helper that delegates
to the progress-capable implementation. This preserves current tamper,
extra-file, missing-file, schema, version, and interpreter tests while making
the startup call graph auditable.

## Packaging and documentation

- `scripts/build-desktop.ps1` will stage a supplied `RuntimeRoot` into the
  configured Tauri resource source when necessary and verify that source tree
  before and after the build. It must not inspect Tauri's ephemeral
  `target/release/resources` staging directory after bundling: Tauri may empty
  or remove that implementation-detail directory after producing the MSI and
  Setup bundles, even though the installers contain the configured resource.
- Existing GitHub Actions CPU artifact download/staging remains in place and
  feeds the installer build. Contract checks will assert the resource config,
  staging path, manifest/interpreter checks, and installer-only release set.
- `apps/desktop/README.md` and the Tauri long description will describe the
  one-step CPU Runtime installer, the optional ZIP repair path, external model
  weights, and the absence of Portable packaging.

## Compatibility and rollback

Development mode keeps its explicit source-root/Python behavior. Only release
resolution changes. If Tauri resource inclusion causes an installer-size or
bundle regression, rollback is limited to the resource/config and packaging
changes; the startup event/state-machine refactor can remain independently
tested. No user data or model directories are migrated or deleted.

## Verification strategy

- Rust unit tests cover direct/nested resource discovery, no verification in
  discovery/layout helpers, single startup verification ownership, progress
  callbacks, and all existing fail-closed rejection cases.
- Python contract tests cover Tauri resource configuration, staging retention,
  installer-only outputs, and the frontend event/phase contract.
- Frontend `npm run build` checks the typed event consumer.
- Rust `cargo test` and the relevant Python test slice/full suite validate the
  cross-layer implementation.
