# Implement: Phase 4 Tauri Sidecar

## Pre-flight

- [x] Phase 3 `858245a`
- [ ] Check if `cargo` / `node` / `npm` available; if not, scaffold files anyway + document
- [ ] Keep Python tests green with auth bypass for existing TestClient

## Checklist

### 1. Python auth + shutdown

- [ ] `figuresmith/security/auth.py` — bearer middleware
- [ ] Mount middleware in `main.py` when token set
- [ ] `POST /api/shutdown` token-protected
- [ ] Redact token from any logging helpers
- [ ] Tests: 401/200 matrix; DISABLE_AUTH path for phase3 API tests
- [ ] Update phase3 API tests to set DISABLE_AUTH or inject token

### 2. Tauri project scaffold

- [ ] Create `apps/desktop` Tauri 2 structure (manual scaffold if `npm create tauri-app` unavailable)
- [ ] `tauri.conf.json`: productName FigureSmith, identifier local.figuresmith.app
- [ ] Placeholder icons (generated simple, not upstream logo)
- [ ] README in apps/desktop for dev prerequisites

### 3. Sidecar + commands (Rust)

- [ ] Find free port; spawn python main.py
- [ ] Pass env token, strict offline, data dir, PYTHONPATH
- [ ] Wait healthz
- [ ] Commands: get_session, import_sam3_model, import_rmbg_archive, import_rmbg_folder, open_models_directory
- [ ] Exit hook cleanup

### 4. Frontend bridge

- [ ] Minimal JS/TS: get_session, fetch wrapper OR rely on same-origin vendor UI + inject token via custom protocol / window var set by Tauri
- [ ] Prefer serving UI from FastAPI (already static) so API same origin — inject token into window via query is BAD; use Tauri evaluate_script after load

Practical approach:
- WebView navigates to `http://127.0.0.1:port/`
- Tauri runs script: `window.__FIGURESMITH__ = { token, port }`
- Patch vendor app.js only if needed with thin figuresmith bridge file mounted by FastAPI static

Optional thin static: `apps/backend/figuresmith/static/desktop-bridge.js` mounted at `/figuresmith-bridge.js` and referenced by a small desktop index override.

If vendor index hard to patch: desktop uses local `apps/desktop/src` page with links + model import buttons calling invoke, and "Open editor" opens sidecar URL.

**MVP acceptable**: Desktop window loads sidecar UI; model import also available via Tauri menu commands without full UI redesign.

### 5. Scripts & docs

- [ ] `scripts/run-desktop.ps1`
- [ ] Update `scripts/build-desktop.ps1` status
- [ ] `docs/phase4-delivery.md`, development.md, CHANGELOG, README

### 6. Validation

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
$env:FIGURESMITH_DISABLE_AUTH = "1"   # or token fixtures
python -m pytest tests -q
```

Manual:
```powershell
./scripts/run-desktop.ps1
# open app, check health, exit, verify no python leftover
```

## Review Gates

1. No 0.0.0.0 in desktop spawn
2. Token not logged
3. Auth on /api/* when token set
4. Existing tests pass
5. Exit cleanup documented + implemented best-effort
6. No weights in package

## Defaults

- UI host: sidecar static (vendor web)
- Auth on when token present
- TestClient uses DISABLE_AUTH=1 in fixtures unless testing auth
- If Rust toolchain missing: still commit full scaffold; mark build as manual prerequisite in delivery doc
