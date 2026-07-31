# Safe Beta Runtime Integration

## Goal

Make the production vendor-backed backend and Tauri shell function as one
authenticated application. Welcome, Models, vendor APIs, native model commands,
and shutdown must be reachable on first load without route interception,
anonymous-request races, or leaked sidecar processes.

## Background

- FigureSmith routers are currently appended after the vendor root static mount
  (`apps/backend/main.py:91`, `vendor/autofigure_edit/server.py:808`). In the
  actual app, model/system routes return 404 and shutdown returns 405.
- The remote loopback page has no remote Tauri capability
  (`apps/desktop/src-tauri/capabilities/default.json:5`).
- Session injection occurs at `PageLoadEvent::Finished`, after initial API
  requests (`apps/desktop/src-tauri/src/lib.rs:29`). A browser probe observed a
  first-request 401 and no UI recovery.
- Sidecar readiness can wait the full timeout after early child exit and can
  return after spawn without reclaiming the process
  (`apps/desktop/src-tauri/src/sidecar.rs:122`).

## Dependencies

This is the first implementation child and has no implementation dependency.
It establishes the production app factory, exact API origin/session contract,
dynamic Tauri permission contract, and sidecar ownership contract consumed by
the security, writable-data, and Windows runtime children.

## Requirements

### R1. Deterministic production composition

- A FigureSmith-owned outer FastAPI app must register authentication,
  FigureSmith routes, and desktop readiness before mounting the vendor app at
  `/` as the final fallback.
- The production factory must accept a vendor app override for tests without
  using a test-only route order.
- Public liveness and authenticated desktop readiness must be distinct. Desktop
  startup may navigate only after authenticated readiness succeeds.
- Vendor UI/API behavior and URLs must remain compatible.

### R2. Exact runtime Tauri capability

- Only the four native model commands may be callable from the remote page:
  `import_sam3_model`, `import_rmbg_archive`, `import_rmbg_folder`, and
  `open_models_directory`.
- After sidecar readiness, Rust must register a dynamic capability for only the
  main webview and exact `http://127.0.0.1:<actual-port>/*` origin.
- A wildcard port, `core:default`, direct dialog/opener permissions,
  `get_session`, and unrelated commands must not be available remotely.
- Navigation and new-window behavior must fail closed outside the approved
  origin.

### R3. Session before page code

- The bundled window is a local startup/splash surface. Rust creates the remote
  main webview only after readiness and capability registration.
- A document-start initialization script must install the exact API base and
  bearer handling before any application script, fetch, or EventSource runs.
- The script must apply only to the top-level exact-origin document and must run
  on reload/navigation.
- The long-lived session bearer must not be exposed through a public native
  getter, persistent browser storage, URL, or log. A security-scoped, short-lived
  SSE ticket is the only allowed URL credential and must be redacted.

### R4. Sidecar startup and loss handling

- Python ownership must begin immediately after spawn through an RAII-style
  pending guard.
- Readiness polling must detect early child exit, timeout, cancellation, and
  authentication failure, then kill and reap the process tree.
- Ownership transfers to application state only after authenticated readiness.
- Unexpected backend exit after readiness must close the remote webview and
  terminate the desktop process so an old capability cannot be reused against a
  new listener on the same origin.
- Cleanup is idempotent and leaves no FigureSmith-owned child after forced exit.

## Acceptance Criteria

- [ ] Under the real vendor-backed factory, authenticated `/api/models`,
      `/api/system/status`, `/api/config`, and `POST /api/shutdown` succeed;
      missing/invalid authentication receives 401.
- [ ] `/welcome.html`, `/models.html`, and vendor `/` all succeed, and the final
      parent route is the vendor root mount.
- [ ] Playwright proves the first Welcome, Models, and vendor API calls are
      authenticated, with no transient 401, 404, or 405.
- [ ] A Windows Tauri integration check proves exactly four model commands are
      available and `get_session`, direct dialog/opener, and an unknown command
      are rejected.
- [ ] The capability matches the actual port; same-host different-port and
      non-loopback navigation are denied.
- [ ] Fake sidecars that exit immediately, never become ready, or fail
      authentication all fail promptly and have their process/PID reclaimed.
- [ ] Unexpected sidecar loss after readiness closes the remote page and exits
      instead of attempting an in-process hot restart.
- [ ] Existing Python, frontend, Rust, and production-composition tests pass.

## Out of Scope

- SVG sanitization and exact-origin fetch/EventSource wrapping beyond the
  document-start bootstrap; owned by the security child.
- Packaged CPython/runtime discovery; owned by the Windows runtime child.
- Mutable data migration; owned by the writable-data child.
- Rich job queueing, cancellation UX, crash recovery, and graceful settling of
  active generation; owned by the lifecycle child.

## Technical Notes

- Tauri 2.11.5 supports runtime `Manager::add_capability` and
  `ipc::CapabilityBuilder`; the exact runtime port can therefore be authorized
  without a static wildcard.
- Dynamic capabilities are additive. The no-hot-restart rule is required to
  avoid retaining authority for a dead sidecar origin.
- If the vendor app later gains a lifespan, the outer factory must explicitly
  compose it; mounting alone must not silently skip required startup/shutdown.
