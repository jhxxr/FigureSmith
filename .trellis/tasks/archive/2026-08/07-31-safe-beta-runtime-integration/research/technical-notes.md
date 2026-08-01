# Runtime Integration Technical Notes

## Verified defects

- `apps/backend/main.py:91` includes FigureSmith routes after the vendor app has
  mounted `StaticFiles` at `/` in `vendor/autofigure_edit/server.py:808`.
- Real HTTP probes returned 404 for model/system routes and 405 for shutdown
  while vendor health remained successful.
- `apps/desktop/src/main.ts:57` navigates to a dynamic loopback origin, but
  `apps/desktop/src-tauri/capabilities/default.json:5` is local-only.
- `apps/desktop/src-tauri/src/lib.rs:29` injects the token after page load; page
  code issues initial requests earlier.
- `apps/desktop/src-tauri/src/sidecar.rs:122` can lose cleanup ownership between
  spawn and final state construction.

## Selected design

1. Create a FigureSmith outer ASGI application, register owned middleware and
   routes, and mount the vendor application at `/` last.
2. Add authenticated `/api/desktop/ready`; retain public `/healthz` as liveness.
3. Use a local splash while the sidecar starts.
4. After authenticated readiness, dynamically register a capability scoped to
   the main label, exact runtime origin, and four generated command permissions.
5. Create the remote main webview with a document-start initialization script.
6. Use a pending sidecar guard until readiness, then transfer ownership to
   application state. Exit the desktop if the ready sidecar is lost.

## Tauri references

- Runtime capability registration:
  https://docs.rs/tauri/latest/tauri/trait.Manager.html#method.add_capability
- Capability builder:
  https://docs.rs/tauri/latest/tauri/ipc/struct.CapabilityBuilder.html
- Document-start initialization script:
  https://docs.rs/tauri/latest/tauri/webview/struct.WebviewWindowBuilder.html#method.initialization_script

On Windows the initialization script also runs in child frames, so it must
verify `window.top === window` and exact `location.origin` before activating.

## Test constraints

- Tests must instantiate the same production factory used by Uvicorn.
- ACL tests must include negative commands and a same-host different-port URL.
- Startup tests need fake child processes for immediate exit, timeout, invalid
  readiness, successful transfer, and loss after readiness.
- Browser assertions must count initial 401/404/405 responses, not only the
  final visible UI state.
