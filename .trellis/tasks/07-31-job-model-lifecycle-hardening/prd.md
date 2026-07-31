# Job and Model Lifecycle Hardening

## Goal

Make long-running generation and model operations bounded, cancellable,
transactional, and honest about integrity so the post-Beta application cannot
exhaust a machine, leave work behind, or execute unverified model code.

## Background

- `/api/run` launches an unbounded heavyweight child for every request
  (`vendor/autofigure_edit/server.py:184`).
- Model import can exceed the desktop's fixed 120-second command timeout
  (`apps/desktop/src-tauri/src/commands.rs:23`).
- Shutdown calls `os._exit` without owning generation descendants
  (`apps/backend/figuresmith/api/system_routes.py:308`,
  `vendor/autofigure_edit/server.py:371`).
- Provider keys and method text are currently put in child argv
  (`vendor/autofigure_edit/server.py:244`).
- Directory import is not completely resource-bounded
  (`apps/backend/figuresmith/models/import_rmbg.py:283`), and model/settings
  operations lack process-wide locking/transaction recovery.
- `trust_remote_code=True` is used while executable model files have no release
  pins (`resources/model-manifest.json:36`).

## Dependencies

Depends on the completed runtime-integration and writable-data contracts, and
must preserve the security child's SVG/offline/bridge behavior. It is a
post-Beta hardening child; the first Safe Beta may explicitly document that
complete lifecycle and model-code verification are not yet production claims.

## Key policy decision

Production mode executes only model packages whose complete executable-code and
weight-shard inventory matches a trusted, pinned manifest. An imported package
that does not match may be inspected or re-imported after verification, but is
not executed through `trust_remote_code` in production mode. This is the safe
default for a release artifact; it avoids treating a user-selected code pack as
verified merely because its weights load.

## Requirements

### R1. Bounded jobs

- Generation and import use stable job IDs, explicit queued/running/succeeded/
  failed/cancelled states, progress, timeout, and one-GPU concurrency limit.
- Duplicate submissions have an idempotency key or deterministic rejection.
- Cancellation terminates the owned process tree and cleans temp/output staging.
- Existing UI/API shapes remain additive/compatible where practical.

### R2. Graceful lifecycle

- Shutdown stops intake, cancels or settles active jobs within a bounded window,
  terminates descendants, cleans staging, and exits normally.
- Crash/timeout recovery marks interrupted jobs and removes incomplete promotion.
- Windows and non-Windows process-tree cleanup share a tested abstraction.

### R3. Safe input and filesystem bounds

- Provider secrets and method content move from argv into bounded stdin/pipe
  input; child environments and logs are allowlisted/redacted.
- Uploads stream under byte limits before decoding; artifact paths use resolved
  containment and reject sibling-prefix/reparse escapes.
- Directory/archive imports enforce member, byte, depth, compression-ratio,
  and destination-overlap limits before copying.

### R4. Transactional model/settings operations

- Imports use process-wide locks, staging journals, atomic promotion, settings
  compare/update, and recovery on restart.
- Status separates configured, structurally valid, integrity verified, and
  runtime loaded; installed files alone do not imply loaded.

### R5. Executable model integrity

- Trusted manifests cover every executable Python/config file and every weight
  shard, not just an index or first shard.
- `trust_remote_code` execution is denied when the complete code inventory or
  source provenance does not match the trusted policy.

## Acceptance Criteria

- [ ] Concurrent generation/import requests are bounded and observable; excess
      work queues or rejects deterministically.
- [ ] Cancel, timeout, close, and shutdown leave no child process or staging
      directory, including grandchildren.
- [ ] Restart recovery marks interrupted jobs and preserves the previous model/
      settings state.
- [ ] Process inspection/log capture finds no provider key, method text, or
      session token in argv/environment/logs.
- [ ] Oversized uploads/imports, zip bombs, overlap, and sibling-prefix paths
      fail before unsafe memory/copy operations.
- [ ] Concurrent model/settings operations cannot lose fields or leave a model
      promoted without matching settings/transaction state.
- [ ] Unverified executable model code is rejected in production mode; complete
      trusted manifests verify all shards/files and status labels are distinct.

## Out of Scope

- New generation/model capabilities.
- Automatic cloud model downloads or weight redistribution.
- General production code signing and updater work.
