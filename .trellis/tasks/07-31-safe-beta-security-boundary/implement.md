# Safe Beta security boundary implementation plan

## Start Gate

- [x] Confirm `07-31-safe-beta-runtime-integration` has implemented and tested
      the production composition and authenticated bootstrap contract described
      in `design.md`.
- [x] Confirm the runtime contract provides one canonical loopback `apiBase`, a
      Rust-private token before navigation, an exact dynamic capability, and a
      document-start initialization script on every remote navigation.
- [x] Re-read `prd.md` and `design.md` after the upstream task lands; update this
      plan if its public DTO or hook name differs, then obtain fresh planning
      approval before `task.py start`.
- [x] Confirm `07-31-safe-beta-windows-runtime` records this task as a release
      gate and will not publish or label a Beta artifact early.

## 1. Establish SVG Fixtures And Sanitizer Contract

- [ ] Add hostile fixtures for script, all `on*` attributes, foreign content,
      external and obfuscated URLs, CSS loading, unsafe schemes, DTD/entities,
      oversized data URI, excessive depth, excessive nodes, and long attributes.
- [ ] Add compatibility fixtures covering the SVG shapes, text, transforms,
      gradients, markers, clipping, local references, inline presentation, and
      embedded raster data used by scientific figures.
- [ ] Add tests for stable `UNSAFE_SVG_CONTENT` categories and redacted errors.
- [ ] Implement one `figuresmith.security` sanitizer with hardened parser,
      explicit resource limits, element/attribute/URL allowlists, structured
      inline CSS parsing, and deterministic serialization.
- [ ] Declare any structured CSS parser as a direct backend runtime dependency
      and notify the Windows runtime task that it must be present in artifacts.
- [ ] Reparse the serialized result and return only a distinct sanitized value.

Rollback point: the helper and tests are isolated; revert them together if the
contract is wrong. Do not add a temporary bypass.

## 2. Wire Every SVG Sink

- [ ] Sanitize after LLM extraction and after optimizer output, before saving or
      invoking CairoSVG.
- [ ] Ensure generation failures surface `UNSAFE_SVG_CONTENT` without including
      raw SVG in logs.
- [ ] Route both current and historical SVG artifact responses through the same
      sanitizer, including artifacts written by older releases.
- [ ] Return sanitized bytes with SVG-specific CSP and nosniff headers; use an
      attachment disposition for download behavior.
- [ ] Verify no alternate output/static route can return the raw SVG.
- [ ] Replace the canvas object fallback with an image fallback and verify
      SVG-Edit receives only a sanitized response body.
- [ ] Add API and browser regressions for historical malicious artifacts,
      response headers, editor load, PNG rendering, and zero outbound loads.

Rollback point: hold the release and revert the complete sink integration if a
served path bypasses the helper. Do not leave generation-only sanitization.

## 3. Make Bridge Credential Attachment Exact-Origin

- [ ] Refactor the bridge around one URL-normalization and exact-origin
      predicate shared by fetch and EventSource.
- [ ] Cover string, `URL`, and `Request` inputs; preserve Request body, signal,
      credentials, method, cache, redirect, referrer, and caller headers.
- [ ] Pass malformed, external, host-alias, and same-host/different-port URLs
      through without any Authorization header or query token.
- [ ] Store token and allowed origin only in bridge closure state and remove
      token reads from shared frontend helpers.
- [ ] Remove remote session-token commands and splash/global token propagation.
- [ ] Require top-level exact origin before the initialization script activates
      and keep the token only in its closure.
- [ ] Add deterministic JavaScript tests using mocked fetch/EventSource and Rust
      tests for public-session serialization and injection rejection.

Rollback point: bridge, public session DTO, Rust injection, and their tests form
one atomic compatibility change. Do not restore path-only matching.

## 4. Prove Document-Start Authentication

- [ ] Install the bridge wrapper through the runtime child's document-start
      initialization script before application scripts.
- [ ] Begin a valid Tauri page in desktop-ready state; reject malformed, framed,
      or origin-mismatched bootstrap locally with `AUTH_BOOTSTRAP_FAILED`.
- [ ] Keep auth-disabled ordinary browser mode non-blocking.
- [ ] Audit every EventSource and direct API call site for wrapper coverage.
- [ ] Remove any anonymous-first/401-retry behavior.
- [ ] Test immediate Models refresh, Welcome, History, Canvas, reload, and
      forward/back navigation.
- [ ] Run the upstream production-composition cold-start smoke and record that
      the first `/api/*` request contains Bearer auth with zero preceding API
      traffic and zero 401 responses.

Rollback point: do not publish the Windows artifact if readiness fails. Restore
the last complete desktop build rather than allowing anonymous bootstrap.

## 5. Enforce Effective Strict Offline

- [ ] Normalize provider aliases, defaults, endpoint URLs, and redirects before
      the outbound policy makes its decision.
- [ ] Reject cloud providers, public fallbacks, remote redirects, and
      provider-returned remote assets in strict mode before DNS/socket use.
- [ ] Correct status parsing so explicit false remains false.
- [ ] Add runtime network canaries for omitted URLs, redirects, and remote image
      responses; do not rely on source-text assertions.

Rollback point: keep the outbound gate centralized. Do not restore a mode that
claims strict offline while allowing default or follow-up remote requests.

## 6. Validation

Run focused tests while iterating, then every full-scope command before review.

```powershell
$env:PYTHONPATH='apps/backend;vendor/autofigure_edit'
$env:FIGURESMITH_DISABLE_AUTH='1'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -q -p no:cacheprovider --basetemp "$env:TEMP\figuresmith-security-pytest"
node --test apps/desktop/tests/desktop-bridge.test.mjs
npm --prefix apps/desktop run build
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml -- --check
cargo clippy --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```

- [ ] Run the runtime-integration task's production composition smoke in
      addition to the commands above.
- [ ] Capture browser/Tauri request traces for cold start and navigation; assert
      exact-origin auth, zero pre-session API traffic, zero 401, and no external
      SVG loads.
- [ ] Search all artifact response, SVG render, fetch, EventSource, session DTO,
      and page-load injection call sites for bypasses.
- [ ] Inspect logs and error bodies to confirm they contain neither session/API
      tokens nor hostile SVG bodies.
- [ ] Run `git diff --check` and verify the dirty-file list contains only this
      task's intended implementation and tests.

## 7. Review And Downstream Handoff

- [ ] Have the check pass compare every acceptance criterion in `prd.md` to a
      named automated test or recorded composed-app smoke assertion.
- [ ] Verify the sanitizer and origin predicate each have one implementation
      owner; reject duplicated validation logic.
- [ ] Confirm API-key argv transport, job queue/cancellation/shutdown, and model
      supply-chain work remain explicitly tracked as follow-ups rather than
      being partially refactored here.
- [ ] Notify `07-31-safe-beta-windows-runtime` that the security gate passed only
      after the final full-scope validation is green.
- [ ] Do not mark the parent release hardening task complete; this child closes
      only the SVG/session boundary.

## Evidence (2026-08-01)

- `247` Python tests pass; desktop TypeScript/Vite build, Rust fmt/clippy/test,
  and context validation pass.
- `npm --prefix apps/desktop run test:bridge` passes 3 behavior tests against
  the Rust document-start template: exact-origin Bearer, Request preservation,
  and scoped `fs_ticket` EventSource behavior.
- A local browser cold load plus reload of `/welcome.html` reached only
  `127.0.0.1` resources and `/api/system/status` (200); no external or
  cross-port request was observed.
- The external SAM3 checkpoint was read-only validated through the registry:
  `G:\0JHX-code\Project\FigureSmith-model\sam3.pt`, `3,450,062,241` bytes.
- Remaining release gate: Tauri/WebView production cold-start trace with auth
  enabled, and socket-level strict-offline canaries for omitted defaults,
  redirects, and provider-returned assets.

## Risky Surfaces

- `vendor/autofigure_edit/autofigure2.py`: generation and rasterization order.
- `vendor/autofigure_edit/server.py`: current/history artifact egress.
- `vendor/autofigure_edit/web/app.js` and `canvas.html`: editor and fallback
  rendering sinks plus EventSource timing.
- `apps/backend/figuresmith/static/desktop-bridge.js` and UI API helpers:
  credential scope and readiness.
- `apps/desktop/src-tauri/src/lib.rs`, `commands.rs`, and `apps/desktop/src/main.ts`:
  private/public session split and navigation injection timing.

Changes across these surfaces must be reviewed as one cross-layer contract even
when committed in staged implementation batches.
