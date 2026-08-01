# FigureSmith Release Hardening Implementation Plan

## Execution model

The parent remains a planning and integration task. Product changes are made in
the child that owns the contract. Start only one overlapping child at a time;
parallel work is allowed only when file ownership and dependency contracts do
not overlap.

## Ordered checklist

### 1. Approve and freeze the program plan

- [ ] Review the parent PRD, design, child boundaries, and Safe Beta definition.
- [ ] Confirm every child PRD names explicit dependencies.
- [ ] Validate real entries in parent and first-child context manifests.
- [ ] After fresh user approval, start `safe-beta-runtime-integration`, not the
      parent coordinator.

### 2. Safe Beta runtime integration

- [ ] Replace fragile vendor route ordering with an outer composed ASGI app.
- [ ] Add production-composition HTTP tests for health, model, system, and
      shutdown routes with authentication enabled.
- [ ] Establish the desktop authentication readiness contract.
- [ ] Scope remote Tauri capability to the main loopback webview and approved
      native commands.
- [ ] Centralize sidecar startup/early-exit/close cleanup and own the Windows
      child process tree.
- [ ] Run Python, frontend, Rust, and cold-start integration checks.

### 3. Safe Beta security boundary

- [ ] Implement one bounded, fail-closed SVG sanitizer and use it during
      generation, rendering, history retrieval, preview, and download.
- [ ] Add artifact response isolation headers and prevent alternate raw paths.
- [ ] Require exact origin before bridge fetch/EventSource authentication.
- [ ] Make first-page API/SSE calls wait for the private desktop session.
- [ ] Enforce strict offline after effective provider defaults and redirects
      are resolved.
- [ ] Run hostile SVG, cross-origin canary, cold-load, and network-denial tests.

### 4. Writable application data

- [ ] Introduce one validated data-root resolver for desktop and backend.
- [ ] Move settings, models, jobs, uploads, outputs, temp files, and logs under
      that contract.
- [ ] Keep install/runtime resources read-only and preserve explicit dev mode.
- [ ] Add read-only install and atomic-write/fallback tests.

### 5. Safe Beta Windows runtime distribution

- [ ] Probe and freeze the CPython 3.12/cu128/SAM3/native-wheel compatibility
      matrix, source hashes, legal metadata, and measured artifact size.
- [ ] Generate exact hashed dependency/source locks and a canonical runtime
      manifest schema.
- [ ] Assemble the runtime offline from verified inputs and run import checks.
- [ ] Resolve release resources through the Tauri runtime contract with no
      system-Python or repository fallback.
- [ ] Build Setup and Portable from the same verified payload.
- [ ] Remove placeholder success behavior and stage artifacts atomically.
- [ ] Run clean-checkout-independent positive and negative artifact smoke tests.
- [ ] Perform a Safe Beta integration review across all four blocker children.

### 6. Job and model lifecycle hardening

- [ ] Implement bounded scheduling, stable job state, progress, timeout, and
      cancellation for generation and model imports.
- [ ] Move provider secrets and method content out of argv into a bounded,
      ephemeral child-input channel and redact diagnostics.
- [ ] Enforce streaming upload/resource limits and resolved path containment.
- [ ] Make graceful shutdown stop intake, settle/cancel work, and clean staging.
- [ ] Add process-wide locks, transaction journals, atomic settings updates,
      and recovery tests.
- [ ] Bound directory/archive import and fix path-containment checks.
- [ ] Pin and verify all executable model-package files and weight shards.
- [ ] Separate configured, valid, verified, and loaded status semantics.

### 7. Release quality and consistency

- [ ] Make composed Python, frontend, Rust format/lint/test, security, packaging,
      and clean-artifact smoke checks required in PR/release workflows.
- [ ] Separate build/test/runtime dependency inputs and validate every lock.
- [ ] Establish `VERSION` as the authoritative value and check Python, npm,
      Cargo, Tauri, changelog, filenames, and runtime manifest.
- [ ] Align English/Chinese documentation and remove stale or binary content.
- [ ] Validate legal notices, checksums, source metadata, and weight exclusions.
- [ ] Run the production-readiness review; do not infer it from Beta completion.

## Validation commands

Commands may gain focused targets inside each child, but these full gates remain
the integration baseline:

```powershell
python -m pytest tests -q
npm --prefix apps/desktop run build
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --check
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets --locked -- -D warnings
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Windows packaging validation must additionally:

```text
1. build the locked runtime from an empty staging directory;
2. assemble Setup and Portable;
3. verify runtime-manifest hashes and weight exclusions;
4. copy/download the artifact into a clean path with spaces and non-ASCII text;
5. launch, authenticate, probe health/model/system APIs, and shut down;
6. verify no FigureSmith-owned process survives;
7. corrupt required payload components and prove fail-closed behavior.
```

Playwright checks cover welcome, models, history/artifact, editor, refresh,
back/forward, external-origin canaries, and absence of non-loopback requests.

## Risky files and ownership boundaries

- `apps/backend/main.py`: production ASGI composition; child 1 owns first.
- `apps/desktop/src-tauri/src/lib.rs`, `sidecar.rs`, capabilities: child 1 owns
  session/process/capability contracts before child 3 changes release paths.
- `apps/backend/figuresmith/static/desktop-bridge.js`: child 2 owns origin and
  readiness behavior.
- `vendor/autofigure_edit/autofigure2.py` and `server.py`: the security child
  owns SVG and offline gates; the lifecycle child later owns job/secret/upload
  portions.
- Runtime/data path modules: child 4 establishes mutable paths before the
  Windows distribution child packages an immutable payload.
- `scripts/build-*.ps1`, Tauri bundle config, and release workflow: the Windows
  distribution child owns Beta packaging; final CI/version expansion belongs
  to the release-quality child.

Before touching a file already changed by a completed child, the next child
must read and preserve that child's tested contract.

## Rollback points

- Land and verify each child independently; do not combine all hardening into a
  single unreviewable patch.
- Keep development and release path resolution explicit so release hardening
  can be rolled back without hiding production fallback behavior.
- Promote runtime/artifact staging only after validation; failed staging is
  diagnostic output, never a release candidate.
- Preserve pre-migration data until atomic replacement and recovery checks pass.

## Pre-start gate

- [ ] Parent PRD has no unresolved product decisions.
- [ ] Parent and first-child `prd.md`, `design.md`, and `implement.md` are final.
- [ ] Parent and first-child `implement.jsonl`/`check.jsonl` contain real
      spec/research context.
- [ ] Task validation passes.
- [ ] User explicitly approves the latest final planning summary in a later
      message.
