# Writable Application Data Contract

## Goal

Make every mutable FigureSmith path use one verified writable data root while
keeping the installed application and packaged runtime immutable. Setup and
Portable must fail early or choose a working fallback, never fail later during
onboarding, model import, upload, or generation.

## Background

- The sidecar currently sets `FIGURESMITH_DATA_DIR` to executable-adjacent
  `data` (`apps/desktop/src-tauri/src/sidecar.rs:89`).
- An explicit data path is returned even when the writability check fails
  (`apps/backend/figuresmith/models/paths.py:74`).
- Vendor uploads and outputs are rooted in its source tree
  (`vendor/autofigure_edit/server.py:25`).
- Repository documentation intentionally prefers writable install-adjacent data
  so large models can stay off the system drive, then falls back to LocalAppData.

## Dependencies

Depends on `07-31-safe-beta-runtime-integration` for the sidecar launch and
authenticated readiness contracts. The Windows runtime distribution depends on
this task because its resources must remain immutable and its clean-install
smoke must exercise the resolved data root.

## Requirements

### R1. One authoritative resolution

- Backend startup resolves the data root once and stores the canonical result
  in application state.
- Resolution order is: explicit override; writable install/portable-adjacent
  `data`; explicit development repo data; LocalAppData fallback.
- An explicit override that cannot pass the write probe fails startup with a
  stable error. Automatic candidates may fall through to the next candidate.
- The final fallback must also pass the probe; failure is a blocking startup
  error, not a best-effort path.
- Readiness exposes the canonical path as nonsecret metadata so Rust native
  actions and backend routes use the same location.

### R2. Complete mutable layout

- Settings, models, job state, uploads, outputs, temporary files, logs, and
  sanitizer caches must derive from the resolved root.
- Runtime/application source directories must not receive mutable files in
  release mode.
- Temporary and staging paths must be on the target data volume when atomic
  rename/promotion requires same-volume behavior.

### R3. Safe writes and cleanup

- The probe must test create, write, flush, atomic replace/rename, and delete.
- Settings and metadata use temp-file plus atomic replacement with cleanup.
- Request/job temp directories have owned lifecycle and deterministic cleanup.
- Paths use resolved containment and do not follow a sibling-prefix escape.

### R4. Development and compatibility

- Explicit development mode may use repository data, but production mode may
  not infer a repo fallback from the current directory.
- Existing environment/CLI override names remain supported with stricter early
  validation.
- No automatic copy of multi-gigabyte existing model directories is required;
  they remain valid user-selected import sources.

## Acceptance Criteria

- [ ] A Setup-style read-only install root starts successfully and places all
      created files under a temporary LocalAppData root.
- [ ] A writable Portable root selects adjacent `data` and keeps large model
      paths on that volume.
- [ ] An explicitly configured read-only path fails before the UI navigates and
      reports a stable, redacted error.
- [ ] Settings, onboarding, SAM/RMBG import, upload, generation output, history,
      temp, logs, and sanitizer cache tests all resolve below the same root.
- [ ] A release-mode test scans the install/runtime tree before and after the
      workflow and finds no mutations.
- [ ] Atomic write failure preserves the previous settings/metadata and removes
      staging files.
- [ ] Desktop `open_models_directory` opens the backend-resolved models root,
      not an independently guessed path.
- [ ] Paths containing spaces and non-ASCII characters pass on Windows.

## Out of Scope

- A UI for relocating the entire data root after installation.
- Automatic copying of existing large model packs between volumes.
- Cloud/network storage and multi-user shared-data support.
- Full model transaction/recovery semantics; owned by the lifecycle child.

## Technical Notes

- Portable and Setup use the same resolver. Their normal install permissions
  naturally select adjacent data or LocalAppData without separate hidden rules.
- The Windows runtime manifest describes immutable resources only and must not
  include mutable data hashes.
