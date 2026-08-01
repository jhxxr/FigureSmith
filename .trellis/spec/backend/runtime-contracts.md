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
  app_data_dir, models_dir}`; this route is protected when session auth is
  enabled.
- `sanitize_svg(raw: bytes | str, *, limits: SvgLimits | None = None) ->
  SanitizedSvg`; unsafe content raises `UnsafeSvgContent`.

### 3. Contracts

- The outer app registers FigureSmith routes and middleware before mounting the
  vendor app at `/` as the final fallback.
- `app.state.figuresmith_app_data_dir` is the resolved absolute canonical root.
- `app.state.figuresmith_app_paths` is one immutable `AppPaths` value containing
  settings, models, jobs, uploads, outputs, temp, logs, and SVG-cache roots.
- The root resolver probes create, write, flush, atomic replace, and delete.
  An explicit `FIGURESMITH_DATA_DIR` failure raises stable
  `DATA_DIR_NOT_WRITABLE`; automatic install candidates may fall through to
  LocalAppData. Repository data requires explicit `FIGURESMITH_DEV_MODE=1`.
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
- When desktop auth is enabled, `/api/events/*` accepts only the short-lived
  `fs_ticket` query credential (`FIGURESMITH_SSE_TICKET` plus an absolute
  `FIGURESMITH_SSE_TICKET_EXPIRES_AT`); the long-lived session Bearer token is
  never accepted in a URL. Both values are redacted from sidecar/backend logs.
- Strict offline policy runs after AutoFigure resolves provider aliases,
  default endpoints, image endpoints, and response-asset URLs. Only explicit
  loopback `custom` providers are permitted; public providers, remote assets,
  and unchecked redirects fail before a network client follows them.

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

## Scenario: User-managed Python and model environment boundary

### 1. Scope / Trigger

- Trigger: the Windows application pack, Tauri sidecar resolver, backend
  startup probe, model diagnostics, and welcome/splash UI cross the packaging,
  Rust, Python, and frontend boundaries.
- Owner: `apps/desktop/src-tauri/src/sidecar.rs` scans supported base Python installations and creates the isolated environment; `apps/backend/figuresmith/api/system_routes.py` reports package/GPU state; `scripts/build-runtime.ps1` publishes application files and guidance only.

### 2. Signatures

- `resolve_release_runtime_root(resource_dir: Option<PathBuf>) -> Result<PathBuf, String>`
- `GET /api/system/status -> {python, python_executable, python_supported,
  dependencies, gpu_available, sam3_loaded, rmbg_loaded, ...}`
- `probe_dependency_status() -> {bootstrap_ready, models_ready,
  missing_bootstrap, missing_models, install_command, ...}`
- `probe_gpu_status() -> {gpu_available, pytorch_cuda, torch_version,
  probe_error, ...}`; Torch is loaded in a disposable child process.

### 3. Contracts

- Release resources contain application source, `requirements-runtime.txt`,
  `requirements-bootstrap.txt`, `requirements-models.txt`, dependency metadata,
  and a hash manifest. They never contain Python executables, wheels, model
  weights, caches, or user data.
- Python candidates are scanned from `FIGURESMITH_PYTHON`, project environments, the Windows launcher, PATH, conda/virtualenv locations, and known user installation roots. A supported Python 3.10-3.12 is used only as the base for `%LOCALAPPDATA%\FigureSmith\python-env`; the sidecar runs from that isolated environment.
- Release mode resolves only through Tauri Resource paths. It never falls back
  to PATH/repository files for application code. A missing, extra, tampered,
  wrong-version, or embedded-runtime file fails before sidecar spawn.
- Missing bootstrap packages are installed into the isolated environment during
  first launch. They never modify the selected base Python. Missing model
  packages do not block the editor; status separates them from bootstrap
  packages and offers the model requirements command.
- The backend GPU probe must not import Torch in the main process. Native import
  aborts, nonzero exits, timeouts, and Python exceptions become `probe_error`.
- `FIGURESMITH_RUNTIME_ROOT` identifies the packaged guidance root for status
  commands; `FIGURESMITH_PYTHON` is the explicit base-Python override and
  `FIGURESMITH_MANAGED_PYTHON_DIR` overrides the isolated environment location.

### 4. Validation & Error Matrix

| Condition | Result |
|---|---|
| Release resource directory missing | startup fails before sidecar spawn; no repo fallback |
| Python version outside 3.10-3.12 | candidate rejected and diagnostic retained |
| Bootstrap package missing | first launch installs it into the isolated environment; the base Python is unchanged |
| Only Torch/SAM3/model import missing | editor starts; `/api/system/status` reports `missing_models` |
| Torch native import aborts or times out | backend remains alive; GPU is unavailable with redacted `probe_error` |
| Runtime manifest version/hash/inventory mismatch | local splash receives bounded startup error |
| Python/wheel/weight/cache appears in application pack | build or manifest verification fails closed |

### 5. Good/Base/Bad Cases

- Good: `py -3.12` lacks SAM3 but has FastAPI; the editor opens and the
  welcome page gives `requirements-models.txt`.
- Base: an explicit venv is selected when it has bootstrap packages even if a
  newer PATH Python appears first.
- Bad: Python 3.13 with an incompatible Torch, a stale repository `PYTHONPATH`,
  or a resource pack containing `python.exe`; startup rejects it.

### 6. Tests Required

- Rust tests assert missing resource, application-only identity/version,
  tamper/hash/extra-file rejection, and no embedded Python acceptance.
- Python tests assert manifest application-only fields, dependency scope
  payloads, system status commands, and subprocess-isolated GPU failure paths.
- Frontend checks assert one status load, separated model/bootstrap messaging,
  copyable install action, and bilingual splash/welcome content.
- PowerShell/CI checks assert the application pack contains all three guidance
  files and no Python/wheel/weight artifacts.

### 7. Wrong vs Correct

#### Wrong

```python
try:
    import torch
except Exception:
    return {"gpu_available": False}
```

#### Correct

```python
completed = subprocess.run(
    [sys.executable, "-c", gpu_probe_script],
    timeout=25,
    check=False,
)
return parse_probe_or_report_error(completed)
```

A native extension can terminate the host interpreter without raising a Python
exception, so model/GPU probing must be process-isolated.
