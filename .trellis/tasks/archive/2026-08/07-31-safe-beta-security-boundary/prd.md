# Safe Beta Security Boundary

## Goal

Prevent untrusted generated content and webview/provider networking from
crossing the desktop trust boundary. A Safe Beta must not execute hostile SVG,
leak its desktop session, or claim strict offline while making implicit remote
requests.

## Background

- Generated SVG is only checked for XML syntax
  (`vendor/autofigure_edit/autofigure2.py:2623`) and is served from the app
  origin (`vendor/autofigure_edit/server.py:442`).
- The desktop bridge authenticates by path without checking origin
  (`apps/backend/figuresmith/static/desktop-bridge.js:27`). A browser probe
  confirmed a bearer token on an external `/api/*` request.
- EventSource places the session token in a query string.
- Strict-offline validation occurs before default provider/image URLs are fully
  resolved, so later code can still reach the network.

## Dependencies

Depends on `07-31-safe-beta-runtime-integration` for the outer application,
exact sidecar origin, private document-start bootstrap, and authenticated
readiness contract. It may develop sanitizer tests in parallel, but integration
must target that finalized session interface.

## Requirements

### R1. One fail-closed SVG boundary

- Every generated/imported/history SVG must pass one bounded sanitizer before
  preview, edit, PNG render, inline response, or download.
- Parsing must disable network, DTD, external entities, and unbounded expansion;
  input bytes, nodes, nesting depth, and attribute length must be bounded.
- Element, attribute, namespace, URI, and CSS allowlists must reject scripts,
  event handlers, active embedding, external references, and unsupported data.
- Sanitization failure must return stable `UNSAFE_SVG_CONTENT` behavior. No code
  path may fall back to the raw artifact.
- Legal scientific SVG fixtures must retain paths, text, gradients, clipping,
  fragment references, and supported embedded raster images.
- Artifact responses must use isolation headers and no alternate raw static path.

### R2. Exact-origin credential transport

- Fetch and EventSource authentication must require exact match with the
  sidecar API origin, including scheme, host, and port, plus an `/api/` path.
- Same-host different-port, `localhost` substitution, protocol-relative,
  credential-bearing, non-loopback, and external URLs must never receive a
  session credential.
- Wrapped `Request` behavior must preserve method, body, headers, credentials,
  signal, and error semantics.
- The bearer token must remain private, must not be returned by a command, and
  must be redacted from errors/access logs. Any temporary SSE query credential
  must be exact-origin, narrowly scoped, and redacted.

### R3. Effective strict-offline enforcement

- Validation must run after provider defaults and redirects are resolved.
- Strict mode must reject cloud providers, public endpoint fallbacks, remote
  response assets, and external redirects before any network request.
- UI/system status must report the effective boolean correctly, including
  explicit false.
- Tests must use network canaries to prove zero non-loopback requests.

## Acceptance Criteria

- [ ] Hostile SVG fixtures cover script, events, `foreignObject`, DTD/entities,
      external image/font/CSS URLs, `file:`, `javascript:`, deep nesting, and
      oversized input; none execute or make a network request.
- [ ] A legal SVG compatibility corpus survives sanitization and can be edited,
      previewed, and rendered to PNG.
- [ ] A malicious pre-upgrade history artifact is blocked at the HTTP boundary.
- [ ] Artifact responses include sandboxed CSP and `nosniff`; downloads use
      attachment disposition and no raw bypass route exists.
- [ ] Relative and exact-origin API calls authenticate, while same-host
      different-port and external fetch/EventSource canaries receive no token.
- [ ] Cold load, reload, and navigation produce no anonymous API request.
- [ ] Strict offline with omitted/default provider URLs produces no external
      DNS/HTTP attempt and reports its actual state.

## Out of Scope

- Cryptographic signing and full integrity verification of executable model
  packages; owned by the lifecycle child.
- General browser sandboxing of all same-origin application JavaScript.
- Rich queue/cancel UI and crash recovery.
- Provider-key/method-content transport out of child argv, bounded uploads, and
  the remaining filesystem request hardening; owned by the backend lifecycle
  hardening child.
- TLS for the ephemeral loopback server.

## Technical Notes

- The sanitizer must use structured XML/CSS parsers, not regular-expression
  replacement.
- Same-origin renderer code remains trusted application code; this child closes
  known untrusted SVG and remote-network entry points, not every future XSS.
