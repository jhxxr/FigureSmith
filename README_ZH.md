# FigureSmith / 图匠

本地优先的科研插图生成、分割、矢量化与 SVG 编辑工具。

**FigureSmith 是基于 AutoFigure-Edit 的独立开源项目，与 ResearAI 无任何隶属或背书关系。**

> English README: [README.md](./README.md)

对应英文独立声明：

> FigureSmith is an independent open-source project based on AutoFigure-Edit. It is not affiliated with or endorsed by ResearAI.

## 阶段六状态

阶段六在桌面 UX 基础上提供 **Windows 打包工具**：

- `./scripts/build-runtime.ps1`：包含内置 CPython 3.12、哈希锁定 CPU 依赖和原生 DLL 的 Windows Runtime V1；不包含模型权重
- `./scripts/build-desktop.ps1`：生成 Setup/Portable 到 `dist-desktop/`
- `./scripts/write-checksums.ps1`：生成 SHA-256 `checksums.txt`
- 发布清单：[`docs/phase6-delivery.md`](./docs/phase6-delivery.md)、[`docs/release.md`](./docs/release.md)

发布版自带隔离的 CPython 3.12 和可复现的 CPU 依赖集合；首次启动不需要系统 Python、pip、虚拟环境或网络。`cu128` 锁文件仍保留给维护者或手工构建使用，但本次 Release 不上传 CUDA 运行时。

桌面端使用 **Tauri 2 + 本地 Python Sidecar**，并在阶段三模型管理之上提供：

- `apps/desktop/` 启动桌面进程，Sidecar **仅绑定 127.0.0.1**
- 一次性会话 Token（仅内存/子进程环境）保护 `/api/*` Bearer 鉴权
- 原生文件选择器触发 SAM3/RMBG 导入
- 退出时 `POST /api/shutdown`，超时则清理进程树
- 浏览器模式仍可用 `./scripts/run-backend.ps1`（无 Token）

**不随仓库或发布包提供：** SAM3/RMBG 等模型权重和用户数据。CPU Runtime V1 会随 Windows Release 发布；模型仍需用户自行准备并导入。

### 本地模型环境变量

| 变量 | 作用 |
|------|------|
| `FIGURESMITH_STRICT_OFFLINE` | 默认 `1`，禁止远程 SAM 与 HF 下载回退 |
| `FIGURESMITH_SAM3_CHECKPOINT` | 本地 SAM3 权重路径 |
| `FIGURESMITH_SAM3_BPE` | 可选 BPE 词表路径 |
| `FIGURESMITH_RMBG_MODEL_PATH` | 本地 RMBG-2.0 模型目录 |
| `FIGURESMITH_DATA_DIR` | 显式应用数据根目录（模型/设置/上传/输出）；必须通过可写探针，否则启动以 `DATA_DIR_NOT_WRITABLE` 失败 |
| `FIGURESMITH_DEV_MODE` | 仅源码开发时设为 `1` 才允许使用仓库 `data/`；发布/Portable 模式先尝试安装目录旁 `data/`，再回退到 LocalAppData |
| `FIGURESMITH_ALLOW_UNPINNED_MODELS` | 开发：允许与官方 pin 不匹配的导入 |
| `FIGURESMITH_SESSION_TOKEN` | 桌面 Sidecar 会话令牌（由 Tauri 注入，勿提交） |
| `FIGURESMITH_DISABLE_AUTH` | 测试旁路鉴权（`1` 关闭） |
| `FIGURESMITH_PYTHON` | 仅开发模式使用的外部 Python 路径；发布版 Runtime V1 忽略它 |

详见 [docs/phase4-delivery.md](./docs/phase4-delivery.md)、[docs/phase3-delivery.md](./docs/phase3-delivery.md)。

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
# 1) 创建 venv 并安装 FigureSmith 服务包
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
│   └── desktop/           # Tauri 桌面壳与打包配置
├── vendor/
│   ├── autofigure_edit/   # AutoFigure-Edit 基线
│   └── svg_edit/          # svg-edit 边界副本
├── resources/             # model-manifest 空壳、licenses、notices
├── scripts/               # setup-dev、run-backend、后续占位脚本
├── docs/                  # 开发、许可、发布与阶段交付说明
└── tests/                 # 冒烟测试
```

## 文档

- [docs/development.md](./docs/development.md) — 安装、启动、测试
- [docs/phase1-delivery.md](./docs/phase1-delivery.md) — 阶段一清单与限制
- [docs/phase6-delivery.md](./docs/phase6-delivery.md) — Windows 打包说明
- [docs/release.md](./docs/release.md) — 发布检查清单
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
| 1 | 仓库骨架、vendor 导入、品牌与合规、开发入口 |
| 2 | 本地 SAM3/RMBG、模型包、离线路径 |
| 3–5 | 加固、安全、模型管理与桌面 UX |
| 6（当前） | Windows Runtime/Setup/Portable 打包工具与发布清单 |

## 引用 / 上游

若使用 AutoFigure 相关方法，请同时参考：

- `vendor/autofigure_edit/CITATION.cff`
- `vendor/autofigure_edit/CITATION_AND_ATTRIBUTION.md`

## 许可证

- FigureSmith 代码：MIT — 见 [LICENSE](./LICENSE)
- 上游 AutoFigure-Edit：MIT — 见 `vendor/autofigure_edit/LICENSE`
- 第三方说明：[THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)
