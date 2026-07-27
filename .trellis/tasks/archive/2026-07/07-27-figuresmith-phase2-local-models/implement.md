# Implement: Phase 2 Local Model Loading & Strict Offline

## Pre-flight

- [x] Phase 1 merged (`ac9e9f9`)
- [ ] Read current `segment_with_sam3` / `BriaRMBG2Remover` / CLI / `RunRequest`
- [ ] Confirm no weights in repo

## Checklist

### 1. figuresmith security & env

- [ ] `figuresmith/security/offline.py`
  - `apply_strict_offline_env()`
  - `validate_offline_endpoint(base_url: str) -> None`
  - `is_loopback_host(host: str) -> bool` (parse + IP, not startswith)
- [ ] `figuresmith/runtime/env.py` — launcher hook
- [ ] Unit tests: allow localhost/127.0.0.1/::1；deny evil suffix hosts；deny public hosts

### 2. figuresmith model path & errors

- [ ] `figuresmith/models/errors.py` — exception types + codes
- [ ] `figuresmith/models/paths.py` — app data dir, default model locations, safe join
- [ ] `figuresmith/models/registry.py` — read settings/metadata if present
- [ ] `figuresmith/models/sam3_loader.py` — validate checkpoint file; build load kwargs dict
- [ ] `figuresmith/models/rmbg_loader.py` — validate dir contents; build from_pretrained kwargs
- [ ] Update `resources/model-manifest.json` schema entries for sam3 + rmbg-2.0
- [ ] Tests for missing files, path traversal under models root

### 3. Vendor patch: autofigure2.py

- [ ] Extend `segment_with_sam3` with `sam_checkpoint_path`, `sam_bpe_path`, `strict_offline`
- [ ] Local load: `checkpoint_path=...`, `load_from_HF=False`
- [ ] Preflight: missing checkpoint → RuntimeError (no HF)
- [ ] If strict_offline / FIGURESMITH_STRICT_OFFLINE: reject non-local backends
- [ ] `BriaRMBG2Remover`: local_files_only=True; strict path no HF fallback
- [ ] `_ensure_rmbg2_access_ready`: strict mode only accepts existing local path
- [ ] Thread params through `method_to_svg` and CLI argparse
- [ ] Mark patches with FIGURESMITH-BEGIN/END comments

### 4. Vendor patch: server.py + FigureSmith main

- [ ] `RunRequest.strict_offline: bool = False`
- [ ] Wire CLI flags from server via env/registry paths (not raw client filesystem paths)
- [ ] `apps/backend/main.py` / `scripts/run-backend.ps1`: optional strict offline default; pass env for model paths
- [ ] Document settings file format for dev

### 5. Tests

- [ ] `tests/test_offline_endpoint.py`
- [ ] `tests/test_model_paths.py`
- [ ] `tests/test_sam3_local_load_contract.py` (kwargs / missing path; mock build_sam3 if needed)
- [ ] `tests/test_rmbg_local_load_contract.py`
- [ ] `tests/test_strict_offline_no_remote_fallback.py`
- [ ] Keep Phase 1 layout tests green

### 6. Docs

- [ ] `docs/phase2-delivery.md`
- [ ] Update `docs/development.md` model path section
- [ ] Update `CHANGELOG.md`
- [ ] README brief note on local model env vars

## Validation Commands

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q

# Contract: missing checkpoint fails closed
python -c "from autofigure2 import segment_with_sam3"  # import only
```

Optional GPU (manual):

```powershell
$env:FIGURESMITH_SAM3_CHECKPOINT = "C:\path\to\sam3.pt"
$env:FIGURESMITH_RMBG_MODEL_PATH = "C:\path\to\RMBG-2.0"
$env:FIGURESMITH_STRICT_OFFLINE = "1"
# run a small fixture image through local segment + rmbg
```

## Review Gates

1. No HF download branch reachable under strict mode
2. `load_from_HF=False` present on local SAM build call
3. `local_files_only=True` on RMBG local load
4. Endpoint validator not spoofable by prefix
5. Client cannot force arbitrary path via API in default server config
6. Tests pass without GPU/weights

## Rollback Points

- After step 1–2: figuresmith-only, low risk
- After step 3: vendor behavior change — revert marked regions
- After step 4: API surface change — revert RunRequest fields

## Decisions (defaults unless user overrides)

- No-GPU machine: control-flow tests sufficient for AC
- Keep fal/roboflow code in vendor but unreachable under strict/FigureSmith defaults
- FigureSmith launcher defaults `FIGURESMITH_STRICT_OFFLINE=1`
