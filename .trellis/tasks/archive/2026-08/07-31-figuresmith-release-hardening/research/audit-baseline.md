# Release Hardening Audit Baseline

## Scope decisions

- The first milestone is a Safe Windows Beta, followed by broader hardening.
- Setup and Portable must each ship a self-contained runtime directory.
- The runtime includes pinned CPython and all application dependencies,
  including pinned SAM3 application code.
- Model weights and model caches are never bundled.
- The Beta may still require a compatible Windows/NVIDIA driver. It may not
  require a source checkout, system Python, pip, or an online dependency
  installation.

## Verified baseline

The following commands passed during the 2026-07-31 audit:

- `python -m pytest tests -q`: 214 passed, 1 warning.
- `npm run build`: passed.
- `cargo check --locked`: passed.
- `cargo test --locked`: 3 passed.

The following quality checks did not pass:

- `cargo fmt --check` reports formatting drift.
- `cargo clippy --all-targets --locked -- -D warnings` reports six errors.

The passing unit suites do not exercise the actual packaged application
composition. Browser and HTTP probes against the vendor-backed entry point
confirmed the critical failures below.

## Safe Beta blockers

### Production application composition

- FigureSmith routers are included after the vendor root catch-all in
  `apps/backend/main.py:91` and
  `vendor/autofigure_edit/server.py:808`.
- In the real app, `/api/models` and `/api/system/status` return 404, while
  `POST /api/shutdown` returns 405. `/healthz` still returns success, so the
  existing health check cannot detect the broken application surface.
- The repair must be proven through the production assembly, not a test-only
  FastAPI fixture.

### Tauri access and authentication timing

- The desktop navigates to a dynamic loopback URL in
  `apps/desktop/src/main.ts:57`.
- `apps/desktop/src-tauri/capabilities/default.json:5` grants no remote URL
  access, so the remote page cannot use the native model commands under the
  pinned Tauri version.
- Rust injects the session after `PageLoadEvent::Finished` in
  `apps/desktop/src-tauri/src/lib.rs:29`, but page scripts make API requests
  during initial load. A real browser run observed an initial 401 and a UI that
  did not recover.

### Runtime and packaging contract

- `apps/desktop/src-tauri/src/sidecar.rs:46` requires a source-style
  `apps/backend/main.py` tree.
- `apps/desktop/src-tauri/tauri.conf.json` does not bundle the Python runtime,
  backend, or vendor tree.
- `scripts/build-desktop.ps1:93` copies only the executable, documentation, and
  developer scripts. Its runtime layout does not match the sidecar resolver.
- `scripts/build-desktop.ps1:104` can create a successful placeholder Portable
  archive when no executable exists. The release workflow can upload it.
- The existing ignored Portable archive is about 15 KiB, contains
  `BUILD_INSTRUCTIONS.txt`, and contains no executable.

### Untrusted content and session credentials

- Generated SVG receives only XML syntax validation in
  `vendor/autofigure_edit/autofigure2.py:2623` and can be served from the
  authenticated application origin by
  `vendor/autofigure_edit/server.py:442`.
- Script, event handlers, `foreignObject`, external references, and CSS URL
  loading are therefore part of the current attack surface.
- `apps/backend/figuresmith/static/desktop-bridge.js:27` decides whether to
  attach the bearer token by pathname only. A browser probe showed that an
  external URL ending in `/api/...` receives the token.
- Provider secrets and method text are passed in generation child argv at
  `vendor/autofigure_edit/server.py:244` and
  `vendor/autofigure_edit/server.py:262`.
- The declared strict-offline mode validates explicit request URLs but later
  provider defaults and returned image URLs can still reach the network
  (`vendor/autofigure_edit/autofigure2.py:133`,
  `vendor/autofigure_edit/autofigure2.py:564`).

### Writable data and process ownership

- The desktop sets an executable-adjacent data directory in
  `apps/desktop/src-tauri/src/sidecar.rs:89`.
- `apps/backend/figuresmith/models/paths.py:74` returns that explicit path even
  when its writability probe fails. A Program Files install can therefore fail
  only when onboarding or model import attempts a write.
- Uploads and outputs remain rooted in the vendor source tree at
  `vendor/autofigure_edit/server.py:25`.
- Sidecar startup can return after spawning Python without owning cleanup, and
  the health loop does not stop early when the child exits
  (`apps/desktop/src-tauri/src/sidecar.rs:122`).
- `/api/shutdown` calls `os._exit` in
  `apps/backend/figuresmith/api/system_routes.py:308`. Generation children are
  started independently in `vendor/autofigure_edit/server.py:371`, so graceful
  shutdown does not currently own the full process tree.

## Follow-up hardening findings

### Job and model lifecycle

- `/api/run` launches unbounded heavyweight child processes and has no cancel
  endpoint (`vendor/autofigure_edit/server.py:184`).
- Large model imports are synchronous while the desktop has a fixed 120-second
  timeout (`apps/desktop/src-tauri/src/commands.rs:23`).
- Model managers and settings updates have no process-wide lock or transaction
  journal.
- Directory import has no complete byte/file/depth bound
  (`apps/backend/figuresmith/models/import_rmbg.py:283`).
- Installed, verified, and runtime-loaded states are conflated.
- RMBG may execute local Python through `trust_remote_code=True`, while the
  release model manifest has null integrity pins
  (`resources/model-manifest.json:36`).

### Release quality and consistency

- Standard CI does not run the frontend build, Rust checks, composed backend,
  Tauri checks, or unpacked artifact smoke (`.github/workflows/ci.yml:21`).
- Python runtime dependencies are range-based and the backend package metadata
  does not declare the full shipped dependency set.
- Product versions diverge: authoritative/Python/Tauri are 0.6.0, npm/Cargo
  are 0.4.0, and the changelog begins with 0.6.1.
- English and Chinese documentation disagree about the current phase and
  distribution status. `docs/development.md` contains a literal NUL byte.
- Packaging tests exercise a helper rather than the production PowerShell
  assembly path.

## Architecture constraints established by evidence

1. Compose a FigureSmith-owned outer ASGI application and mount the vendor app
   as the final `/` fallback. Do not rely on appending routes after its static
   catch-all.
2. Grant the remote loopback page only named FigureSmith native commands and
   only for the main webview label and loopback URL pattern.
3. Establish a document-load authentication barrier before page code can send
   API requests, and compare exact origins before attaching credentials.
4. Sanitize SVG at creation and again at the HTTP artifact boundary so legacy
   files cannot bypass the policy.
5. Use one immutable runtime schema for Runtime, Setup, Portable, and sidecar
   resolution. Release mode must never fall back to PATH Python or repo paths.
6. Build the runtime from exact, hashed inputs and assemble it offline. The
   target machine performs no pip installation.
7. Keep every mutable path outside the immutable install/runtime payload.
8. A Windows process-tree ownership mechanism must guarantee cleanup even when
   graceful application shutdown fails.

## External technical references

- Tauri capabilities and remote URL grants:
  https://v2.tauri.app/security/capabilities/
- Tauri packaged resources:
  https://v2.tauri.app/develop/resources/
- CPython embeddable distribution:
  https://docs.python.org/3.12/using/windows.html#the-embeddable-package
- pip hash-checking and offline installs:
  https://pip.pypa.io/en/stable/topics/secure-installs/
- Tauri Windows installer modes:
  https://v2.tauri.app/distribute/windows-installer/

## Risks to measure during implementation

- CPython 3.12 embeddable compatibility with native wheels and DLL discovery.
- The exact pinned PyTorch cu128/SAM3 dependency matrix and licenses.
- Full runtime compressed size, build time, and release-asset limits.
- Microsoft VC/UCRT and WebView2 behavior on a clean Windows runner.
- Tauri resource paths across raw executable, Portable, NSIS, and MSI layouts.
- Weight exclusion rules must distinguish forbidden model checkpoints from
  legitimate package files such as Python `.pth` path configuration files.
