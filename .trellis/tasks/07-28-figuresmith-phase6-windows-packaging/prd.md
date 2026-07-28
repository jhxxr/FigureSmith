# FigureSmith 阶段六：Windows 打包与发布

## Goal

交付可分发的 **Windows x86_64** 发布产物：Tauri 安装包/便携包、**不含模型权重** 的 Runtime Pack、校验和与发布说明；支持用户在无网环境用预下载 Runtime + 手动导入模型运行 FigureSmith。

## Background

- 阶段一～五已完成（产品 commit `a5a4454`）
- `scripts/build-desktop.ps1` 已能调 tauri build；`build-runtime.ps1` 仍为占位
- 目标产物：Setup exe、Portable zip、Runtime zip、checksums.txt
- **禁止** 发布物与 git 含模型权重

## Scope

### In Scope

1. 完善 desktop 构建：命名产物、`dist-desktop/`、portable zip、附带许可证
2. 实现 Runtime Pack 脚本：目录骨架、依赖说明/安装脚本、排除权重
3. checksums 生成
4. 发布文档与（可选）GitHub Actions 草案
5. CHANGELOG / README 发布说明

### Out of Scope

- 自动下载 gated 模型
- macOS/Linux 包
- 强制代码签名（可预留钩子）

## Constraints

1. 发布物零权重
2. 不默认开放局域网
3. 优先 Runtime 目录 + Sidecar，非 onefile
4. dist 目录 gitignore
5. 产品名 FigureSmith

## Acceptance Criteria

- [ ] `build-desktop.ps1` 产出规范命名 installer/portable（或清晰失败原因）
- [ ] `build-runtime.ps1` 生成 Runtime 骨架且 `contains_weights: false`
- [ ] checksums 流程存在
- [ ] `docs/phase6-delivery.md` + `docs/release.md`
- [ ] 打包路径测试排除 `*.pt`/`*.safetensors`
- [ ] CHANGELOG 更新；Python 测试仍通过

## Dependencies

- Phase 5: `a5a4454`
