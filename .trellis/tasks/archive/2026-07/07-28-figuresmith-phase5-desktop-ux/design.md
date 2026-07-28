# Design: Phase 5 Desktop UX

## Overview

阶段五以 **“可完成首次配置并跑通本地科研图工作流”** 为体验目标。技术上采用：

1. **后端补齐 system status API**
2. **静态 UI 增量**：新页面 + 对 vendor web 的品牌/SAM 收敛补丁
3. **桌面 bridge 增强**：向导与模型页调用 Tauri import commands
4. **不重写** 整条 SVG/任务流水线后端

## Information Architecture

```text
/welcome.html     欢迎 + 向导入口
/models.html      模型管理
/index.html       创建（方法文本）— 品牌/SAM 收敛后
/import.html      导入已有图
/history.html     历史
/canvas.html      SVG 编辑
/guide.html       指南（更新 FigureSmith 文案）
```

顶栏统一：FigureSmith | 创建 | 导入图 | 模型 | 历史 | 指南 | 语言

## Backend: System Status

`GET /api/system/status`（需 token，与其他 /api 一致）

```json
{
  "product": "FigureSmith",
  "version": "0.5.0",
  "platform": {"system": "Windows", "release": "...", "machine": "AMD64"},
  "python": "...",
  "gpu_available": true,
  "gpu_name": "NVIDIA ...",
  "cuda_version": "...",
  "vram_total_mb": 12288,
  "vram_free_mb": 10320,
  "pytorch_cuda": true,
  "sam3_loaded": false,
  "rmbg_loaded": false,
  "models": { "... from ModelManager.list ..." },
  "strict_offline": true,
  "onboarding_completed": false,
  "messages": {
    "gpu_missing_zh": "未检测到可用的 NVIDIA CUDA 环境。...",
    "gpu_missing_en": "No usable NVIDIA CUDA environment detected. ..."
  }
}
```

Implementation notes:
- torch/cuda probe in try/except — never crash
- model status reuses `ModelManager`
- onboarding flag in settings.json

`POST /api/system/onboarding` `{ "completed": true }`

## UI Branding Patch Strategy

Prefer **additive overlay** over massive vendor rewrite:

1. `figuresmith/static/brand-override.js` + `brand-override.css`  
   - rewrite document title, brand text nodes, hide remote SAM UI blocks
2. Or direct edits to vendor `web/*.html` + `app.js` with `FIGURESMITH-BEGIN` markers

**Decision:** Direct minimal edits to vendor web for reliability (same-origin, no race), plus new pages under `figuresmith/static/ui/` mounted at `/fs/` or root overrides.

Mount plan in `main.py`:
- Serve `figuresmith/static/ui/*` with higher priority for new pages
- Keep vendor web for pipeline pages after patch

## Model Management Page

- Fetch `GET /api/models` + `GET /api/system/status`
- Buttons:
  - Desktop: `invoke('import_sam3_model')` etc.
  - Browser dev: file path input (advanced) or disabled with message “use desktop app”
- Verify/Delete via existing API
- Open directory via Tauri or show path

## Create Page Changes

- Force `sam_backend=local` hidden field
- Remove fal/roboflow choice cards from DOM/JS
- Remove HF token fields if any
- Keep OpenAI-compatible providers; when strict_offline, validate base URL client-side hint + server already enforces
- Pipeline progress labels 中英：准备图片 → 本地 SAM3 → 本地 RMBG → SVG → 装配 → 完成

## Log Redaction

Shared helper `figuresmith/security/redact.py`:
- mask `api_key`, `Authorization`, bearer tokens, sk- keys
- shorten home directory paths in logs if streamed

Apply when streaming job events if easy; at least document + helper used by any new log endpoints.

## Onboarding Flow

```text
welcome → check system status
  → if !sam3 imported → models import step
  → if !rmbg imported → models import step
  → configure provider (optional skip)
  → mark onboarding complete
  → go to create
```

## Testing

- `test_system_status.py` — no torch crash; shape keys present
- `test_ui_branding_contract.py` — key HTML/JS files do not advertise Roboflow/fal as default options (string contracts)
- Keep auth/models tests green

## Risks

| Risk | Mitigation |
|------|------------|
| Editing large app.js | surgical patches + tests for forbidden strings |
| Tauri invoke only in desktop | feature detect `window.__TAURI__` |
| API keys in localStorage from vendor | strip/disable persistence where found; document residual risk |

## Phase 6 Handoff

- Installer, runtime pack, release checksums
- Stronghold for secrets if not done
