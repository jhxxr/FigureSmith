# Design: FigureSmith 阶段一仓库骨架

## Overview

阶段一目标是“可追踪地导入上游 + 建立 FigureSmith 边界”，不是重写流水线。  
策略：**vendor 保留上游完整可运行基线**，`apps/backend/figuresmith` 作为未来桌面版自有代码边界；阶段二再在自有边界内改 SAM3/RMBG 加载。

## Architecture

```text
FigureSmith/
├── apps/
│   ├── desktop/                 # 阶段四：Tauri 占位
│   │   └── README.md
│   └── backend/                 # FigureSmith Python 后端边界
│       ├── figuresmith/
│       │   ├── __init__.py
│       │   ├── api/             # 阶段一占位
│       │   ├── pipeline/        # 阶段一：vendor 适配入口（薄）
│       │   ├── models/          # 阶段二
│       │   ├── runtime/         # 阶段二
│       │   └── security/        # 阶段二
│       ├── main.py              # 开发入口：转发/启动 vendor server 或自有 app
│       ├── pyproject.toml
│       └── requirements.txt     # 基于上游 requirements，标注 SAM3 外置
│
├── vendor/
│   ├── autofigure_edit/         # 上游快照（只读基线，修改需记录）
│   │   ├── UPSTREAM.md          # 来源、版本、导入日期、修改策略
│   │   ├── LICENSE
│   │   ├── autofigure2.py
│   │   ├── server.py
│   │   ├── requirements.txt
│   │   └── web/                 # 原 Web UI（阶段四前仍可用于开发）
│   └── svg_edit/                # 从上游 web/vendor/svg-edit 抽出
│
├── resources/
│   ├── model-manifest.json      # 阶段二用，阶段一放空壳 schema
│   ├── licenses/
│   └── notices/
│
├── scripts/
│   ├── setup-dev.ps1
│   ├── run-backend.ps1
│   └── verify-offline.ps1       # 阶段二实现；阶段一可放 TODO stub
│
├── docs/
│   ├── licenses.md
│   ├── development.md
│   └── phase1-delivery.md       # 交付清单/限制
│
├── tests/
│   └── test_package_import.py   # 最小冒烟：包可导入
│
├── LICENSE
├── NOTICE.md
├── THIRD_PARTY_NOTICES.md
├── CHANGELOG.md
├── README.md
└── README_ZH.md
```

## Module Boundaries

| 路径 | 职责 | 阶段一允许修改 |
|------|------|----------------|
| `vendor/autofigure_edit/` | 上游快照，保持可 diff | 仅加 `UPSTREAM.md`；尽量不改业务代码 |
| `vendor/svg_edit/` | SVG 编辑器静态资源 | 不改逻辑 |
| `apps/backend/figuresmith/` | FigureSmith 自有 API/运行时 | 新建薄模块 |
| `scripts/` | 开发与构建脚本 | 新建 |
| 根文档 | 品牌、许可、致谢 | 新建 |

## Import Strategy

1. **文件级拷贝**上游目录到 `vendor/autofigure_edit/`  
   - 原因：当前工作区无 git 历史可合并；用户给的是解压/目录副本  
   - 在 `UPSTREAM.md` 记录来源路径、导入日期、上游版本线索（README v1.1 / arXiv）
2. **抽出** `web/vendor/svg-edit` → `vendor/svg_edit/`，并在 vendor web 中保留相对可用路径或文档说明后续映射
3. **不**把 `img/case` 大图案例强依赖为运行必需；可复制 `img` 中 logo/pipeline 到 `docs/assets` 或保留在 vendor 供参考，但 README 主品牌不使用上游 Logo 作为 FigureSmith Logo

## Backend Dev Entry (Phase 1)

阶段一开发启动优先保证“能跑通上游 Web+API”，降低风险：

```text
scripts/run-backend.ps1
  → 设置 PYTHONPATH 包含 vendor/autofigure_edit 与 apps/backend
  → 启动 uvicorn server:app（vendor）或 apps.backend.main
  → 默认绑定 127.0.0.1:8765
```

`apps/backend/main.py` 可以：
- 选项 A：subprocess/文档方式启动 vendor `server.py`
- 选项 B：import vendor server app 并暴露

推荐 **选项 B（import 暴露）** 或直接 `run-backend.ps1` 指向 vendor module path，保持最少胶水。

## Python Packaging

`apps/backend/pyproject.toml`：
- name = `figuresmith`
- python = `>=3.12`（与总体方案一致；若本机仅 3.10/3.11，在已知限制中说明可先用 3.10+ 开发骨架）
- packages = `figuresmith`

阶段一 `figuresmith.pipeline` 提供：
```python
# 明确标注为 vendor bridge，阶段二替换
from pathlib import Path
VENDOR_ROOT = ...
```

不在阶段一改 `segment_with_sam3` / `BriaRMBG2Remover`。

## Compliance Design

1. 根 `LICENSE`：FigureSmith 自有代码 MIT，Copyright 当前项目贡献者
2. `NOTICE.md`：说明包含修改自 AutoFigure-Edit 的组件
3. `THIRD_PARTY_NOTICES.md`：
   - AutoFigure-Edit (MIT)
   - svg-edit（按其上游许可，从目录/文件识别）
   - SAM3 / RMBG 运行时依赖提示（权重不随仓库分发）
4. README 固定声明：
   - 独立项目、非 ResearAI 附属
   - based on AutoFigure-Edit
   - 源码许可 ≠ 第三方模型权重许可

## Config / Secrets

- `.env.example`：OpenAI 兼容接口变量占位；**不**引导必须配置 `HF_TOKEN` 作为桌面版主路径
- `.gitignore`：排除 `**/*.pt`、`**/*.safetensors`、`models/`、`outputs/`、`.env`、venv 等

## Testing Strategy (Phase 1)

最小测试即可：
1. `import figuresmith` 成功
2. 关键关键路径存在性检查（vendor 文件、合规文件）
3. 不跑 GPU / 不下载模型

## Risks & Mitigations

| 风险 | 缓解 |
|------|------|
| 拷贝后路径断裂（svg-edit 相对路径） | 保留 `vendor/autofigure_edit/web/vendor/svg-edit` 同时复制一份到 `vendor/svg_edit`，或在 web 内做 junction/说明 |
| 过早改 SAM/RMBG 导致不可对比上游 | 阶段一冻结 vendor 业务代码 |
| 误提交大文件/模型 | gitignore + README 警告 |
| 与 Trellis 目录冲突 | 不触碰 `.trellis/` |

## Rollout / Rollback

- Rollout：一次性落地骨架文件；开发者按 `docs/development.md` 启动
- Rollback：删除新建目录即可；vendor 为拷贝，不影响上游原目录 `AutoFigure-Edit-main`

## Phase 2 Handoff Points

以下文件是阶段二的明确插入点（本阶段只记录，不实现）：
- `vendor/autofigure_edit/autofigure2.py` → `segment_with_sam3` / `BriaRMBG2Remover`
- 未来自有实现：`apps/backend/figuresmith/models/`、`runtime/`、`security/`
