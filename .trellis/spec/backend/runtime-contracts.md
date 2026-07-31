# Runtime Boundary Contracts

This document records executable contracts for the composed FigureSmith
backend and the vendored AutoFigure-Edit application.

## Scenario: Composed backend and mutable data boundary

### 1. Scope / Trigger

- Trigger: the outer FastAPI app, vendor app, desktop readiness probe, and
  mutable artifact paths cross the backend/vendor/desktop boundary.
- Owner: `apps/backend/main.py` owns composition and the canonical data root;
  `vendor/autofigure_edit/server.py` owns generation routes and must consume
  the root supplied by the owner.

### 2. Signatures

- `create_production_app(vendor_app=None, *, app_data_dir: Path | None = None,
  install_auth: bool = True) -> FastAPI`
- `GET /healthz -> {"status": "ok", "application": "figuresmith"}`
- `GET /api/desktop/ready -> {ok, ready, application, api_base_path,
  app_data_dir}`; this route is protected when session auth is enabled.
- `sanitize_svg(raw: bytes | str, *, limits: SvgLimits | None = None) ->
  SanitizedSvg`; unsafe content raises `UnsafeSvgContent`.

### 3. Contracts

- The outer app registers FigureSmith routes and middleware before mounting the
  vendor app at `/` as the final fallback.
- `app.state.figuresmith_app_data_dir` is the resolved absolute canonical root.
- The vendor module globals `APP_DATA_DIR`, `OUTPUTS_DIR`, and `UPLOADS_DIR`
  are rebound to that root during production composition. Explicit output/upload
  overrides remain supported, but are resolved before use and created eagerly.
- Uploaded paths are returned relative to `APP_DATA_DIR` when possible (for
  example `uploads/<uuid>.png`) and are resolved against the app root first;
  legacy source-tree-relative paths remain a read-only compatibility fallback.
- SVG artifact responses are sanitized before egress and include
  `Content-Security-Policy: sandbox; default-src 'none'; img-src data:;
  style-src 'unsafe-inline'` plus `X-Content-Type-Options: nosniff`.
- History artifacts, current artifacts, and uploaded SVGs share that egress
  boundary. Add `?download=1` only when a caller explicitly needs an
  attachment; the default response remains inline for the editor/preview.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Missing/invalid session token on `/api/*` | HTTP 401 with `UNAUTHORIZED` |
| `/healthz` without token | HTTP 200 |
| Relative upload/artifact path escapes its resolved root | HTTP 400 `Invalid path` |
| SVG contains script, event handler, foreign namespace, external URL,
  malformed XML, or exceeds a resource limit | HTTP 422 `UNSAFE_SVG_CONTENT` |
| SVG sanitizer cannot be loaded/read | HTTP 500 `SVG_SANITIZER_UNAVAILABLE` |

### 5. Good/Base/Bad Cases

- Good: `uploads/abc.png` resolves below `<app-data>/uploads`; `fill:url(#g)`
  references a local SVG fragment.
- Base: a legacy `uploads/abc.png` path is found below the vendor source tree
  only when the canonical-root candidate does not exist.
- Bad: `../uploads-escape/secret.png`, `href="https://example.invalid/x"`,
  `onclick="..."`, or a `<script>` node is rejected.

### 6. Tests Required

- Composition tests assert outer `/healthz`, vendor fallback, authenticated
  `/api/desktop/ready`, and matching model/vendor data roots.
- SVG tests assert safe round-trip, local fragment/data URI handling, hostile
  content rejection, limits, inline/download artifact headers, uploaded-SVG
  egress, and sibling-prefix upload rejection.
- Full backend tests run with `PYTHONPATH=apps/backend`; Rust and frontend
  checks remain required for the desktop document-start consumer.

### 7. Wrong vs Correct

#### Wrong

```python
rel_path = out_path.relative_to(BASE_DIR).as_posix()
candidate = (UPLOADS_DIR / filename).resolve()
if not str(candidate).startswith(str(UPLOADS_DIR.resolve())):
    raise HTTPException(status_code=400, detail="Invalid path")
```

#### Correct

```python
rel_path = out_path.relative_to(APP_DATA_DIR).as_posix()
candidate = (UPLOADS_DIR / filename).resolve()
candidate.relative_to(UPLOADS_DIR.resolve())
```

The resolved containment check prevents sibling-prefix escapes, and the
canonical root prevents uploads from silently returning a path that points back
into the immutable vendor tree.
