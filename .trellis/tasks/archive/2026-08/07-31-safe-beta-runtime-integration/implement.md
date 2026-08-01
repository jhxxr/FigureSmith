# Safe Beta Runtime Integration Implementation Plan

## Ordered checklist

### 1. Production app factory

- [x] Add focused failing tests against the real vendor-backed factory.
- [x] Create the outer FastAPI app and move authentication/owned routers to it.
- [x] Mount the vendor app at `/` last and remove private route reordering.
- [x] Add authenticated `/api/desktop/ready` and structural readiness checks.
- [x] Verify vendor `/api/config`, static UI, FigureSmith APIs, and auth failures.

### 2. Sidecar ownership

- [x] Refactor spawn into `PendingSidecar` with idempotent tree cleanup.
- [x] Check `try_wait` during readiness and report early exit promptly.
- [ ] Add cancellation for splash close/application exit during startup.
- [x] Transfer child ownership only after authenticated readiness.
- [x] Monitor ready-sidecar exit and close `main` before application exit.
- [x] Add a cross-platform short-lived-child regression for unexpected
      post-ready loss; full startup fake-child matrix remains below.
- [ ] Add fake-child tests for immediate exit, timeout, auth failure, success,
      and cancellation.

### 3. Tauri command manifest and dynamic ACL

- [x] Declare exactly four custom commands in the Tauri app manifest.
- [x] Keep the bundled static capability local-only and remove remote
      `get_session` exposure.
- [x] Register a process-unique capability for exact port and `main` only.
- [x] Add exact-origin navigation and new-window denial.
- [ ] Add negative ACL checks for wildcard/different port and unrelated commands.

### 4. Remote webview bootstrap

- [x] Configure/create a local splash rather than navigating an existing window.
- [x] Serialize API base and token safely into a document-start script.
- [x] Require top-level exact origin and keep token state private.
- [x] Create/show remote `main` only after readiness and ACL registration.
- [x] Remove `PageLoadEvent::Finished` injection.
- [ ] Verify reload/back/forward keep first-request authentication.

### 5. Cross-layer validation

- [x] Run focused production-composition pytest tests.
- [ ] Run bridge/browser cold-load Playwright coverage.
- [x] Run Rust unit tests for sidecar state and capability construction.
- [ ] Run a Windows Tauri smoke for positive and negative native invokes.
- [x] Run full Python, frontend, Rust format/lint/test baselines.

## Validation commands

```powershell
python -m pytest tests -q
npm --prefix apps/desktop run build
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --check
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets --locked -- -D warnings
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml --locked
```

Focused test names should cover production app composition, authentication,
sidecar pending/running transitions, exact runtime capability, document-start
ordering, and first-request browser behavior.

## Risky files

- `apps/backend/main.py`: application ownership and route precedence.
- `apps/backend/figuresmith/runtime/auth.py`: parent-app middleware behavior.
- `apps/desktop/src-tauri/build.rs`: generated custom-command permissions.
- `apps/desktop/src-tauri/src/lib.rs`: splash/main construction and lifecycle.
- `apps/desktop/src-tauri/src/sidecar.rs`: child ownership and cleanup.
- `apps/desktop/src-tauri/capabilities/*.json`: local static capability.
- `apps/desktop/src/main.ts`: existing navigation/bootstrap behavior.

The security child follows this work in the bridge file; avoid completing its
URL-policy refactor here beyond the minimum document-start interface contract.

## Rollback points

- Land backend factory/tests before desktop lifecycle changes.
- Land sidecar state/cleanup before dynamic ACL and remote window creation.
- Keep splash errors local so an incomplete remote bootstrap cannot hide
  sidecar cleanup failures.
- Do not retain compatibility fallback to the old Finished-event token path.

## Pre-start checks

- [x] Parent final plan has fresh user approval.
- [x] This PRD/design/implementation plan is unchanged since approval.
- [x] Both context manifests contain real research entries.
- [x] `task.py validate` passes.
