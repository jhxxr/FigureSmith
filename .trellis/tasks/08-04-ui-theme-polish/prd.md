# 统一并美化 FigureSmith 全量 UI（双主题）

## Goal

把 FigureSmith 各页面统一成一套可切换的浅色 / 深色设计系统，并把**首次打开检测流程**（桌面启动 splash + Welcome 环境检查 / 向导）重新设计为简洁现代化风格；允许对 Create 表单做适度信息层级重排以提升可读性。

用户价值：冷启动时一眼看到“系统已准备就绪”；日常使用时浅/深主题一致、可切换；Create 配置区更清晰；离线桌面无外链字体依赖。

## Background / Confirmed Facts

### 产品与 UI 来源

- FigureSmith：本地优先科研插图工具（Tauri 2 + Python sidecar）。
- 主流程页：`vendor/autofigure_edit/web/`（Create / Import / History / Canvas / Guide），共享 `styles.css` + `app.js`；当前浅色学术台面，含 Google Fonts `@import`。
- 自有页：`apps/backend/figuresmith/static/ui/`（Welcome / Models），共享 `common.css` + `common.js`；当前深色石墨 + 青绿。
- 桌面 splash：`apps/desktop/index.html` + `apps/desktop/src/main.ts`（内联深色；监听 `startup-status`）。
- Welcome 向导步骤（业务逻辑保留）：`env` → `sam3` → `rmbg` → `provider` → `done`（`welcome.js`）。
- 语言偏好：`localStorage.autofigure_locale_v1`。
- **尚无主题系统**；SVG-Edit 内嵌编辑器明确不改。

### 用户已确认决策

| 决策 | 选择 |
|------|------|
| 流程 | Trellis 规划后实现 |
| 视觉 | 浅 / 深双主题可切换 |
| 默认主题（无偏好） | **跟随系统** `prefers-color-scheme` |
| 主题控件 | **三态**：light / dark / system |
| 首次打开检测 | **重新设计为简洁现代化**（不改业务逻辑 / API） |
| 美化深度 | **允许适度重排 Create 表单信息层级**（保留字段 id 与提交逻辑） |
| SVG-Edit | 不动 |

## Requirements

### R1 — 统一设计令牌

- 跨页面共享 design tokens（色、半径、阴影、字号、间距、焦点环）。
- light / dark 两套解析结果；system 模式按系统偏好解析为 light 或 dark。
- Welcome / Models / Create / Import / History / Canvas 外壳 / Guide / 桌面 splash 视觉同族。

### R2 — 主题切换与持久化

- 控件三态：`light` | `dark` | `system`。
- 偏好写入 `localStorage`（键名：`figuresmith_theme_v1`）。
- 无偏好时按 system 解析。
- 当前页即时生效；跨页读存储；system 时监听 `prefers-color-scheme` 变化。

### R3 — 首次打开检测流程（重点）

**桌面 splash（`apps/desktop`）**

- 简洁现代化卡片：品牌 + 阶段文案 + 进度反馈 + 错误态。
- 阶段仍来自 `startup-status`：`locating` / `verifying` / `starting` / `ready` / `error`。
- 失败态保留现有 code 文案，展示更清晰。

**Welcome 环境检查 / 向导**

- 极简卡片布局：清晰主 CTA、状态网格、进度条、步骤条精简。
- 成功态明确“已就绪”；失败 / 需关注态具体到缺什么。
- 步骤业务顺序与 API 调用不变；可改 DOM 结构与样式，保留关键 id 与 JS 钩子。

### R4 — Create 表单层级（允许重排）

- 允许重组 Create 页区块顺序与分组（例如：正文输入 / 路由摘要 / 提供商绑定 / 高级选项折叠），使主路径更短、次要配置下沉。
- **必须保留**现有控件 `id`、隐藏字段、提交与 binding 逻辑；`app.js` 选择器尽量不破。
- 不新增业务能力；不删除已有配置项（可折叠隐藏默认不常用项）。

### R5 — 页面覆盖

1. Welcome  2. Models  3. Create  4. Import  5. History  
6. Canvas 外壳（非 iframe SVG-Edit）  7. Guide  8. 桌面 splash

### R6 — 离线与桌面

- 去掉对 `fonts.googleapis.com` 的强制依赖；系统字体栈。
- 鉴权 / bridge / i18n 不回退；尊重 `prefers-reduced-motion`。

### R7 — 美化质量

- 统一按钮、输入、卡片、导航、badge、alert、focus。
- 深色下表单对比度达标。

### R8 — 兼容

- 尽量保留 DOM id / 关键 class；改 class 则同步 JS。
- 中英 i18n 继续工作。

## Out of Scope

- SVG-Edit 内部主题
- 生成管线 / 模型导入协议等业务逻辑变更
- Storybook / 设计文档站
- 云同步主题
- 移动端原生 App

## Acceptance Criteria

- [ ] AC1：列出的 8 处 UI 在 light/dark 下同族 token，不再一半深一半浅
- [ ] AC2：三态切换可用；刷新与跳转后偏好保持；system 随系统变化
- [ ] AC3：无偏好时按 system 解析
- [ ] AC4：splash + Welcome 检测流程视觉简洁现代化；成功/失败态清晰；业务步骤与 API 行为不变
- [ ] AC5：Create 表单信息层级更清晰（重排/分组/折叠允许）；全部原有配置项仍可访问；提交与 binding 行为不变
- [ ] AC6：离线不请求 Google Fonts；页面可渲染
- [ ] AC7：Canvas 仅外壳主题化；iframe 内 SVG-Edit 外观不变
- [ ] AC8：导航、语言、表单、模型导入等冒烟通过
- [ ] AC9：键盘 focus 可见；`prefers-reduced-motion: reduce` 时无多余动画

## Open Questions

（无阻塞项）

## Risks

- vendor `styles.css` / `index.html` / `app.js` 耦合 → 重排时保留 id，先结构后样式
- 双主题散落多文件 → 单一 token 源（`common.css` + vendor 映射）
- 去 Google Fonts 后字重变化 → 系统字体栈 + 字号微调验收

## Notes

- 与 `08-04-custom-api-base-url` 并行；本任务不实现 API base URL。
- 实现前需用户批准本规划总结后 `task.py start`。
