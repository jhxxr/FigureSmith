# Design: Phase 3 Model Manager

## Overview

在 `figuresmith.models` 上增加 **import / verify / delete / list** 服务层，所有写入走 **staging → validate → atomic promote**，失败清理 staging，不碰已 verified 目录（或仅在 promote 瞬间替换）。

## Architecture

```text
apps/backend/figuresmith/models/
  import_sam3.py       # import checkpoint
  import_rmbg.py       # import zip/dir + zip slip
  checksums.py         # sha256 file/dir
  manifest.py          # load resources/model-manifest.json + pin policy
  manager.py           # list/delete/verify/status facade
  staging.py           # staging paths + atomic promote + rollback

apps/backend/figuresmith/api/  (or extend vendor server carefully)
  models_routes.py     # FastAPI router mounted from figuresmith main

CLI (optional):
  python -m figuresmith.models.cli import-sam3 ...
```

Prefer mounting routes on FigureSmith `main.py` app (or include_router into vendor app after import) without rewriting entire vendor server.

## Import Flows

### SAM3

```text
source.pt
  → validate extension (.pt/.pth), size range (e.g. >1MB and <20GB configurable)
  → sha256(source)
  → copy to staging/sam3/sam3.pt
  → validate_sam3_checkpoint(staging path)  # phase2 helper
  → optional torch load probe if FIGURESMITH_MODEL_LOAD_PROBE=1 and cuda
  → write metadata.json + checksum.sha256 in staging
  → atomic promote staging → models/sam3/
  → update settings.json models.sam3_checkpoint
```

metadata example:

```json
{
  "id": "sam3",
  "display_name": "SAM 3",
  "checkpoint": "sam3.pt",
  "sha256": "...",
  "imported_at": "2026-07-27T12:00:00Z",
  "verified": true,
  "load_verified": "skipped",
  "source": "user_import",
  "official_verified": false
}
```

### RMBG ZIP / folder

```text
zip or dir
  → if zip: safe_extract to staging (zip slip checks, max files, max uncompressed)
  → ensure required files present (manifest.required_files + optional BiRefNet py files)
  → sha256 of model.safetensors (and/or full pack digest)
  → compare to manifest pins if present
  → if mismatch and not ALLOW_UNPINNED → abort
  → validate_rmbg_model_dir (phase2)
  → metadata + checksum
  → atomic promote to models/rmbg-2.0/
  → update settings
```

## Zip Slip Rules

- Reject absolute paths
- Reject `..` components after normpath
- Extract target must stay under staging root
- Max file count (e.g. 200)
- Max total uncompressed (e.g. 8GiB configurable)
- Skip or reject symlink members when detectable

## Atomic Promote

1. Write all content under `models/.staging/<id>-<uuid>/`
2. Validate entirely inside staging
3. If destination exists: move destination → `models/.trash/<id>-<ts>/` (or `.bak`)
4. Move staging → destination
5. On failure after step 3: restore from trash
6. Success: optional trash cleanup policy (keep last N)

## Pin / Official Verify Policy

- `resources/model-manifest.json` gains optional `official_sha256` / `files_sha256` map
- Empty/null pins: import allowed but `official_verified=false` with warning
- When pins present: mismatch → reject unless `FIGURESMITH_ALLOW_UNPINNED_MODELS=1`
- Release builds should document pins; Phase 3 can ship with null pins + structure ready

## API Surface (backend)

```text
GET  /api/models                 # list status
POST /api/models/sam3/import     # body: { "source_path": "..." }  # local path only
POST /api/models/sam3/verify
DELETE /api/models/sam3
POST /api/models/rmbg/import     # { "source_path": "...", "kind": "zip"|"dir" }
POST /api/models/rmbg/verify
DELETE /api/models/rmbg
GET  /api/models/paths           # resolved paths (no secrets)
```

Auth: Phase 4 token; Phase 3 loopback-only is mitigation. Document that endpoints are local-dev.

**Do not** accept multi-GB multipart upload as primary path.

## Integration with Phase 2

- After successful import, write settings.json so `resolve_model_paths` finds models
- Or rely on default layout under app data (already supported)
- Prefer both: default layout + settings mirror

## Testing

| Test | Approach |
|------|----------|
| sha256 | small temp file |
| zip slip `../` | craft zip, expect reject |
| zip absolute path | reject |
| max files | tiny limit override in test |
| sam3 import rollback | fail validation mid-way, assert old dest intact |
| rmbg required files | incomplete dir rejects |
| unpin policy | manifest pin mismatch |
| list/delete | temp app data dir via FIGURESMITH_DATA_DIR |

## Risks

| Risk | Mitigation |
|------|------------|
| Copying multi-GB files slow/fail | stream copy + progress logs; staging on same volume |
| Windows file locks | retry on replace; document close handles |
| trust_remote_code | UI/API warning strings; pin hashes |
| API abuse on loopback | Phase 4 token; path must be absolute existing file |

## Phase 4 Handoff

- Tauri `import_sam3_model` / `import_rmbg_archive` commands call same Python manager or local path API
- Native file picker supplies `source_path`
