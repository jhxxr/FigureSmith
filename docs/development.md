# Development guide — FigureSmith (Phase 1)

## Prerequisites

- Windows 10/11 (primary target for scripts)
- Python **3.10+** (overall plan prefers **3.12**; Phase 1 allows 3.10/3.11 for scaffold work)
- Git
- Optional later: CUDA-capable GPU + SAM3 install for local segmentation

## Repository map

| Path | Role |
|------|------|
| `apps/backend/figuresmith/` | FigureSmith-owned Python package boundary |
| `apps/backend/main.py` | Dev entry: imports vendor FastAPI app |
| `apps/desktop/` | Tauri placeholder (Phase 4) |
| `vendor/autofigure_edit/` | Upstream AutoFigure-Edit baseline (do not casually rewrite) |
| `vendor/svg_edit/` | Boundary copy of svg-edit static assets |
| `resources/` | Manifests, licenses, notices (no weights in git) |
| `scripts/` | Windows PowerShell helpers |
| `docs/` | Developer and compliance docs |
| `tests/` | Phase 1 smoke tests |

## Setup

```powershell
cd G:\0JHX-code\Project\FigureSmith
./scripts/setup-dev.ps1
copy .env.example .env
# Edit .env: set OpenAI-compatible keys if you will call image/SVG providers
```

Notes:

- `setup-dev.ps1` creates `.venv` and installs `apps/backend/requirements.txt`.
- **SAM3 is not installed** by setup (separate optional step).
- **Model weights are not downloaded** by setup.
- `HF_TOKEN` is **not** the primary desktop path; leave it unset unless you intentionally use gated HF workflows during early development.

## Run backend (loopback only)

```powershell
./scripts/run-backend.ps1
```

Defaults:

- Host: `127.0.0.1`
- Port: `8765`
- Health: `http://127.0.0.1:8765/healthz`
- UI: `http://127.0.0.1:8765/`

**Bind policy:** the backend must be treated as local-only. Phase 1 forces/defaults to `127.0.0.1`. Do not expose it on `0.0.0.0` for normal desktop use.

Override (not recommended):

```powershell
$env:FIGURESMITH_HOST = "127.0.0.1"
$env:FIGURESMITH_PORT = "8765"
./scripts/run-backend.ps1
```

Equivalent manual launch:

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
.\.venv\Scripts\python.exe apps\backend\main.py --host 127.0.0.1 --port 8765
```

## Tests

```powershell
$env:PYTHONPATH = "apps\backend"
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -c "import figuresmith; print(figuresmith.__version__)"
```

## Vendor policy

- Keep `vendor/autofigure_edit` as a **preserve-as-baseline** snapshot.
- Phase 1 must **not** change SAM3/RMBG inference semantics in vendor code.
- FigureSmith adapters start in `apps/backend/figuresmith/` (e.g. `pipeline/vendor_bridge.py`).
- See `vendor/autofigure_edit/UPSTREAM.md`.

## Placeholder scripts

| Script | Status |
|--------|--------|
| `scripts/build-runtime.ps1` | Phase 2+ placeholder |
| `scripts/build-desktop.ps1` | Phase 4 placeholder |
| `scripts/verify-offline.ps1` | Phase 2+ placeholder |

## Branding

Product name: **FigureSmith / 图匠**.  
Do not present AutoFigure-Edit as the FigureSmith product name, package name, or primary logo.
