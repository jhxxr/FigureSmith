# Implementation plan — packaged Runtime startup flow

## Ordered checklist

1. **Update the packaging contract**
   - Set Tauri `bundle.resources` to `runtime`.
   - Replace stale shell-only comments and long-description text.
   - Make `build-desktop.ps1` preserve/stage the Runtime resource and assert
     the built Tauri resource contains the manifest, embedded interpreter, and
     no model-weight files.
   - Keep only MSI/Setup plus the separately published CPU Runtime ZIP; do not
     add Portable output.

2. **Refactor Runtime verification ownership**
   - Split the manifest verifier into a progress-capable internal function and
     a no-op-callback wrapper.
   - Remove full verification from
     `resolve_release_runtime_root()` and `resolve_application_layout()`.
   - Make `SidecarState::start_with_progress()` resolve the layout once,
     validate one release Runtime, report progress, then transition to
     `starting` before spawning the embedded interpreter.
   - Preserve release fail-closed behavior and development-only explicit source
     resolution.

3. **Move startup off the Tauri setup thread**
   - Add a serializable Rust startup status payload and bounded error
     classification.
   - In `lib.rs`, emit `locating`, then run resolution/verification/sidecar
     startup in `spawn_blocking`.
   - Hand the verified ready state back through `run_on_main_thread`, register
     the state, start liveness monitoring, and create the hidden remote window.
   - Keep the existing page-load visibility gate and shutdown cleanup.

4. **Make the Splash stateful**
   - Replace the static status write with a typed `startup-status` listener.
   - Render locating, verifying with file progress, starting, ready, and
     bounded bilingual error states.
   - Remove wording that asks users to place a sibling Runtime directory beside
     the executable. Explain Setup/MSI repair and the optional ZIP instead.

5. **Update release documentation and workflow contracts**
   - Document the one-step installer and ZIP repair path in the desktop README.
   - Keep the CI runtime download/staging step and add/adjust assertions for
     the Tauri resource and retained staged tree.
   - Ensure release notes continue to say CPU-only, external models, and no
     Portable package.

6. **Add/adjust tests**
   - Update `tests/test_desktop_packaging_contract.py` for embedded resources,
     startup event names, error guidance, and no Portable output.
   - Extend `tests/test_runtime_release_workflow_contract.py` for resource
     staging/retention.
   - Add Rust tests for direct/nested roots, discovery without hashing, one
     verification path, progress callbacks, and existing rejection cases.

## Validation commands

From the repository root:

```powershell
python -m pytest tests/test_desktop_packaging_contract.py tests/test_runtime_release_workflow_contract.py
cd apps/desktop
npm run build
cd src-tauri
cargo test
cd ../../..
python -m pytest
```

On Windows with a staged CPU Runtime:

```powershell
./scripts/build-desktop.ps1 -SkipBuild
```

The final check must also inspect the generated bundle/resource tree and run
the existing no-model-weights assertion. A full GitHub Actions packaging run
is the release-level proof that MSI/Setup contains the staged CPU Runtime.

## Risk and rollback points

- **Before Rust changes:** resource/config and script changes can be reverted
  without touching runtime verification logic.
- **After Rust changes:** if async handoff or Tauri API compatibility fails,
  keep the single-verification refactor and revert only the threading handoff
  while fixing the API usage.
- **Before release:** do not publish an installer unless the resource manifest,
  `python/python.exe`, no-weight assertion, Rust tests, frontend build, and
  contract tests are all green.

## Completion note

The implementation gate was approved before product changes. The final
installer proof still belongs to the GitHub Actions Windows packaging run,
because this checkout does not contain a CPU Runtime staging tree.
