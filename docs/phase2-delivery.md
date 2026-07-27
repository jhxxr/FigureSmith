# Phase 2 delivery — Local SAM3/RMBG + strict offline

## Goal

Make local model loading **fail-closed** and offline-safe:

- SAM3 uses explicit `checkpoint_path` with `load_from_HF=False`
- RMBG loads local directories with `local_files_only=True`
- Strict offline blocks HF / fal / roboflow silent fallbacks
- Server resolves model paths from env/registry — not arbitrary client paths

## Files added / changed

### FigureSmith modules (`apps/backend/figuresmith/`)

| Path | Role |
|------|------|
| `security/offline.py` | `apply_strict_offline_env`, `is_loopback_host`, `validate_offline_endpoint` |
| `runtime/env.py` | Launcher + child-process env helpers |
| `models/errors.py` | `SAM3_MODEL_MISSING`, `RMBG_MODEL_MISSING`, `REMOTE_SAM_DISABLED`, … |
| `models/paths.py` | App data dir, default layout, safe path join |
| `models/registry.py` | CLI > env > settings > default path resolution |
| `models/sam3_loader.py` | Checkpoint validation + `build_sam3_load_kwargs` |
| `models/rmbg_loader.py` | Dir validation + `from_pretrained` kwargs |
| `main.py` | Default strict offline on launch |
| `resources/model-manifest.json` | sam3 + rmbg-2.0 metadata skeleton |

### Vendor patches (marked)

| Path | Change |
|------|--------|
| `vendor/autofigure_edit/autofigure2.py` | Local SAM3 load, RMBG `local_files_only`, CLI flags, strict reject remote |
| `vendor/autofigure_edit/server.py` | `RunRequest.strict_offline`; env/registry paths; child offline env |

Patches are wrapped in:

```text
# --- FIGURESMITH-BEGIN: <name> ---
# --- FIGURESMITH-END: <name> ---
```

### Tests

- `tests/test_offline_endpoint.py`
- `tests/test_model_paths.py`
- `tests/test_sam3_local_load_contract.py`
- `tests/test_rmbg_local_load_contract.py`
- `tests/test_strict_offline_no_remote_fallback.py`

### Scripts / docs

- `scripts/run-backend.ps1` — defaults `FIGURESMITH_STRICT_OFFLINE=1`
- `scripts/verify-offline.ps1` — runs offline contract tests
- `docs/phase2-delivery.md` (this file)
- `docs/development.md`, `CHANGELOG.md`, README notes, `.env.example`

## Start commands

```powershell
cd G:\0JHX-code\Project\FigureSmith
./scripts/setup-dev.ps1   # if needed

# Optional: point at local weights (not in git)
$env:FIGURESMITH_SAM3_CHECKPOINT = "$env:LOCALAPPDATA\FigureSmith\models\sam3\sam3.pt"
$env:FIGURESMITH_RMBG_MODEL_PATH = "$env:LOCALAPPDATA\FigureSmith\models\rmbg-2.0"

./scripts/run-backend.ps1
```

Health: http://127.0.0.1:8765/healthz

### Tests (no GPU / no weights)

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
# or
./scripts/verify-offline.ps1
```

### Developer CLI (explicit paths)

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python vendor/autofigure_edit/autofigure2.py `
  --input_figure_path path\to\figure.png `
  --sam_backend local `
  --sam_checkpoint_path path\to\sam3.pt `
  --rmbg_model_path path\to\RMBG-2.0 `
  --strict_offline `
  --stop_after 3 `
  --output_dir .\output\demo
```

## Settings file (dev)

Optional project-local file: `.figuresmith/settings.json`

```json
{
  "models": {
    "sam3_checkpoint": "C:/path/to/sam3.pt",
    "sam3_bpe": null,
    "rmbg_model_path": "C:/path/to/RMBG-2.0"
  },
  "strict_offline": true
}
```

App-data default (Windows): `%LOCALAPPDATA%\FigureSmith\settings.json`

## Path resolution order

1. Explicit CLI args (`--sam_checkpoint_path`, `--rmbg_model_path`, …)
2. Env: `FIGURESMITH_SAM3_CHECKPOINT`, `FIGURESMITH_SAM3_BPE`, `FIGURESMITH_RMBG_MODEL_PATH`
3. Settings JSON (`models.*`)
4. Default layout under app data: `models/sam3/sam3.pt`, `models/rmbg-2.0/`

**API safety:** `RunRequest` accepts `strict_offline` but **does not** accept client-supplied absolute model paths. The server injects paths from env/registry only.

## Strict offline behavior

When `FIGURESMITH_STRICT_OFFLINE=1` or `--strict_offline`:

| Flag / check | Behavior |
|--------------|----------|
| `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` / `HF_DATASETS_OFFLINE` | set to `1` |
| `NO_PROXY` | includes `127.0.0.1,localhost,::1` |
| `sam_backend` | must be `local` |
| SAM3 missing checkpoint | hard fail `SAM3_MODEL_MISSING` (no HF) |
| RMBG missing local dir | hard fail `RMBG_MODEL_MISSING` (no HF download) |
| `base_url` / `image_base_url` | must be loopback (`validate_offline_endpoint`) |

Endpoint validation rejects suffix tricks such as `localhost.example.com` and `127.0.0.1.example.com`.

## Known limitations

1. **No weights in repo** — users must obtain SAM3 / RMBG packs themselves; licenses differ from source MIT.
2. **No import UI yet** — Phase 3 adds ZIP/folder import, checksums, model cards.
3. **GPU optional for AC** — control-flow tests pass without CUDA; real inference needs local packs + GPU recommended.
4. **`trust_remote_code=True`** still applies for local RMBG Transformers code — Phase 3 should pin hashes.
5. **fal/roboflow source retained** in vendor for upstream compatibility but unreachable under FigureSmith strict defaults.
6. **`build_sam3_image_model` signature** may vary by sam3 package version; Phase 2 assumes support for `checkpoint_path` + `load_from_HF`.
7. **Non-strict vendor CLI** can still use legacy HF RMBG path when `FIGURESMITH_STRICT_OFFLINE` is off (dev escape hatch only).

## Phase 3 handoff

- Model pack import wizard (ZIP/folder) with Zip Slip guards — **done in Phase 3**
- Write `metadata.json` / registry updates from UI — backend ready; Tauri UI in Phase 4
- Checksum verification against manifest — **done in Phase 3** (pins may still be null)
- UI model cards and status
- Replace env-centric setup with managed registry as primary UX
