# Design: Phase 4 Tauri Sidecar Shell

## Overview

```text
FigureSmith.exe (Tauri)
  → spawn Python: apps/backend/main.py --host 127.0.0.1 --port <p>
       env: FIGURESMITH_SESSION_TOKEN, FIGURESMITH_STRICT_OFFLINE=1,
            FIGURESMITH_DATA_DIR, PYTHONPATH
  → wait http://127.0.0.1:<p>/healthz (Authorization header)
  → WebView navigate to http://127.0.0.1:<p>/  OR local dist + API base
  → on exit: POST /api/shutdown or kill process group
```

## Components

### 1. Tauri app (`apps/desktop/`)

```text
apps/desktop/
  package.json
  src/                 # minimal TS bootstrap (token bridge optional)
  src-tauri/
    Cargo.toml
    tauri.conf.json
    src/main.rs
    src/sidecar.rs     # spawn/monitor python
    src/commands.rs    # import_sam3_model, etc.
    icons/             # placeholder FigureSmith icons (not upstream)
```

### 2. Sidecar launcher (Rust)

- Resolve Python: `FIGURESMITH_PYTHON` or `apps/backend/.venv/Scripts/python.exe` or `python`
- Args: `-m` or path to `main.py` with host/port
- Generate `token = random 32 bytes hex`
- Port: `0` bind then read back **or** pick free port in Rust and pass `--port`
- Prefer: Rust finds free port → pass to Python (simpler than parsing child stdout)

### 3. Auth middleware (Python)

```python
# figuresmith/security/auth.py
FIGURESMITH_SESSION_TOKEN
FIGURESMITH_DISABLE_AUTH=1  # tests / legacy browser dev only

middleware:
  if path in PUBLIC: /healthz maybe still requires token in desktop mode?
  Recommended: /healthz allows without token for probe OR requires token —
  Design choice: healthz requires token when SESSION_TOKEN set; Tauri always sends it.
  Alternative: healthz public, all /api/* protected.

Decision: 
- `/healthz` public (process alive check)
- all other routes require Bearer when token env set
```

CORS: only allow tauri origins / null / localhost as needed for WebView.

### 4. Shutdown

- Add `POST /api/shutdown` (token required) → sets flag / os._exit after response in thread
- Tauri on Exit: call shutdown, wait 3s, kill if needed
- Windows: taskkill process tree if orphaned

### 5. Tauri commands

```rust
#[tauri::command]
async fn import_sam3_model(app: AppHandle, path: Option<String>) -> Result<ModelInfo, String>
// if path None → open dialog filter pt
// then HTTP POST http://127.0.0.1:port/api/models/sam3/import {source_path} with token
// OR invoke python -c manager (prefer HTTP to reuse server state)
```

Similarly rmbg zip/dir, open_models_directory (shell open path from GET /api/models/paths).

### 6. Frontend integration

Option A (recommended Phase 4 MVP): load vendor web from sidecar; inject small preload script via Tauri to wrap `fetch`:

```js
const { invoke } = window.__TAURI__
// store apiBase + token in memory from invoke('get_session')
```

Option B: minimal React app that embeds iframe to vendor UI.

Go with **Option A + get_session command**.

### 7. Dev workflow

```powershell
# terminal 1 optional: backend only still works with DISABLE_AUTH for browser
./scripts/run-backend.ps1

# desktop dev
./scripts/run-desktop.ps1
# → npm install && cargo / tauri dev
```

## Security

| Topic | Policy |
|-------|--------|
| Bind | 127.0.0.1 only; refuse 0.0.0.0 in desktop spawn args |
| Token | process env child only; Tauri holds in memory |
| Logs | redaction: never print token |
| File dialog | user-selected paths only |
| Strict offline | child env always for desktop |

## Testing

- Python: auth middleware unit tests (401 without token, 200 with token)
- Python: shutdown endpoint
- Optional: spawn main.py subprocess with token in integration test
- Rust: unit test free port helper if pure
- Document manual GUI checklist

## Risks

| Risk | Mitigation |
|------|------------|
| tauri CLI not installed on user machine | docs + graceful script errors |
| WebView CORS/fetch to loopback | same-origin if UI served by FastAPI |
| Killing python leaves torch workers | process group kill |
| Path with spaces on Windows | careful Command quoting |

## Phase 5 Handoff

- Welcome wizard, hardware page, polished model cards
- History/SVG editor UX
- Stronghold for API keys
