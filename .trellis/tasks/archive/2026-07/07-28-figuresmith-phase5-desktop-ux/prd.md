# FigureSmith 阶段五：桌面体验（向导/模型页/历史/SVG）

## Goal

在阶段四 Tauri Sidecar 之上，交付 **可日常使用的桌面体验**：首次启动向导、硬件检测、模型管理页、创建/任务运行页去远程 SAM 化、历史记录与 SVG 编辑入口、双语错误与日志脱敏；产品品牌统一为 **FigureSmith / 图匠**。

## Background

- 阶段四已交付（`e37ec65`）：Tauri 壳、Sidecar、Token、原生导入 command；测试 186 passed
- 当前 Web UI 仍是 vendor `web/`：品牌为 AutoFigure-Edit，仍暴露 fal/Roboflow SAM 选项
- 阶段三已有 `/api/models/*`；阶段二有本地加载与严格离线

## Scope

### In Scope

1. **品牌与导航**：FigureSmith / 图匠；统一顶栏；不用上游主 Logo
2. **欢迎页 + 首次向导**：环境检查 → 导入 SAM3 → 导入 RMBG → 配置生成模型；可跳过；持久化 onboarding 状态
3. **硬件检测**：`GET /api/system/status`；无 CUDA 友好中英提示，不崩溃
4. **模型管理页**：状态卡片；导入/验证/删除/打开目录（桌面走 Tauri）
5. **创建与运行**：SAM 固定 Local SAM3；无 Roboflow/fal/HF_TOKEN 正式 UI；流水线步骤 + 日志脱敏
6. **历史 + SVG 编辑**：列表/打开产物；svg-edit 入口可用
7. **测试与文档**：system status 测试、UI 契约测试、`docs/phase5-delivery.md`、CHANGELOG

### Out of Scope

- Installer / Runtime Pack（阶段六）
- 全盘 React 重写
- 内置本地生图大模型 / CPU SAM 承诺

## Constraints

1. 不引入远程 SAM 作为正式 UI 选项或静默回退
2. 不展示 HF_TOKEN 桌面主路径
3. 不把 API Key 新写入明文 settings.json（本阶段）
4. 延续严格离线、127.0.0.1、session token
5. 权重不进 git

## Acceptance Criteria

- [ ] 用户可见品牌为 FigureSmith
- [ ] 欢迎页与可跳过向导；状态可持久化
- [ ] `GET /api/system/status` 可用；无 CUDA 不崩溃并有提示文案
- [ ] 模型管理页可展示并触发导入/验证/删除
- [ ] 创建页 SAM 固定本地；无 Roboflow/fal 正式选项；无 HF_TOKEN 字段
- [ ] 任务运行有流水线步骤；日志脱敏 helper 存在并有测试
- [ ] 历史与 SVG 编辑入口可用
- [ ] Python 测试通过；含 system/status 与关键 UI 契约
- [ ] `docs/phase5-delivery.md` + CHANGELOG

## UI Strategy (default)

增量改造 vendor web + 新增静态页（welcome/models），FastAPI 挂载；不一次性重写 React 应用。

## Dependencies

- Phase 4: `e37ec65`
- Phase 3 models API / Phase 2 local load
