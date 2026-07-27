# FigureSmith 阶段二：本地 SAM3/RMBG 加载与严格离线

## Goal

在阶段一仓库骨架上，实现 **真正的本地模型加载**：SAM3 使用显式本地 checkpoint 且 `load_from_HF=False`；RMBG 仅从本地目录加载且 `local_files_only=True`；桌面/严格离线路径下禁止 Hugging Face / Roboflow / fal.ai 静默回退；补齐模型路径配置与可自动化的离线防护测试。

## Background

- 阶段一已完成：`vendor/autofigure_edit` 基线、`apps/backend/figuresmith` 边界、loopback 启动、合规文档（commit `ac9e9f9`）
- 上游现状（问题）：
  - `build_sam3_image_model(device=..., bpe_path=...)` **未传** `checkpoint_path`，且未设 `load_from_HF=False` → 缺权重时可能访问 Hugging Face
  - `BriaRMBG2Remover` 本地路径存在时可本地加载，但未设 `local_files_only=True`；缺失时回退 `briaai/RMBG-2.0` + HF token
  - `sam_backend` 仍支持 `fal` / `roboflow` / `api`
  - CLI 已有 `--rmbg_model_path`，**没有** `--sam_checkpoint_path` / `--sam_bpe_path` / `--strict_offline`
  - `RunRequest` 无对应本地路径与严格离线字段
- 阶段三才做完整模型导入 UI/ZIP；本阶段先打通加载链路与安全默认值

## Scope

### In Scope

1. **SAM3 本地加载**
   - `segment_with_sam3` 增加 `sam_checkpoint_path`、`sam_bpe_path`（可选）
   - 本地加载：`build_sam3_image_model(..., checkpoint_path=..., bpe_path=..., load_from_HF=False)`
   - 缺 checkpoint / 文件不存在 → 明确错误（中英消息），不访问 HF，不回退远程 SAM
2. **RMBG 本地加载**
   - `from_pretrained(..., local_files_only=True)` 仅加载本地目录
   - 删除/禁用严格路径下的 HF 仓库名下载回退
   - 缺失模型 → 结构化错误（如 `RMBG_MODEL_MISSING`）
3. **严格离线模式**
   - 启动时设置 `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` / `HF_DATASETS_OFFLINE` / `NO_PROXY`
   - `validate_offline_endpoint(base_url)`：解析 host，仅允许 loopback，防 `localhost.evil.com` 绕过
   - `strict_offline=True` 时禁止 Roboflow / fal / 非本机 OpenAI base URL
4. **模型路径配置（注册表最小版）**
   - 从应用数据目录或环境变量/配置读取 SAM3/RMBG 路径
   - **服务端不信任前端任意本机路径**；CLI 可显式传路径供开发
   - `resources/model-manifest.json` 填充支持的模型元数据骨架
5. **API / CLI 接线**
   - CLI：`--sam_checkpoint_path`、`--sam_bpe_path`、`--strict_offline`
   - `RunRequest`：增加 `strict_offline`；路径由后端注册表/环境解析
   - 默认 `sam_backend=local`；严格离线下拒绝非 local
6. **测试与文档**
   - 单元：离线 endpoint、路径安全、缺模型错误
   - 无权重/无 GPU 时控制流测试必须通过
   - `docs/phase2-delivery.md` + `CHANGELOG.md`

### Out of Scope

- 完整模型导入向导 / ZIP Slip 导入 UI（阶段三）
- Tauri 封装（阶段四）
- Runtime Pack / Installer（阶段六）
- 完整显存双模式常驻管理（可后置）

## Constraints

1. 不自动下载 gated 模型；不把权重写入 git
2. 不得出现：本地缺失 → HF / Roboflow / fal 静默回退
3. 后端只绑定 127.0.0.1（延续阶段一入口）
4. 上游修改保持可 diff：最小补丁 + `figuresmith` 自有模块承载安全逻辑
5. 用户可见错误提供中英（至少关键路径）

## Acceptance Criteria

- [ ] 本地 SAM3 调用使用显式 `checkpoint_path` 且 `load_from_HF=False`
- [ ] 未配置/缺失 SAM3 权重时直接失败并提示，无 HF 访问意图
- [ ] 本地 RMBG 使用 `local_files_only=True`；缺失时明确错误，无 HF 下载回退（严格路径）
- [ ] `strict_offline` 设置离线环境变量；远程 SAM 与非 loopback endpoint 被拒绝
- [ ] `validate_offline_endpoint` 拒绝 `localhost.example.com` / `127.0.0.1.example.com` 类绕过
- [ ] CLI 支持 `--sam_checkpoint_path`、`--sam_bpe_path`、`--strict_offline`
- [ ] 服务端模型路径来自注册表/环境，默认不接受任意客户端路径覆盖
- [ ] 单元测试覆盖离线校验、缺模型、路径/registry；无权重时仍可通过
- [ ] `docs/phase2-delivery.md` 含修改清单、启动命令、已知限制
- [ ] `CHANGELOG.md` 更新

## Defaults (unless overridden)

- 无 GPU 机器：控制流测试即可验收
- 保留 fal/roboflow 源码但 strict/FigureSmith 默认不可达
- FigureSmith launcher 默认 `FIGURESMITH_STRICT_OFFLINE=1`

## Dependencies

- Phase 1 commit: `ac9e9f9`
- Upstream: `vendor/autofigure_edit/autofigure2.py`, `server.py`
