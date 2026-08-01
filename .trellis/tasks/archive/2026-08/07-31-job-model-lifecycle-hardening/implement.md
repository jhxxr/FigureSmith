# Job and Model Lifecycle Hardening Implementation Plan

- [ ] Add characterization tests for concurrent run/import, timeout, cancel,
      shutdown, argv/log secrets, archive bounds, and status labels.
- [ ] Implement bounded `JobManager`, stable job records, idempotency, status,
      progress, capacity, timeout, and cancel APIs.
- [ ] Add process-tree controller, Windows Job Object/equivalent cleanup, and
      graceful backend shutdown/lifespan.
- [ ] Replace child argv secrets with bounded stdin envelopes and redaction.
- [ ] Stream-limit uploads and unify resolved path containment/reparse checks.
- [ ] Add import resource counters, overlap rejection, and async job progress.
- [ ] Add process-wide model/settings locks, journals, atomic promotion, and
      restart recovery.
- [ ] Expand model integrity to all executable files and weight shards; reject
      unverified code in production mode.
- [ ] Separate configured/valid/verified/loaded status and update UI/API tests.
- [ ] Run full stress, shutdown, recovery, security, Python, frontend, and Rust
      validation before handing off to release quality.

## Validation

Use deterministic fake children and small fixtures for unit tests, then run a
Windows process-tree smoke with real sidecar/generation. Inspect processes,
argv, environments, logs, staging trees, journals, and settings after every
cancel/timeout/shutdown path.

## Risky files

- `vendor/autofigure_edit/server.py` and `autofigure2.py`.
- `apps/backend/figuresmith/api/system_routes.py`, model imports/managers,
  settings I/O, and new job service.
- `apps/desktop/src-tauri/src/sidecar.rs`/commands only where lifecycle contract
  crosses the already-landed runtime integration.
- UI job/status/import consumers.

## Rollback points

- Land job state/controller before changing endpoint semantics.
- Land stdin protocol before removing argv values.
- Land transaction journals before changing promotion/settings order.
- Never add an environment flag that lets production execute unverified code or
  disables cleanup.
