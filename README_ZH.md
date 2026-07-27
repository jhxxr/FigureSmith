# FigureSmith / 图匠

本地优先的科研插图生成、分割、矢量化与 SVG 编辑工具。

**FigureSmith 是基于 AutoFigure-Edit 的独立开源项目，与 ResearAI 无任何隶属或背书关系。**

> English README: [README.md](./README.md)

对应英文独立声明：

> FigureSmith is an independent open-source project based on AutoFigure-Edit. It is not affiliated with or endorsed by ResearAI.

## 阶段一状态

阶段一只交付**仓库骨架**：

- 上游 AutoFigure-Edit 基线导入 `vendor/`
- FigureSmith 自有 Python 包边界 `apps/backend/figuresmith/`
- Windows 开发安装/启动脚本
- 合规与品牌文档
- 最小冒烟测试

**尚未包含：** 断网可保证的本地 SAM3/RMBG 加载、Tauri 桌面壳、Runtime Pack/安装包、仓库内模型权重。

## 与 AutoFigure-Edit 的关系

FigureSmith 基于 AutoFigure-Edit（MIT，Copyright 2026 Autofigure2 contributors；论文 arXiv:2603.06674）。

| 项目 | FigureSmith 策略 |
|------|----------------|
| 产品名 | **FigureSmith / 图匠**（不以 AutoFigure-Edit 作为产品名） |
| 包名 | `figuresmith` |
| 上游代码 | 以快照形式保留在 `vendor/autofigure_edit/` |
| Logo | 不使用上游 AutoFigure-Edit / ResearAI Logo 作为 FigureSmith 产品 Logo |

详见 `NOTICE.md`、`THIRD_PARTY_NOTICES.md`、`docs/licenses.md`。

## 重要许可说明

**源码许可证 ≠ 第三方模型权重许可证。**

本仓库**不包含** SAM3/RMBG 等模型权重。分发或商业打包前请自行审阅权重提供方条款。

## 快速开始（Windows 开发）

```powershell
# 1) 创建 venv 并安装 backend 依赖
./scripts/setup-dev.ps1

# 2) 可选：配置 OpenAI 兼容接口密钥
copy .env.example .env

# 3) 启动后端（仅回环地址）
./scripts/run-backend.ps1
```

然后打开：

- 界面：http://127.0.0.1:8765/
- 健康检查：http://127.0.0.1:8765/healthz

### 后端绑定策略

开发后端面向**本机桌面使用**，默认：

- 主机：**仅 `127.0.0.1`**
- 端口：`8765`

日常使用请勿绑定到公网接口。

## 目录结构

```text
FigureSmith/
├── apps/
│   ├── backend/           # figuresmith 包 + main.py
│   └── desktop/           # Tauri 占位（阶段四）
├── vendor/
│   ├── autofigure_edit/   # AutoFigure-Edit 基线
│   └── svg_edit/          # svg-edit 边界副本
├── resources/             # model-manifest 空壳、licenses、notices
├── scripts/               # setup-dev、run-backend、后续占位脚本
├── docs/                  # 开发、许可、阶段一交付说明
└── tests/                 # 冒烟测试
```

## 文档

- [docs/development.md](./docs/development.md) — 安装、启动、测试
- [docs/phase1-delivery.md](./docs/phase1-delivery.md) — 阶段一清单与限制
- [docs/licenses.md](./docs/licenses.md) — 许可说明
- [CHANGELOG.md](./CHANGELOG.md)

## 测试

```powershell
$env:PYTHONPATH = "apps\backend"
python -m pytest tests -q
python -c "import figuresmith; print(figuresmith.__version__)"
```

## 阶段规划（摘要）

| 阶段 | 重点 |
|------|------|
| 1（当前） | 仓库骨架、vendor 导入、品牌与合规、开发入口 |
| 2 | 本地 SAM3/RMBG、模型包、离线路径 |
| 3+ | 加固、安全、打包准备 |
| 4 | Tauri 桌面壳 |

## 引用 / 上游

若使用 AutoFigure 相关方法，请同时参考：

- `vendor/autofigure_edit/CITATION.cff`
- `vendor/autofigure_edit/CITATION_AND_ATTRIBUTION.md`

## 许可证

- FigureSmith 代码：MIT — 见 [LICENSE](./LICENSE)
- 上游 AutoFigure-Edit：MIT — 见 `vendor/autofigure_edit/LICENSE`
- 第三方说明：[THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)
