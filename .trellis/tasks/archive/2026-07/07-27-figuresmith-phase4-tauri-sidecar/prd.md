# FigureSmith 阶段四：Tauri 桌面封装与 Sidecar

## Goal

用 **Tauri 2** 封装 FigureSmith 桌面壳：启动/停止本地 Python 后端 Sidecar、仅绑定 `127.0.0.1`、一次性 session token 鉴权、原生文件选择器驱动阶段三模型导入，并加载现有 Web UI。本阶段打通“可运行的桌面进程生命周期”；完整首次向导与页面打磨主要在阶段五。

## Background

- 阶段一～三已完成：vendor 基线、本地 SAM3/RMBG、严格离线、模型导入管理器（commit `858245a`）
- 当前开发：`scripts/run-backend.ps1` → 浏览器访问 `http://127.0.0.1:8765`
- 要求：Tauri 启动 Sidecar → 随机端口 → Token → `/healthz` → 加载页面；退出无残留 Python

## Scope

### In Scope

1. Tauri 2 工程骨架（`apps/desktop/`），产品名 FigureSmith
2. Python Sidecar 生命周期（启动/健康检查/优雅退出/超时强杀）
3. Session Token 鉴权（Bearer；内存；可测试旁路）
4. Tauri commands：导入 SAM3/RMBG、打开模型目录、`get_session`
5. 前端/WebView 接线（优先加载 sidecar vendor web）
6. `scripts/run-desktop.ps1`、文档、`docs/phase4-delivery.md`
7. Python auth/shutdown 单测；现有测试保持绿色

### Out of Scope

- 完整首次向导/硬件页美化（阶段五）
- Runtime Pack / Installer 完整发布（阶段六）
- macOS/Linux 打包承诺

## Constraints

1. 后端只听 `127.0.0.1`
2. Token 不落盘、不进日志
3. 不打包模型权重
4. Windows x86_64 首版目标
5. 退出不残留 Python 进程
6. 不使用上游 Logo

## Acceptance Criteria

- [ ] `apps/desktop` 存在 Tauri 2 工程与开发说明
- [ ] 桌面可拉起 Python sidecar 并打开 UI（工具链可用时）
- [ ] sidecar 绑定 127.0.0.1
- [ ] API 在 token 模式下无 Bearer 返回 401
- [ ] Tauri 可选择本地文件触发模型导入 API
- [ ] 退出清理后端进程（实现 + 验证说明）
- [ ] 严格离线 env 传入子进程
- [ ] `docs/phase4-delivery.md` + CHANGELOG
- [ ] Python 测试通过（auth 有旁路/fixture）

## Defaults

- UI：sidecar 提供的 vendor web
- Auth：有 `FIGURESMITH_SESSION_TOKEN` 时启用；测试可用 `FIGURESMITH_DISABLE_AUTH=1`
- 若本机无 Rust/Node：仍提交完整脚手架，delivery 中标明构建前置条件

## Dependencies

- Phase 3 model manager API (`858245a`)
- Dev: Python venv；可选 Rust + Node + WebView2
