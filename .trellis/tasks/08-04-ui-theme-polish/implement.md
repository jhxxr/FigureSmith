# Implement: UI 双主题 + 首启现代化 + Create 重排

## Checklist（顺序）

1. **Theme runtime（`common.js`）** — storage / resolve / apply / media / `renderThemeSwitch`；`renderNav` 挂载
2. **Token（`common.css`）** — light 默认 + `[data-theme="dark"]`；组件吃 token
3. **Welcome 现代化** — `welcome.html` / `welcome.css`（及必要文案）；不改 STEPS/API
4. **Models** — 对齐 token；去掉硬编码色
5. **Vendor 主流程主题** — `styles.css` 去 Google Fonts + token/dark；HTML 引入 `/fs/common.js`；`app.js` applyTheme + 控件
6. **Create 表单重排** — `index.html` 分组/折叠；必要时微调 `styles.css` / `app.js` 布局类；**保留全部 id**
7. **Import / History / Guide / Canvas 外壳** — 随 styles 主题化；顶栏控件一致
8. **Desktop splash** — `index.html` + `main.ts` 进度/阶段视觉
9. **挂载检查** — `main.py` 仅新增文件时改
10. **自测** — 见 Validation

## Risky files

| 文件 | 风险 |
|------|------|
| `vendor/.../styles.css` | 面广 |
| `vendor/.../index.html` | Create 重排 |
| `vendor/.../app.js` | 初始化 / 选择器 |
| `static/ui/common.js` | 多页依赖 |
| `apps/desktop/src/main.ts` | 启动体验 |
| `welcome.js` | 误伤向导逻辑 |

## Validation

```text
rg "fonts.googleapis" vendor/autofigure_edit/web apps/backend/figuresmith/static apps/desktop

# 手工
1. /welcome.html：三态主题，刷新保持；检查向导
2. Create：重排后字段齐全；binding 保存/选择；Confirm
3. Import / History / Guide / Canvas 外壳同主题
4. Models 可读
5. splash phase 文案与错误
6. preference=system 随系统外观
7. 无外链字体；SVG-Edit iframe 未改
```

## Before `task.py start`

- [x] prd / design / implement
- [x] implement.jsonl / check.jsonl
- [ ] 用户批准最终规划总结
- [ ] 然后 `task.py start` 再改产品代码
