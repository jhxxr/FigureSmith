# Safe Beta Runtime Integration Design

## Component boundaries

### Outer ASGI application

`create_production_app(vendor_app=None)` owns the process-facing FastAPI app.
It installs, in order:

1. authentication and shared response middleware;
2. public liveness plus authenticated desktop readiness;
3. FigureSmith model, system, onboarding, UI, and bridge routes;
4. the vendor FastAPI app mounted at `/` as the last fallback.

The vendor app remains responsible for its generation APIs and static UI.
FigureSmith does not mutate its route array or rely on private Starlette route
insertion. Tests inject a small vendor app into the same factory.

`/healthz` means the server loop is alive. `/api/desktop/ready` requires the
session and confirms that owned routers and the vendor mount are present. Rust
navigates only after the latter succeeds.

### Desktop window lifecycle

The Tauri configuration creates only a bundled local splash. Setup starts the
sidecar on a worker and retains UI responsiveness. After authenticated
readiness, Rust performs this sequence atomically from the user's perspective:

1. register the exact dynamic capability;
2. build remote `main` with the initialization script and navigation policy;
3. show `main` after its first valid page is ready;
4. close the splash;
5. begin monitoring the backend child.

Any failure before step 4 leaves the local splash able to display a bounded,
redacted startup error and trigger cleanup.

### Capability contract

`build.rs` declares the four custom commands through Tauri `AppManifest` so
generated permissions exist. The local static capability does not grant those
commands to arbitrary remote origins.

After the actual port is known, Rust builds a runtime capability with:

- identifier unique to this process;
- `local(false)`;
- window/webview label `main`;
- exact remote URL `http://127.0.0.1:<port>/*`;
- only the four custom allow permissions.

The remote page receives no broad core/plugin defaults. Rust commands may
internally use dialog/opener plugins while page JavaScript cannot call them
directly.

Navigation permits bundled splash URLs before remote-window creation and the
exact API origin for `main`. Other top-level navigation and child-window
creation are rejected or opened through a Rust-owned external-browser policy.

### Document-start session bootstrap

The initialization script is generated from validated Rust values, with JSON
serialization rather than string interpolation. On every document it first
requires a top-level frame and exact scheme/host/port. It then installs a frozen
desktop bootstrap with token state kept in a closure.

The bootstrap wraps API fetch/EventSource before vendor scripts run. The
security child owns the complete URL and request-semantics implementation, but
this child proves that the first request cannot precede session installation.
The old `PageLoadEvent::Finished` injection and remote `get_session` command are
removed.

### Sidecar state machine

```text
NotStarted
    |
    v
Pending(child + cleanup guard + cancellation)
    | ready/authenticated          | exit/timeout/cancel/auth failure
    v                              v
Running(SidecarState)          Reaped -> Failed
    | expected shutdown            | unexpected exit
    v                              v
Stopping -> Reaped             Close main -> Reaped -> Exit app
```

Immediately after spawn, `PendingSidecar` owns the child and Windows process
tree. Its drop/abort path kills the tree and waits for the direct child. Each
readiness iteration calls `try_wait` before HTTP polling. Error messages include
bounded exit/readiness context but never the session token or child environment.

On successful readiness, ownership transfers exactly once to `SidecarState`.
Cleanup is guarded so multiple window/app events cannot race double shutdown.
Because dynamic capabilities cannot be revoked selectively, unexpected child
loss exits the desktop instead of hot-restarting on another port.

## Data flow

```text
Rust creates port + token
  -> spawn backend with token in environment
  -> public liveness
  -> authenticated desktop readiness
  -> exact dynamic capability
  -> remote webview + document-start private session
  -> first HTML/page API request
```

The long-lived token is never returned by a command, placed in the URL, stored
in web storage, or logged. The security child may mint a short-lived,
stream-scoped ticket for EventSource compatibility and must redact it from
logs; it is never accepted as a general API credential.

## Compatibility

- Vendor route paths and response bodies remain unchanged.
- Direct browser development can still load the backend; native-only actions
  remain unavailable and must show existing web fallbacks.
- The packaged-runtime resolver is not introduced here. Existing development
  Python discovery remains until the Windows runtime child replaces release
  behavior.

## Failure and rollback

- Composition can be reverted independently because the vendor app remains
  intact behind one mount.
- Splash stays local and functional on startup failure; no remote error page is
  trusted to report capability/bootstrap failure.
- All post-spawn errors converge on one process cleanup path.
- A feature cannot fall back from authenticated readiness to public liveness.

## Residual risks

- Same-origin renderer compromise can access its own authorized APIs; SVG and
  bridge hardening are required next.
- Active generation cancellation remains forceful at this stage; graceful job
  settlement belongs to the lifecycle child.
- Future vendor lifespan hooks require explicit composition tests.
