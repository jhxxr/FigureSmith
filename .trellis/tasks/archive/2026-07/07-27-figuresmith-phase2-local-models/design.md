# Design: Phase 2 Local Model Loading & Strict Offline

## Overview

阶段二在 **不重写整条流水线** 的前提下，把“本地模型加载”做成强制、可测试的行为：

1. **安全与配置** 放在 `apps/backend/figuresmith/`（可单测）
2. **上游 `autofigure2.py` / `server.py`** 做最小补丁：新参数、本地加载参数、失败即停
3. FigureSmith 入口默认启用严格离线环境变量，并强制 local SAM

## Component Map

```text
apps/backend/figuresmith/
  security/
    offline.py          # env flags + validate_offline_endpoint
  models/
    paths.py            # resolve data dir + registered model paths
    registry.py         # read metadata.json / settings
    errors.py           # RMBG_MODEL_MISSING, SAM3_MODEL_MISSING, ...
    sam3_loader.py      # pure helpers: validate checkpoint, build kwargs
    rmbg_loader.py      # pure helpers: validate dir, from_pretrained kwargs
  runtime/
    env.py              # apply_strict_offline_env()
  pipeline/
    vendor_bridge.py    # existing + optional ensure offline before import

vendor/autofigure_edit/
  autofigure2.py        # surgical patches only
  server.py             # RunRequest + cmd wiring; path from registry not client
```

## Data Flow

### SAM3 local

```text
resolve sam_checkpoint_path (CLI | registry | env FIGURESMITH_SAM3_CHECKPOINT)
  → validate file exists
  → build_sam3_image_model(
        device=...,
        bpe_path=sam_bpe_path or package default,
        checkpoint_path=sam_checkpoint_path,
        load_from_HF=False,
    )
  → Sam3Processor ...
  → on missing path: raise SAM3_MODEL_MISSING (no HF, no fal/roboflow)
```

### RMBG local

```text
resolve rmbg_model_path (CLI | registry | env)
  → validate required files present (config.json, model.safetensors, ...)
  → AutoModelForImageSegmentation.from_pretrained(
        str(path), trust_remote_code=True, local_files_only=True
    )
  → no else-branch to briaai/RMBG-2.0 when figuresmith_strict / strict_offline
```

### Strict offline

```text
apply_strict_offline_env():
  HF_HUB_OFFLINE=1
  TRANSFORMERS_OFFLINE=1
  HF_DATASETS_OFFLINE=1
  NO_PROXY=127.0.0.1,localhost

validate_offline_endpoint(url):
  parse URL → hostname
  resolve IP (or treat known loopback names)
  allow only 127.0.0.1 / ::1 / localhost
  reject suffix tricks via actual parse, not startswith
```

## Vendor Patch Strategy

Keep patches minimal and marked:

```python
# --- FIGURESMITH-BEGIN: local-sam3 ---
...
# --- FIGURESMITH-END: local-sam3 ---
```

### `segment_with_sam3` signature extension

```python
def segment_with_sam3(
    ...
    sam_backend: Literal["local", "fal", "roboflow", "api"] = "local",
    sam_checkpoint_path: str | None = None,
    sam_bpe_path: str | None = None,
    strict_offline: bool = False,
    ...
):
```

When `strict_offline` or env `FIGURESMITH_STRICT_OFFLINE=1` or `FIGURESMITH_FORCE_LOCAL_SAM=1`:
- if backend != local → raise clear error
- never call fal/roboflow

Local branch **must** pass checkpoint and `load_from_HF=False`.

### `BriaRMBG2Remover`

- Prefer path required under strict mode
- Always use `local_files_only=True` when loading local path
- Under strict/desktop: remove HF download branch; raise `RMBG_MODEL_MISSING`

### CLI

```text
--sam_checkpoint_path
--sam_bpe_path
--strict_offline
```

### server.py

```python
class RunRequest(...):
    # Optional hints only; server resolves real paths from registry
    strict_offline: bool = False
    # Do NOT accept arbitrary client sam_checkpoint_path for desktop safety
```

FigureSmith `main.py` / run script:
- apply offline env before importing heavy stacks when configured
- inject registry paths into subprocess env:
  - `FIGURESMITH_SAM3_CHECKPOINT`
  - `FIGURESMITH_RMBG_MODEL_PATH`
  - `FIGURESMITH_STRICT_OFFLINE`

Upstream CLI still accepts explicit paths for developer power-users.

## Model Path Resolution Order

1. Explicit CLI args (developer)
2. Env vars (`FIGURESMITH_*`)
3. Settings file under app data: `%LOCALAPPDATA%\FigureSmith\settings.json` (or project `.figuresmith/settings.json` for dev)
4. Default layout: `%LOCALAPPDATA%\FigureSmith\models/sam3/sam3.pt` and `...\models/rmbg-2.0\`

Phase 2 implements resolver + optional dev settings file; full import UI is Phase 3.

## Error Model

| Code | When | User message (zh / en) |
|------|------|-------------------------|
| `SAM3_MODEL_MISSING` | no checkpoint | 请先配置/导入 SAM3 权重 / Configure SAM3 checkpoint first |
| `SAM3_MODEL_INVALID` | file exists but unreadable | ... |
| `RMBG_MODEL_MISSING` | no local dir | 请先导入 RMBG-2.0 / Import RMBG-2.0 first |
| `REMOTE_SAM_DISABLED` | strict + non-local backend | ... |
| `OFFLINE_ENDPOINT_FORBIDDEN` | non-loopback URL in strict | ... |

## Testing Design

### Unit (always run)

- `validate_offline_endpoint` allow/deny matrix
- path resolver: rejects path traversal when resolving under models root
- missing checkpoint → error code/message
- RMBG missing required files → error
- strict mode rejects fal/roboflow selection

### Offline network guard (no real GPU needed)

- monkeypatch/wrap any function that would call requests to HF/fal/roboflow and assert not called on missing-model and on local-path validation paths
- optional: set offline env and import loader helpers

### Optional integration (`@pytest.mark.gpu`)

- real sam3.pt + CUDA if present

## Risks

| Risk | Mitigation |
|------|------------|
| `build_sam3_image_model` API differs by sam3 package version | probe signature / kwargs carefully; document required sam3 version |
| `trust_remote_code` still executes local py | Phase 2 document trust warning; Phase 3 hash pin |
| Over-patching vendor hurts upstream diff | marker comments + thin helpers in figuresmith |
| Tests flake without torch | guard imports; unit tests pure-python where possible |

## Rollout / Rollback

- Feature flag env `FIGURESMITH_STRICT_OFFLINE` default **true** for FigureSmith launcher; CLI opt-in/out documented
- Rollback: revert vendor patches between FIGURESMITH markers; figuresmith modules unused

## Phase 3 Handoff

- Import ZIP/folder, checksum, metadata.json write
- UI model cards
- Replace env-based path setup with managed registry fully
