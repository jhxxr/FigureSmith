# Writable Application Data Design

## Resolver ownership

Python owns the canonical resolver because backend CLI, tests, desktop sidecar,
and packaged runtime all need the same behavior. Startup constructs a typed
`AppPaths` value once:

```text
root, settings, models, jobs, uploads, outputs, temp, logs, svg_cache
```

The composed app stores `AppPaths` on application state. Model/system/vendor
routes receive it through dependency or app-state access; they do not resolve
environment variables on every request.

The authenticated desktop readiness response includes the canonical root and
models path as nonsecret strings. Rust stores this public runtime metadata and
uses it for `open_models_directory`; it does not recompute LocalAppData paths.

## Resolution algorithm

1. If `FIGURESMITH_DATA_DIR` is nonempty, normalize and probe it. On failure,
   raise `DATA_DIR_NOT_WRITABLE` and stop.
2. In release/portable mode, try `<FIGURESMITH_INSTALL_ROOT>/data` if present.
   Failure is expected for Program Files and falls through.
3. In explicit development mode only, try the repository data directory.
4. Resolve `%LOCALAPPDATA%/FigureSmith`, probe it, or fail startup.

Python executable/current-working-directory heuristics are removed from release
selection. The sidecar passes install root and mode separately; it does not set
an adjacent candidate as an explicit override.

## Mutable path integration

Vendor server globals for uploads/outputs/history are replaced by paths derived
from `AppPaths`. Job working directories live under `temp` or `jobs` and are
created per job. Sanitized artifact cache uses a policy-versioned subtree under
`cache`.

Model managers and settings helpers accept the startup `AppPaths`/root rather
than invoking the default resolver independently. All child processes receive
only the canonical root in their controlled environment.

## Atomic write contract

Settings and small metadata are serialized to a uniquely named sibling temp,
flushed, optionally fsynced where supported, then replaced atomically. Cleanup
removes temp on every failure. Previous content remains until replace succeeds.

Large model promotion remains governed by the lifecycle child, but staging is
located under the final models/data volume so later atomic operations are not
broken by cross-volume temp paths.

## Compatibility

- Existing `FIGURESMITH_DATA_DIR` and CLI overrides keep their names.
- Dev users opt into repository data through the existing/new explicit dev
  launch path; production does not discover a repo accidentally.
- Existing model paths can be selected as import sources. This task does not
  silently move or delete them.
- Root-level `settings.json` remains compatible with current model settings.

## Operational behavior and rollback

The startup splash reports data-root failure before remote navigation. Logs may
show candidate path and error category but no sensitive file contents.

The refactor can roll back before the Windows runtime child consumes it. After
packaging, rollback must preserve the chosen root and prior settings. No
automatic destructive migration is introduced.

## Risks

- Windows antivirus or controlled-folder access may allow create but deny
  replace; the stronger probe intentionally detects that before use.
- Reparse points require resolved containment tests.
- Large model users may prefer another volume; explicit override remains the
  supported Beta mechanism until a relocation UI exists.
