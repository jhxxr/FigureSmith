# Implement: FigureSmith 阶段一仓库骨架

## Pre-flight

- [ ] 确认上游目录可读：`G:\0JHX-code\Project\AutoFigure-Edit-main`
- [ ] 确认工作区：`G:\0JHX-code\Project\FigureSmith`
- [ ] 不删除 `.trellis/`、`.claude/` 等工具目录
- [ ] 阶段一不改 SAM3/RMBG 推理逻辑

## Checklist

### 1. Git 与忽略规则

- [ ] 若无 git 仓库则 `git init`
- [ ] 写入根 `.gitignore`（Python、venv、outputs、models、权重、.env、IDE、OS 垃圾文件）
- [ ] 写入 `.env.example`（OpenAI 兼容占位；弱化 HF 主路径）

### 2. 导入上游到 vendor

- [ ] 创建 `vendor/autofigure_edit/`
- [ ] 复制上游核心：`autofigure2.py`、`server.py`、`requirements.txt`、`LICENSE`、`README.md`、`README_ZH.md`、`CITATION.cff`、`CITATION_AND_ATTRIBUTION.md`、`TRADEMARK.md`、`Dockerfile`、`docker-compose.yml`、`.env.example`、`web/`、`img/`（如体积可接受）、`releases/`
- [ ] 写入 `vendor/autofigure_edit/UPSTREAM.md`（来源路径、导入日期、保留策略）
- [ ] 复制 `web/vendor/svg-edit` → `vendor/svg_edit/`
- [ ] 写入 `vendor/svg_edit/UPSTREAM.md`

### 3. 建立 apps 骨架

- [ ] `apps/desktop/README.md` 占位（Tauri 后续）
- [ ] `apps/backend/figuresmith/__init__.py`（`__version__`）
- [ ] 创建子包目录：`api/`、`pipeline/`、`models/`、`runtime/`、`security/`（各含 `__init__.py` 与简短模块说明）
- [ ] `apps/backend/figuresmith/pipeline/vendor_bridge.py`：暴露 vendor 根路径解析
- [ ] `apps/backend/main.py`：开发启动入口（绑定 127.0.0.1，复用 vendor server app）
- [ ] `apps/backend/requirements.txt` / `pyproject.toml`

### 4. resources / scripts / docs / tests

- [ ] `resources/model-manifest.json` 空壳（注明阶段二填充）
- [ ] `resources/licenses/.gitkeep`、`resources/notices/.gitkeep`
- [ ] `scripts/setup-dev.ps1`：创建 venv、安装 backend requirements
- [ ] `scripts/run-backend.ps1`：启动本地后端
- [ ] `scripts/build-runtime.ps1` / `build-desktop.ps1` / `verify-offline.ps1`：占位说明阶段后续
- [ ] `docs/development.md`、`docs/licenses.md`、`docs/phase1-delivery.md`
- [ ] `tests/test_package_import.py`、`tests/test_repo_layout.py`

### 5. 根合规与品牌文档

- [ ] `LICENSE`（FigureSmith MIT）
- [ ] `NOTICE.md`
- [ ] `THIRD_PARTY_NOTICES.md`
- [ ] `CHANGELOG.md`
- [ ] `README.md` + `README_ZH.md`（FigureSmith 品牌 + 独立声明 + 上游致谢 + 开发启动）
- [ ] 不使用上游主 Logo 作为 FigureSmith 产品 Logo

### 6. 验证

- [ ] 目录结构检查脚本或测试通过
- [ ] `python -c "import figuresmith; print(figuresmith.__version__)"`（在正确 PYTHONPATH 下）
- [ ] `python -m pytest tests -q`（最小测试）
- [ ] 确认无模型权重文件被加入
- [ ] 更新 `docs/phase1-delivery.md`：修改清单、启动命令、已知限制

### 7. 收尾

- [ ] 更新 `CHANGELOG.md`
- [ ] Trellis 质量检查（阶段 2.2）
- [ ] 按用户要求决定是否提交 git commit（需明确授权）

## Validation Commands

```powershell
# 布局与导入冒烟
python -m pytest tests -q

# 包导入
$env:PYTHONPATH = "apps/backend;vendor/autofigure_edit"
python -c "import figuresmith; print(figuresmith.__version__)"

# 后端启动（开发）
./scripts/run-backend.ps1
# 期望：监听 http://127.0.0.1:8765/healthz
```

## Review Gates

1. vendor 是否完整且带 UPSTREAM 说明
2. README 是否完成品牌切割与合规声明
3. 是否误改 SAM3/RMBG 逻辑（阶段一禁止）
4. 是否误加入权重/大缓存

## Rollback Points

- 完成步骤 2 后：可单独删除 `vendor/` 回滚导入
- 完成步骤 3-5 后：可删除 `apps/`、`docs/` 新建文件回滚骨架
- 不影响 `G:\0JHX-code\Project\AutoFigure-Edit-main` 原目录

## Execution Notes

- Windows 路径复制优先使用 Python `shutil.copytree` 或 `robocopy`，避免 bash 在盘符路径上的坑
- 若 `img/case` 体积过大，可只复制必要说明图并在 UPSTREAM 注明未完整复制 gallery
- 阶段一 `main.py` 仅需能启动；Token 鉴权留给阶段四
