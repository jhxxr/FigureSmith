# FigureSmith 阶段一：建立新仓库骨架

## Goal

将 `G:\0JHX-code\Project\AutoFigure-Edit-main` 导入为 FigureSmith 独立开源仓库骨架：完成重命名与目录整理、保留上游许可证与致谢、建立可追踪的 `vendor/` 边界，并提供 Windows 开发启动入口。本阶段**不**实现本地 SAM3/RMBG 加载改造（属阶段二）。

## Background

- 产品名：**FigureSmith / 图匠**
- 定位：本地优先的科研插图生成、分割、矢量化与 SVG 编辑桌面工具
- 上游：AutoFigure-Edit（MIT，Copyright 2026 Autofigure2 contributors）
- 必须声明：FigureSmith 是基于 AutoFigure-Edit 的独立开源项目，与 ResearAI 无隶属或背书关系
- 当前 FigureSmith 工作区几乎为空（仅有 Trellis / 工具配置）

## Scope

### In Scope

1. 导入上游源码到 `vendor/autofigure_edit/` 与 `vendor/svg_edit/`
2. 建立目标 monorepo 目录骨架（`apps/`、`resources/`、`scripts/`、`docs/`、`tests/` 等）
3. 创建 FigureSmith 自有 Python 包边界 `apps/backend/figuresmith/`（阶段一以薄封装/占位为主，不重写上游流水线）
4. 重命名产品标识：README、包名、脚本、文档中不再把 AutoFigure-Edit 作为产品名
5. 许可证与合规：
   - 根 `LICENSE`（FigureSmith MIT）
   - `THIRD_PARTY_NOTICES.md` / `NOTICE.md` / `docs/licenses.md`
   - 保留上游 LICENSE、CITATION、TRADEMARK 说明
6. 开发辅助：
   - `.gitignore`、`.env.example`（不包含 HF 强依赖叙事）
   - `scripts/setup-dev.ps1`
   - 可运行的后端开发启动命令（基于现有 FastAPI server 路径）
7. `CHANGELOG.md` 记录阶段一变更
8. 初始化 git 仓库（若尚未初始化）并保证可提交

### Out of Scope（阶段二及以后）

- SAM3 `checkpoint_path` / `load_from_HF=False` 改造
- RMBG `local_files_only=True` 与删除 HF 回退
- 模型导入管理器、哈希校验、Zip Slip
- 严格离线模式完整实现与断网测试
- Tauri 桌面封装
- Runtime Pack / Installer 打包
- 删除 Roboflow / fal.ai 代码路径（可在文档中标记为阶段二目标，本阶段保留 vendor 原样可追踪）

## Constraints

1. 不要用伪代码代替真实文件落地
2. 不自动下载 gated 模型；不把模型权重写入仓库
3. 不隐藏第三方许可证；不使用上游 Logo 作为 FigureSmith Logo
4. 保持上游核心流程可追踪：优先 `vendor/` 拷贝 + 薄适配，避免无必要大规模重写
5. 后端监听约定在文档中写明仅 `127.0.0.1`（阶段一若复用上游 server，可先文档约束，代码硬约束可在阶段二/四完成）
6. 所有用户可见错误双语可在后续阶段补齐；本阶段至少 README 中英关键
7. 不破坏现有 `.trellis/` 工作流目录

## User-Visible Outcomes

- 开发者打开仓库即可理解 FigureSmith 与 AutoFigure-Edit 的关系
- 开发者可按 README / scripts 在 Windows 上完成依赖安装与后端启动
- 合规文件齐全，GitHub 发布前不会误带模型权重

## Acceptance Criteria

- [ ] 存在目标目录骨架：`apps/backend/`、`apps/desktop/`（可占位）、`vendor/autofigure_edit/`、`vendor/svg_edit/`、`resources/`、`scripts/`、`docs/`、`tests/`
- [ ] `vendor/autofigure_edit/` 包含上游核心文件（至少 `autofigure2.py`、`server.py`、`requirements.txt`、`LICENSE`、`web/`）
- [ ] `vendor/svg_edit/` 包含上游 `web/vendor/svg-edit` 内容
- [ ] 根 `README.md` 使用 FigureSmith 品牌，并包含独立声明与上游致谢
- [ ] 存在 `THIRD_PARTY_NOTICES.md`、`NOTICE.md`、`docs/licenses.md`、`CHANGELOG.md`、`LICENSE`
- [ ] `apps/backend/figuresmith/` 包可 import（含 `__init__.py` 与版本元数据）
- [ ] 提供 `scripts/setup-dev.ps1` 与文档化开发启动命令
- [ ] `.gitignore` 排除模型权重、outputs、venv、secrets
- [ ] 阶段一交付说明文档：修改文件清单、开发启动命令、已知限制
- [ ] 仓库内不出现以 AutoFigure-Edit 作为安装包名/程序名/主 Logo 的 FigureSmith 产品标识
- [ ] 本阶段不修改 SAM3/RMBG 推理语义（vendor 保持可追踪基线）

## Non-goals / Explicit Non-claims

- 不承诺断网可完成分割（阶段二）
- 不承诺 Tauri UI 可用
- 不承诺 CPU 推理
- 不宣传“全部组件可无限制商业使用”（RMBG 等第三方权重需单独合规）

## Upstream Source

- 本地路径：`G:\0JHX-code\Project\AutoFigure-Edit-main`
- 许可证：MIT
- 论文：arXiv:2603.06674

## Open Questions

无阻塞问题。若后续需要保留上游 git 历史，可另开任务做 `git filter-repo` / subtree 导入；阶段一默认文件级导入并在 NOTICE 中说明来源。
