# Safe Beta security boundary design

## Scope

This design establishes four linked controls:

1. one authoritative SVG sanitizer before every executable or browser sink;
2. one exact-origin rule for all desktop credential attachment; and
3. one document-start session protocol that prevents pre-session API traffic;
4. one effective strict-offline gate after provider defaults are resolved.

These controls are intentionally designed together. Exact-origin checks do not
protect a token from same-origin SVG script, and SVG sanitization alone does not
stop the bridge from attaching a token to an external `/api/` URL.

## Dependency Contract

`07-31-safe-beta-runtime-integration` is the upstream provider. Before this
task's integration phase starts, it must provide the following stable contract:

- the production app serves FigureSmith API/static routes before the vendor
  catch-all;
- one non-empty random session token is installed in backend auth before the
  sidecar accepts production UI work;
- Rust owns a canonical `http://127.0.0.1:<port>` `apiBase` and the private
  token before navigating the webview;
- Rust creates the remote webview with a document-start initialization script
  containing the canonical origin and private session; and
- Tauri dynamically grants only the intended commands to the exact sidecar
  origin and main webview.

This task consumes that contract and owns the bridge closure, origin
validation, strict-offline gate, and first-request proof. It does not redesign route
composition. `07-31-safe-beta-windows-runtime` is downstream: its artifact may
not be declared Beta until the controls here pass against the production app.

## Trust Boundaries And Data Flow

### SVG

```text
LLM / optimizer / historical file
              |
              v
       hardened XML parse
              |
              v
       allowlist sanitizer
              |
              v
       canonical safe bytes
          /          \
         v            v
   PNG renderer    stored artifact
                         |
                         v
                 egress sanitizer
                         |
                         v
              editor / preview / download
```

The egress check is authoritative even when generation already sanitized the
file. It protects artifacts created by older releases and catches accidental
future bypasses.

### Desktop session

```text
Rust-owned session
  -> exact-origin page-load check
  -> bridge private setter
  -> closure-held token + resolved readiness promise
  -> exact-origin fetch/EventSource decision
  -> authenticated loopback API
```

The splash receives only public readiness data (`port`, `apiBase`, `ready`). It
does not receive the token and does not attempt to carry JavaScript state across
the navigation.

## SVG Safety Boundary

### Single owner

Add a project-owned helper under `figuresmith.security`, reusable from both the
vendor pipeline and artifact routes. The primary API should operate on bytes
and return a distinct sanitized value or raise a typed error, for example:

```python
sanitize_svg(raw: bytes, *, limits: SvgLimits) -> SanitizedSvg
```

Do not implement separate generation and response sanitizers. Vendor code
already imports project-owned `figuresmith` helpers, so a shared module follows
the existing integration direction.

### Parser and resource limits

Use `lxml` with a parser configured to disable DTD loading, entity resolution,
network access, and recovery. Reject a DOCTYPE before normalization. Enforce
explicit byte, element-count, nesting-depth, attribute-count, and attribute-
length limits. Limit decoded raster data-URI bytes separately.

The exact limits should be constants with boundary tests. They should be large
enough for current generated figures but small enough that validation and
rasterization remain bounded. They must not be request-controlled.

### Allowlist policy

- Allow the SVG namespace and the static shape, grouping, text, definition,
  gradient, marker, clipping, and transform features covered by compatibility
  fixtures.
- Reject `script`, `foreignObject`, `iframe`, `object`, `embed`, animation, and
  other active or unknown elements.
- Reject all attributes whose local name starts with `on`.
- Allow `href`/`xlink:href` only for local `#fragment` references. A raster
  `<image>` may additionally use a size-limited base64 PNG, JPEG, or WebP data
  URI. Reject every other scheme, protocol-relative reference, and obfuscated
  control-character form.
- Reject `<style>` elements for the Beta boundary. Parse inline `style`
  declarations structurally with an explicit presentation-property allowlist;
  reject at-rules, parse errors, unknown properties, `url()`, `expression()`,
  and external references. Do not use regular-expression-only CSS filtering.
- If structured CSS parsing requires a library not already declared directly,
  add it to the backend runtime dependencies and require the Windows runtime
  artifact inspection to prove it is bundled. Do not rely on a transitive
  dependency that packaging may omit.
- Serialize from the sanitized tree, then parse the serialized result once more
  with the hardened parser before returning it.

If a required visual feature is rejected, add the smallest allowlist extension
and a hostile-neighbor regression test. Do not add a bypass or raw fallback.

### Sink integration

- Sanitize immediately after LLM extraction and after any optimizer that can
  introduce new markup, before saving or invoking CairoSVG.
- Store only sanitized SVG in served output directories. A diagnostic raw copy,
  if ever required, must live outside every HTTP-served tree and is not part of
  this Beta task.
- In both current and history artifact routes, detect SVG by resolved file type
  and sanitize on response. Do not rely only on the request suffix.
- For rejected generated content, fail the job with
  `UNSAFE_SVG_CONTENT` and a non-sensitive reason category. For rejected
  historical content, return HTTP 422 with the same stable code.
- Return sanitized SVG bytes rather than a raw `FileResponse`. Apply:

```text
Content-Type: image/svg+xml
Content-Security-Policy: sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'
X-Content-Type-Options: nosniff
```

- A download response additionally uses `Content-Disposition: attachment`.
- Replace the canvas `<object type="image/svg+xml">` fallback with an `<img>`
  path. SVG-Edit may receive only the sanitized response body.

## Exact-Origin Bridge

### Private session state

The bridge installs synchronously at document start and owns closure state:

```text
mode: browser | desktop-ready | failed
allowedOrigin: normalized origin or absent
token: private string or absent
ready: Promise<void>
```

Rust serializes `{apiBase, token}` into an initialization-script IIFE with JSON
encoding rather than source interpolation. The IIFE activates only when:

- `apiBase` parses as HTTP;
- hostname is exactly the supported loopback host (`127.0.0.1` for the current
  runtime contract);
- `window.location.origin === new URL(apiBase).origin`; and
- the port is explicit and valid.

After success, freeze `allowedOrigin`, retain the token only in the closure,
and resolve readiness before page code runs. Delete the public token-bearing
global contract and remove remote `get_session` access. The same bridge source
may load in ordinary browser mode without desktop session state.

### Request decision

Normalize string, `URL`, and `Request` input through `new URL(inputUrl,
window.location.href)`. Attach credentials only when both are true:

```text
candidate.origin === allowedOrigin
candidate.pathname === "/api" or starts with "/api/"
```

Parse failure is unauthenticated and fail-closed. Do not treat substring
matches as an API path. Do not consider `localhost`, another loopback spelling,
or another port equivalent to the canonical origin.

For a `Request`, create a new Request or equivalent merged init without
consuming the original body, and preserve method, signal, credentials, cache,
redirect, referrer, and existing headers. Add Authorization only when the
caller supplied neither case variant.

EventSource uses the identical origin predicate plus the narrower
`/api/events` prefix before adding `fs_token`. External and malformed URLs are
passed through unchanged. Replacing query-token SSE with header-capable fetch
streaming is a later hardening option, not required here.

### Rust-side defense

The initialization script must require `window.top === window` and compare the
document URL to the canonical sidecar origin before enabling authentication.
It must never install token state into a child frame or arbitrary page. The
remote webview navigation policy independently enforces the same origin.

## First-Request Authentication Protocol

The bridge is present before application scripts and immediately wraps fetch.
In a valid Tauri webview it begins in `desktop-ready`; in an ordinary browser it
begins in `browser` mode and does not wait for desktop state. An invalid desktop
bootstrap enters `failed` before any API call can be sent.

An exact-origin `/api` request may proceed only in `desktop-ready`. Failed or
missing desktop bootstrap rejects locally with `AUTH_BOOTSTRAP_FAILED` and sends
nothing. EventSource construction follows the same synchronous state check.
The previous post-`PageLoadEvent::Finished` injection is removed by the upstream
task and must not be reintroduced as a retry path.

The public frontend API helper must stop reading token-bearing global state.
All API call sites must use the wrapped fetch, and every EventSource constructor
must be audited. Bootstrap failure remains a blocking UI error; a 401 retry is
not a substitute for readiness.

## Effective Strict-Offline Gate

Provider aliases, default endpoint URLs, image endpoints, and redirect policy
are normalized before an outbound request is constructed. A central policy
receives the effective provider and final target URL. In strict mode it rejects
cloud providers, public fallback endpoints, redirects to remote origins, and
provider-returned remote image URLs before DNS or socket creation.

Status reports the parsed effective boolean, including explicit false. Tests
intercept DNS/socket/HTTP creation and exercise omitted URLs so a default-value
bypass cannot pass through source-string assertions.

## Compatibility And Migration

- Existing historical SVG requires no destructive migration because the egress
  guard sanitizes it on read. Safe cached copies may be introduced later.
- Browser development with auth disabled bypasses only the desktop readiness
  wait; SVG sanitization and origin decisions remain active.
- Current query-token authentication remains restricted to `/api/events/*`.
- Sanitizer limits and the inline style allowlist are versioned behavior. Add
  representative existing figures as fixtures before tightening them further.
- No product-data deletion is required for rollback. An artifact rejected by a
  newer boundary remains on disk but is not served.

## Error And Logging Contract

| Code | Surface | Meaning |
|---|---|---|
| `UNSAFE_SVG_CONTENT` | job status / HTTP 422 | SVG violates structure, active-content, URL, CSS, or resource limits |
| `AUTH_BOOTSTRAP_FAILED` | desktop UI / rejected fetch | Document-start desktop session was missing or invalid |
| `AUTH_ORIGIN_MISMATCH` | diagnostic category | Rust or bridge rejected session use on a non-canonical origin |

Logs may record the code, rule category, job identifier, and sanitized path.
They must not record the SVG body, session token, Authorization header, or full
query string containing `fs_token`.

## Acceptance Matrix

| ID | Scenario | Expected proof | Test layer |
|---|---|---|---|
| SVG-01 | script, event handler, foreign content | rejected before render and response | Python unit/API |
| SVG-02 | HTTP/file/javascript/CSS external load | rejected and no outbound request | Python + browser |
| SVG-03 | DTD, entities, deep/large payload | bounded typed failure | Python unit |
| SVG-04 | supported scientific figure | safe round trip, editor load, PNG output | Python + browser |
| SVG-05 | pre-existing hostile history file | HTTP 422, no raw fallback | API integration |
| SVG-06 | safe SVG response | CSP, nosniff, attachment headers | API integration |
| BR-01 | relative and exact absolute API URL | Bearer token attached | JavaScript unit |
| BR-02 | external or same-host/different-port API URL | no header or query token | JavaScript unit |
| BR-03 | Request with body/signal/options | request semantics preserved | JavaScript unit |
| BR-04 | malformed session or URL | fail closed without leakage | JavaScript/Rust unit |
| AUTH-01 | production cold start | first API request authenticated, zero 401 | composed-app smoke |
| AUTH-02 | reload and all production pages | same readiness behavior on each load | browser/Tauri smoke |
| AUTH-03 | malformed/missing document-start bootstrap | local failure and zero API traffic | JavaScript/Rust unit |
| AUTH-04 | EventSource exact-origin versus external/mismatch | only valid stream gets scoped credential | JavaScript/browser |
| AUTH-05 | auth-disabled browser development | no desktop wait | browser smoke |
| OFF-01 | strict mode with omitted/default provider URL | rejected before DNS/socket creation | Python integration |
| OFF-02 | redirect or provider-returned remote image | rejected before follow-up request | Python integration |

## Rollout And Rollback

Land the sanitizer and its sink tests before enabling UI changes. Land the
bridge origin rule before removing the public token path. Then land readiness
gating and run the production-composition cold-start test.

These controls are fail-closed and must not have release-time disable flags. If
a valid SVG regresses, rollback means restoring a known-good sanitizer version
or expanding a tested allowlist, never serving raw SVG. If desktop bootstrap
regresses, hold the Windows Beta artifact and restore the last complete desktop
build; do not fall back to anonymous requests or path-only token attachment.

## Deferred Risks

API provider secrets in child argv, bounded uploads/path containment, the
complete generation-job lifecycle, model-code trust/signing, dependency
provenance, and general application CSP are deliberately separate tasks. They
are not hidden by this design, and completion of this boundary does not claim
those risks are closed.
