# Design: UI 双主题 + 首次打开流程现代化 + Create 重排

## Architecture / Boundaries

| 层 | 路径 | 职责 |
|----|------|------|
| 共享 token + 组件 | `apps/backend/figuresmith/static/ui/common.css` | 权威 light/dark CSS 变量、通用组件 |
| 主题运行时 | `apps/backend/figuresmith/static/ui/common.js` | 读/写偏好、解析 system、设 `data-theme`、渲染三态控件 |
| Welcome / Models | `static/ui/welcome.*` `models.*` | 消费 token；Welcome 布局现代化 |
| 主流程 | `vendor/autofigure_edit/web/styles.css` + 各 HTML + `app.js` | token 映射；去外链字体；顶栏主题控件；Create 结构重排 |
| 桌面 splash | `apps/desktop/index.html` + `src/main.ts` | 内联同等 token；阶段 UI 现代化 |
| 挂载 | `apps/backend/main.py` `_mount_figuresmith_ui` | 仅当新增静态文件时登记 |

**不修改**：`vendor/svg_edit/**`、SVG-Edit iframe、后端 API 契约。

## Theme contract

- Storage key：`figuresmith_theme_v1`，值：`light` | `dark` | `system`。
- 解析：`system` → `matchMedia('(prefers-color-scheme: dark)')` → `dark` 或 `light`。
- DOM：`html[data-theme="light|dark"]`（解析结果），`html[data-theme-preference="light|dark|system"]`。
- `color-scheme` 与解析结果一致。
- preference === `system` 时监听 media `change`。
- 控件：Light / Dark / System（中文：浅色 / 深色 / 系统），与语言切换并列。
- `FigureSmithUI`：`getThemePreference` / `setThemePreference` / `resolveTheme` / `applyTheme` / `renderThemeSwitch`。
- 主流程 HTML 引入 `/fs/common.js`；`app.js` 启动时 `applyTheme` + 插入 theme switch。

## Token mapping

**Light**：暖纸底 + 青绿 accent（贴近现 vendor）。  
**Dark**：石墨 + 青绿磷光（贴近现 Welcome）。

vendor `styles.css`：删除 Google Fonts `@import`；旧变量（`--bg-1`、`--ink`、`--accent`…）映射到 `--fs-*` 或双重赋值。

## First-run UX（视觉 only）

### Desktop splash

- 单卡片：品牌、标题、阶段说明、进度条、错误态。
- `main.ts` 事件协议不变；可加 phase class 驱动进度。

### Welcome

- Hero + 状态网格收紧；向导步骤更紧凑；成功/失败更明确。
- **不改变** `STEPS`、`/api/system/status`、`/api/system/onboarding`。

## Create 表单重排

建议信息架构（实现时可微调，以保留 id 为准）：

1. **主列**：Method Text（核心输入）
2. **侧列 / 次卡**：
   - Pipeline 路由摘要（只读摘要优先）
   - AI 提供商绑定 + 模型
   - 图片提供商绑定 + 模型
   - 凭证与 Base URL（可与绑定合并视觉分组）
3. **高级折叠**（`<details>` 或同类）：Optimize、Image Size、Upscale、SAM Prompt、Reference Image 等
4. **底栏动作**：Confirm → Canvas

约束：所有现有 `id` 保留；binding 按钮与 hidden provider 字段保留；不删配置项。

## Compatibility / Trade-offs / Rollback

- i18n key `autofigure_locale_v1` 不变；主题独立键。
- common.js 单实现 vs splash 内联 token 副本（注释同步）。
- 纯前端回滚；无 DB 迁移。
