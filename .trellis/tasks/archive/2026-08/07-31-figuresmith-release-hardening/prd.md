# FigureSmith release hardening

## Goal

Turn the current development-ready FigureSmith prototype into a Windows desktop
release whose runtime behavior, security boundary, packaging claims, and release
metadata are internally consistent and verifiable on a clean machine.

The user outcome is a FigureSmith build that can be installed or unpacked,
started without a source checkout, and used for its documented onboarding,
model-management, creation, and shutdown workflows without known critical
failures.

The first milestone is a **Safe Windows Beta**. It closes runtime composition,
native-command access, installable distribution, writable application data,
effective strict-offline behavior, process-tree startup cleanup, and critical
SVG/session-token security blockers. Broader job lifecycle, model-supply-chain,
CI, version, and documentation requirements remain owned by this parent task
and are delivered through follow-up children before production-ready
positioning.

## Confirmed Facts

- The Python suite passes (`214 passed, 1 warning`), the frontend production
  build passes, and Cargo check plus the three current Rust unit tests pass.
- In the actual vendor-backed application, `GET /api/models` and
  `GET /api/system/status` return 404 and `POST /api/shutdown` returns 405.
  FigureSmith routers are appended after the vendor catch-all mount
  (`apps/backend/main.py:91`, `vendor/autofigure_edit/server.py:808`).
- The Tauri webview navigates from bundled code to a dynamic loopback origin,
  while the enabled capability has no remote URL grant
  (`apps/desktop/src/main.ts:57`,
  `apps/desktop/src-tauri/capabilities/default.json:5`).
- The desktop sidecar requires a source-style `apps/backend/main.py` tree, but
  desktop artifacts do not bundle the backend, vendor tree, or Python runtime
  (`apps/desktop/src-tauri/src/sidecar.rs:46`,
  `scripts/build-desktop.ps1:93`).
- The desktop packaging script can produce a successful placeholder Portable
  zip with no executable (`scripts/build-desktop.ps1:104`). The current ignored
  local artifact demonstrates this path.
- Generated SVG is treated as trusted same-origin content after XML parsing,
  and the desktop fetch/EventSource bridge decides whether to attach the
  session token by path without enforcing the API origin
  (`vendor/autofigure_edit/autofigure2.py:2623`,
  `apps/backend/figuresmith/static/desktop-bridge.js:27`).
- Generation jobs have no queue or cancellation contract, secrets and method
  text are placed in child argv, and graceful shutdown does not own all child
  processes (`vendor/autofigure_edit/server.py:184`,
  `apps/backend/figuresmith/api/system_routes.py:308`).
- Model executable-code integrity is not pinned, model directory import lacks
  a complete resource bound, and model operations do not have a process-wide
  concurrency contract (`resources/model-manifest.json:36`,
  `apps/backend/figuresmith/models/import_rmbg.py:283`).
- The standard CI workflow does not exercise the composed application, Rust,
  Tauri, or an installed/unpacked artifact (`.github/workflows/ci.yml:21`).
- Version sources and bilingual release documentation are currently divergent.

## Delivery Scope

The Safe Beta release train consists of four gates: production runtime
integration, security boundary, writable application data, and the nested
Windows runtime/payload/smoke chain. The runtime chain is ordered as locks and
compatibility measurement, offline assembly and release resolution, then Setup
and Portable artifact smoke.

After Beta, the job/model lifecycle child closes bounded work, secure child
input, transactional imports, and executable-model integrity. The release
quality child then promotes all cross-layer checks, version synchronization,
metadata, documentation, and publication controls into required gates.

## Requirements

### R1. Runtime integration

- The real vendor-backed application must expose every FigureSmith-owned API
  before any catch-all route can intercept it.
- Onboarding, model list/import/verify/delete, system status, and shutdown must
  work through the same application entry point shipped to users.
- The loopback UI must have only the minimum explicitly granted Tauri commands
  needed for native model workflows.

### R2. Installable desktop distribution

- A Setup or Portable artifact must start and reach a healthy backend without a
  repository checkout or developer toolchain.
- The shipped Windows runtime must include a pinned CPython interpreter and all
  application runtime dependencies, including the pinned SAM3 application
  code. Model weights and model caches remain excluded.
- Setup and Portable distributions must each contain the complete runtime; a
  user must not need to install Python, run pip, or combine separately
  downloaded application packages before first launch.
- Runtime layout and sidecar discovery must use one documented contract.
- A desktop build with no runnable executable or backend must fail and must not
  produce a publishable artifact.

### R3. Security boundary

- Generated/imported SVG must be handled as untrusted content and must not gain
  same-origin script execution or unrestricted outbound loading.
- Session credentials must only be attached to the exact loopback API origin
  and must not be exposed through process arguments, logs, or external pages.
- Any model format that executes Python code must have a release-grade source
  and integrity policy covering executable files as well as weights.

### R4. Job and model lifecycle

- Generation and import operations must have explicit concurrency limits,
  observable progress, timeout behavior, cancellation, and deterministic
  cleanup.
- Application shutdown must stop accepting work, settle or cancel active work,
  and leave no child process, staging directory, or partially promoted model.
- Concurrent settings/model/onboarding updates must not lose data.

### R5. Writable application data

- Models, settings, uploads, outputs, and transient work must use a writable
  application-data contract independent of installation permissions.
- A non-writable install directory must produce a working fallback rather than
  a delayed import/onboarding failure.

### R6. Release quality gates

- CI must cover the composed backend application, frontend build, Rust format,
  lint and tests, packaging invariants, and an unpacked-artifact startup smoke
  test.
- Dependency inputs and every product version source must be reproducible and
  checked for consistency.
- English and Chinese current-state documentation must describe the same
  shipped behavior and limitations.

## Acceptance Criteria

- [ ] A test using the production application assembly receives successful,
      authenticated responses from FigureSmith model/system routes and proves
      they precede the vendor catch-all route.
- [ ] Welcome and Models UI Playwright flows complete without 404/405 responses
      or raw API errors.
- [ ] The loopback UI can invoke only the approved native model commands under
      the pinned Tauri version.
- [ ] Setup and Portable artifacts pass a clean-directory launch smoke test and
      reach `/healthz`; neither depends on repository-only paths, system Python,
      pip, or an online dependency install.
- [ ] Artifact inspection proves that the pinned CPython runtime, backend,
      vendor application, and locked runtime dependencies are present while
      model weights and caches are absent.
- [ ] Packaging and release jobs fail when the executable, backend, runtime, or
      required manifest is absent.
- [ ] Security tests cover hostile SVG, external-origin fetch/EventSource calls,
      secret redaction/transport, and executable model-pack integrity.
- [ ] Load and lifecycle tests demonstrate bounded concurrent work, cancellation,
      clean shutdown, import rollback, and no orphan processes.
- [ ] Data-path tests cover a read-only install directory and verify all mutable
      data lands in the resolved writable location.
- [ ] PR CI runs the cross-layer and desktop quality gates, including formatting
      and lint checks.
- [ ] One authoritative version is reflected in Python, npm, Cargo, Tauri,
      changelog, artifact names, and both READMEs.

## Out of Scope

- Bundling or redistributing third-party SAM3/RMBG model weights.
- macOS or Linux installer support in this hardening program.
- Replacing the existing vendor editor with a new frontend framework.
- New figure-generation capabilities unrelated to release correctness.
- Claiming production readiness from the first Safe Windows Beta milestone.

## Notes

- This is a parent task. Independently verifiable implementation areas should
  become child tasks after the milestone scope is decided.
- No implementation begins until design/implementation artifacts and child task
  boundaries are reviewed and explicitly approved.
- Milestone decision recorded 2026-07-31: Safe Windows Beta first, with full
  audit closure in follow-up child tasks.
- Runtime decision recorded 2026-07-31: ship a self-contained Runtime Directory
  with CPython and all application dependencies; exclude only model weights and
  caches from the application runtime.
