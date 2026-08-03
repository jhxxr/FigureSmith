# Evidence — packaged Runtime startup flow

## Repository facts

- `apps/desktop/src-tauri/tauri.conf.json:28-32` currently declares an empty
  `bundle.resources` list.
- `.github/workflows/release-windows.yml:208-239` already downloads the CPU
  Runtime artifact and stages its top-level entries into
  `apps/desktop/src-tauri/runtime` before the Tauri build.
- `scripts/build-desktop.ps1:77-81` still describes the installer as a shell
  without Runtime resources, and `scripts/build-desktop.ps1:110-116` removes a
  staged Runtime after the Tauri build. Both statements are incompatible with
  the selected one-step installer flow.
- `apps/desktop/src-tauri/src/lib.rs:82-121` resolves and starts the sidecar
  synchronously inside Tauri `setup()`. The same callback also creates the
  remote editor window, so the local Splash cannot display intermediate work.
- `apps/desktop/src-tauri/src/sidecar.rs:99-105` constructs the runtime layout
  before launching the child. `resolve_application_layout()` currently calls
  `validate_runtime_manifest()` at lines 1365-1371, while
  `resolve_release_runtime_root()` calls it again at lines 1434-1449.
- `apps/desktop/src/main.ts` only listens for `sidecar-error` and otherwise
  writes one static verification message. `apps/desktop/index.html` contains
  no progress or phase contract.

## Consequence

The current release path performs approximately 23,476 file checks over an
approximately 807 MB extracted CPU Runtime twice on the synchronous setup
thread. The fix must preserve fail-closed verification while moving the work
off the setup/UI thread and making the phase transitions explicit.

## Chosen implementation boundary

`resolve_release_runtime_root()` will only locate a direct or nested Tauri
resource root. `SidecarState::start_with_progress()` will be the only startup
authority that validates a release Runtime and will validate it once before
spawning Python. This keeps discovery, verification, process launch, and the
authenticated readiness probe in one auditable sequence.

During implementation review, the old release resolver was also found to add
the executable's parent as a fallback candidate. That would have allowed a
manually created sibling `runtime` directory to bypass the selected installer
contract, so release resolution now accepts only the Tauri `resource_dir`.
