# FigureSmith 阶段三：模型管理器（导入/校验/回滚）

## Goal

在阶段二本地加载契约之上，实现 **可安全导入、校验、删除与失败回滚** 的模型管理器：用户手动导入 SAM3 权重与 RMBG-2.0 包（ZIP 或文件夹），写入应用数据目录，生成 `metadata.json` / checksum，验证失败不破坏已可用旧模型；并暴露后端 API（及开发用 CLI），为阶段四/五桌面 UI 提供能力。

## Background

- 阶段二（`b5a5d6c`）已具备：路径注册表、本地加载 kwargs、严格离线、缺模型 fail-closed
- 用户仍只能手动设 env / 拷贝文件；无导入、无哈希钉死、无原子替换
- 原始方案 §4 / 阶段三要求：
  - SAM3：选 `.pt` → 校验 → 复制 → 验证 → metadata
  - RMBG：ZIP 或文件夹 → Zip Slip 防护 → 必要文件检查 → 验证 → metadata
  - 哈希匹配显示“官方已验证”；不匹配默认拒绝（开发模式可放宽）
  - 导入失败回滚，不覆盖可用旧模型

## Scope

### In Scope

1. **SAM3 导入**
   - 接受用户选择的 `sam3.pt`（扩展名、大小合理性、SHA-256）
   - 复制到 `%LOCALAPPDATA%\FigureSmith\models\sam3\`（或 `FIGURESMITH_DATA_DIR`）
   - 写入 `metadata.json`、`checksum.sha256`
   - 验证：至少文件级 + 可选“轻量加载探测”（无 GPU 时跳过推理，标记 `verified_load=skipped`）
   - 失败：删除临时目录/文件，不覆盖已 verified 旧模型
2. **RMBG 导入**
   - ZIP 或完整文件夹
   - Zip Slip 防护：禁绝对路径、`..`、超量文件/体积、软链逃逸（Windows 上尽量防御）
   - 检查必要文件：`config.json`、`model.safetensors`、`preprocessor_config.json`（及 manifest 列出的 py 文件若存在）
   - `local_files_only` 契约校验；可选加载探测
   - 哈希与 `resources/model-manifest.json` 对比；匹配 → `official_verified`；不匹配 → 默认拒绝（`FIGURESMITH_ALLOW_UNPINNED_MODELS=1` 开发放行）
3. **模型生命周期 API / CLI**
   - 列表状态、验证、删除、打开目录（CLI 或 API）
   - 更新 settings / registry 使阶段二加载器自动发现
4. **安全与合规文案**
   - 导入 RMBG 时提示 trust_remote_code / 仅可信来源
   - 源码许可 ≠ 权重许可
5. **测试**
   - SHA-256、Zip Slip、回滚、manifest 匹配/拒绝、路径穿越
   - 不依赖真实 GB 级权重（用临时小文件/fake zip fixtures）
6. **文档**
   - `docs/phase3-delivery.md`、CHANGELOG、development 更新

### Out of Scope

- Tauri 原生文件选择器与完整桌面 UI（阶段四/五）——本阶段可提供 **HTTP/CLI 能力**；Tauri command 可留 stub 接口文档
- 真实 GPU 端到端分割集成（optional mark）
- Runtime Pack 打包
- 删除 vendor 远程代码

## Constraints

1. 不把权重提交进 git；导入目标仅在 app data
2. 导入失败不得破坏已可用模型（staging + atomic replace）
3. 正式路径默认拒绝未知哈希；开发开关显式
4. 大文件不经 HTTP multipart 上传作为首选（API 可接受 **本机已存在路径** 的 import 请求，由后端复制；为阶段四 Tauri 选文件做准备）
5. 严格离线：导入/校验过程不访问 HF/公网
6. 中英错误消息

## Acceptance Criteria

- [ ] 可导入 SAM3 `.pt` 到 app data，生成 metadata + sha256
- [ ] 可导入 RMBG ZIP（Zip Slip 防护）与文件夹
- [ ] 校验失败回滚，旧模型仍可用
- [ ] manifest 哈希不匹配默认拒绝；开发开关可放行
- [ ] 可列出/删除/重新验证模型状态
- [ ] 导入后阶段二 registry 能解析到新路径
- [ ] 单元测试覆盖 hash、zip slip、rollback、unpin policy；无真实权重仍通过
- [ ] `docs/phase3-delivery.md` + CHANGELOG
- [ ] 无模型权重进入 git

## Defaults

- Staging 目录：`<app_data>/models/.staging/<id>-<uuid>/`
- 最终目录：`<app_data>/models/sam3/`、`<app_data>/models/rmbg-2.0/`
- 原子替换：staging 验证通过后 `replace` / swap
- 无 GPU：`verified=true` 可基于文件契约；`load_verified` 可为 false/skipped

## Dependencies

- Phase 2 commit `b5a5d6c`
- `figuresmith.models.{paths,registry,sam3_loader,rmbg_loader,errors}`
- `resources/model-manifest.json`
