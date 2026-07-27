# Phase 3 delivery — Model manager (import / verify / delete / rollback)

## Goal

On top of Phase 2 local load contracts, provide a **safe model manager**:

- Import SAM3 `.pt` and RMBG-2.0 ZIP/folder into app data
- SHA-256 + optional official pin checks (`resources/model-manifest.json`)
- **Staging → validate → atomic promote** so failed imports never destroy a working pack
- List / verify / delete lifecycle APIs and a dev CLI
- Strict offline: import/verify do **not** call Hugging Face or other networks

## Files added / changed

### Core (`apps/backend/figuresmith/models/`)

| Module | Role |
|--------|------|
| `checksums.py` | File SHA-256, checksum file IO, multi-file digest |
| `manifest.py` | Load manifest, pin evaluation, `FIGURESMITH_ALLOW_UNPINNED_MODELS` |
| `staging.py` | `.staging` / `.trash`, atomic promote, rollback restore |
| `settings_io.py` | Atomic settings.json updates after import/delete |
| `import_sam3.py` | SAM3 import pipeline |
| `import_rmbg.py` | RMBG ZIP (Zip Slip safe) / folder import |
| `manager.py` | Facade: list / import / verify / delete |
| `cli.py` / `__main__.py` | `python -m figuresmith.models.cli …` |

### API

| Path | Role |
|------|------|
| `figuresmith/api/models_routes.py` | FastAPI router `/api/models/*` |
| `apps/backend/main.py` | Mounts router on vendor app after import |

### Resources / docs / tests

- `resources/model-manifest.json` — phase 3 fields (`official_sha256`, `files_sha256`, pin policy); pins may be `null`
- `docs/phase3-delivery.md` (this file)
- Tests: `test_checksums.py`, `test_zip_slip.py`, `test_import_sam3_rollback.py`, `test_import_rmbg.py`, `test_model_manager_api.py`

## Layout after import

```text
%LOCALAPPDATA%\FigureSmith\   (or FIGURESMITH_DATA_DIR)
  settings.json
  models\
    sam3\
      sam3.pt
      metadata.json
      checksum.sha256
    rmbg-2.0\
      config.json
      preprocessor_config.json
      model.safetensors
      metadata.json
      checksum.sha256
    .staging\     # transient
    .trash\       # previous packs after replace
```

## API (loopback)

Import accepts **local absolute `source_path` only** (no multi-GB multipart upload).

| Method | Path | Body |
|--------|------|------|
| GET | `/api/models` | — |
| GET | `/api/models/paths` | — |
| POST | `/api/models/sam3/import` | `{"source_path":"C:/.../sam3.pt"}` |
| POST | `/api/models/sam3/verify` | — |
| DELETE | `/api/models/sam3` | — |
| POST | `/api/models/rmbg/import` | `{"source_path":"...","kind":"zip\|dir\|auto"}` |
| POST | `/api/models/rmbg/verify` | — |
| DELETE | `/api/models/rmbg` | — |

Auth: Phase 4 token planned; Phase 3 mitigation is **loopback bind only**.

## CLI

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
$env:FIGURESMITH_DATA_DIR = "D:\fs-data"   # optional

python -m figuresmith.models.cli list
python -m figuresmith.models.cli import-sam3 --source C:\weights\sam3.pt
python -m figuresmith.models.cli import-rmbg --source C:\weights\RMBG-2.0.zip --kind zip
python -m figuresmith.models.cli verify-sam3
python -m figuresmith.models.cli delete-rmbg
```

For tiny test files, pass `--min-bytes 1` or set `FIGURESMITH_SAM3_MIN_BYTES=1`.

## Pin policy

1. Manifest pin `null`/absent → import allowed, `official_verified=false` + warning
2. Pin present and matches → `official_verified=true`
3. Pin present and mismatches → **reject** unless `FIGURESMITH_ALLOW_UNPINNED_MODELS=1`

## Safety notes

- **Zip Slip**: reject absolute paths, `..`, symlink members, excess file count / uncompressed size
- **Rollback**: staging cleaned on failure; promote moves old pack to `.trash` and restores on mid-swap failure
- **trust_remote_code**: RMBG import always surfaces a bilingual warning (source license ≠ weight license)
- **No weights in git**

## Tests

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
```

All Phase 3 tests use temp dirs and tiny fixtures — **no GPU, no multi-GB weights**.

## Environment

| Variable | Purpose |
|----------|---------|
| `FIGURESMITH_DATA_DIR` | App data root override |
| `FIGURESMITH_ALLOW_UNPINNED_MODELS` | Allow pin mismatches (dev) |
| `FIGURESMITH_SAM3_MIN_BYTES` / `MAX` | Size gate overrides |
| `FIGURESMITH_RMBG_ZIP_MAX_FILES` | ZIP file-count cap (default 200) |
| `FIGURESMITH_RMBG_ZIP_MAX_UNCOMPRESSED` | ZIP uncompressed byte cap |
| `FIGURESMITH_MODEL_LOAD_PROBE` | Optional torch load probe (CUDA) |

## Known limitations

1. Official pins ship as `null` until release hashing is finalized — policy code is live.
2. Load probe defaults to `skipped` without CUDA / without `FIGURESMITH_MODEL_LOAD_PROBE=1`.
3. No Tauri file picker yet (Phase 4); API/CLI take absolute paths prepared by the OS picker later.
4. Endpoints are unauthenticated beyond loopback (Phase 4 token).
5. Windows file locks may require retries during promote (limited retries implemented).

## Phase 4 handoff

- Tauri commands `import_sam3_model` / `import_rmbg_archive` should call `ModelManager` or `POST /api/models/.../import` with native-picker `source_path`
- Reuse bilingual `FigureSmithError.to_dict()` payloads for UI toasts
- Add auth token before any non-loopback bind
