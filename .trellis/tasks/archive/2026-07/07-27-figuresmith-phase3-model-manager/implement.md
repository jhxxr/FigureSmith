# Implement: Phase 3 Model Manager

## Pre-flight

- [x] Phase 2 `b5a5d6c` present
- [ ] Confirm `figuresmith.models` loaders/paths/registry APIs
- [ ] Fix any remaining ignore rules that could hide manager code

## Checklist

### 1. Core utilities

- [ ] `checksums.py` — file sha256, optional multi-file digest
- [ ] `manifest.py` — load model-manifest.json; get pins; `allow_unpinned()` policy
- [ ] `staging.py` — create staging, promote, restore trash, cleanup
- [ ] Unit tests for checksum + staging rollback

### 2. SAM3 import

- [ ] `import_sam3.py` — validate, stage, checksum, metadata, promote, settings update
- [ ] Size/extension checks
- [ ] Fail closed + rollback tests with temp dirs (`FIGURESMITH_DATA_DIR`)

### 3. RMBG import

- [ ] `import_rmbg.py` — zip safe extract + folder copy
- [ ] Zip Slip tests
- [ ] Required files + pin policy tests
- [ ] Promote + rollback tests

### 4. Manager facade + API

- [ ] `manager.py` — list_models, verify_*, delete_*, import_*
- [ ] FastAPI routes under figuresmith; mount from `main.py` (include_router)
- [ ] Reject non-absolute / non-existent source_path
- [ ] Optional CLI module for dev: `python -m figuresmith...` or scripts/import-model.ps1

### 5. Manifest & settings

- [ ] Extend `resources/model-manifest.json` for phase 3 fields (pins optional null)
- [ ] Write/read metadata.json schema stable with phase 2 docs
- [ ] Ensure registry discovers imported default paths

### 6. Docs & changelog

- [ ] `docs/phase3-delivery.md`
- [ ] Update `docs/development.md`, README env/import section
- [ ] `CHANGELOG.md`

### 7. Validation

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q
```

Optional manual (with real weights outside repo):

```powershell
$env:FIGURESMITH_DATA_DIR = "D:\fs-data"
# import via API or CLI after implementation
```

## Review Gates

1. Zip Slip cannot write outside staging
2. Failed import leaves previous model intact
3. Pin mismatch rejected without ALLOW_UNPINNED
4. No weights in git status
5. Import path does not call HF
6. Phase 2 tests still pass

## Rollback

- Manager modules isolated under figuresmith.models — delete routes to disable
- Staging/trash under app data only

## Defaults (unless user overrides)

- Primary interface: Python API + FastAPI local routes (Tauri later)
- Load probe optional / skipped without CUDA
- Manifest pins may remain null initially but policy code must exist
