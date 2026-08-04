# 修复并支持自定义 API Base URL

## Goal

允许用户在继续已有图片/生成流程时配置自定义 OpenAI 兼容 API Base URL，并避免 URL 被重复拼接；移除严格离线模式对 API endpoint 的 loopback 限制，使用户配置的远程自定义服务可以正常使用。

## Confirmed facts

- `vendor/autofigure_edit/autofigure2.py:100-159` 已存在 `custom` provider 和 `AUTOFIGURE_CUSTOM_BASE_URL`，但自定义 URL 的完整配置/继续流程生效链路仍需修复。
- `apps/backend/figuresmith/security/offline.py:168-203` 当前在严格离线模式下只允许 loopback URL。
- 当前错误中的实际值是 `https://api.orbitaiapi.sitehttps://api.orbitaiapi.site`，说明自定义 URL 在某个配置/拼接路径中被重复连接。
- `tests/test_offline_endpoint.py:96-109` 和 `tests/test_strict_offline_network_canary.py` 覆盖了现有 endpoint 拒绝策略。

## Requirements

- R1: 自定义 Base URL 可由用户配置，并在继续已有图片流程时生效。
- R2: URL 规范化必须识别完整 URL，不能把一个已经包含 scheme 的 URL 再次拼接到自身或默认前缀上；兼容带/不带末尾 `/` 及常见 `/v1` 路径。
- R3: 自定义 provider 的文本与图片调用使用同一个明确的有效 Base URL；错误信息应指出实际解析后的 URL。
- R4: 删除严格离线模式的 endpoint loopback 限制：`validate_offline_endpoint` 不再以“必须是 loopback”为理由拒绝用户配置的远程 HTTP(S) 自定义 API；`validate_effective_offline_policy` 不再阻止远程 custom provider。
- R5: 删除或更新所有依赖“严格离线只能访问本机 endpoint”的代码、测试和用户提示，避免实现与文档矛盾。保留 Hugging Face/Transformers 离线环境变量的行为仅当它们不再阻止用户配置的 API 请求；若现有严格离线总开关仍会阻止远程 API，请同步移除该阻断链路。
- R6: 配置错误应在发起 HTTP 请求前被发现，并返回可理解的错误；URL 解析失败不能退化为错误拼接。
- R7: Provider binding API keys must be kept in secure persistent storage; they must not be written as plaintext settings.

## Acceptance Criteria

- [ ] 输入 `https://api.orbitaiapi.site` 后，最终 URL 不再出现重复 scheme/host。
- [ ] 输入带 `/v1`、末尾 `/` 或不带 scheme 的自定义地址时，规范化结果稳定且不会生成双斜杠或重复路径。
- [ ] 即使默认严格离线环境变量开启，远程自定义 HTTP(S) 地址也不会因 loopback 策略被拒绝。
- [ ] 用户配置远程自定义地址后，文本和图片请求都会使用该地址；测试使用 mock transport，不连接真实服务。
- [ ] 已上传图片继续流程会沿用用户选择的自定义 provider/base URL，而不是回退到默认 provider。
- [ ] 原有 endpoint loopback 拒绝测试被改为反映新契约，新增/更新测试覆盖远程 custom、重复 URL 和规范化场景。
- [ ] 现有非 endpoint 相关测试继续通过，且代码/文案不再声称严格离线只允许 loopback API。

## Out of scope

- 不实现新的云厂商 SDK 或供应商专用协议。
- 不修改本地模型权重下载策略，除非当前严格离线环境变量会意外阻止已配置的 API 请求。

## Key decision

- 按用户明确要求，删除 endpoint loopback 强制策略，而不是增加“允许远程 API”开关。远程自定义 API 由用户配置后直接可用；这会降低网络隔离强度，属于有意的产品行为变更。

## Additional product requirements from latest clarification

- R8: Provider 配置改为可绑定的命名配置，而不是当前内置 provider 预设按钮/选项。
- R9: 删除现有预设 provider（包括 Bianxie、OpenRouter、Gemini、OpenAI 等固定预设展示），用户通过绑定配置填写名称、Base URL、API Key 和模型。
- R10: 将路由拆成两个独立绑定：一个“图片生成 API 提供商”，一个“普通 AI 提供商”；两者可分别选择不同绑定，也可选择同一绑定。
- R11: 绑定配置应保存，方便下次继续使用。
- R12: API Key 也要保存，用户下次选择绑定后无需重新填写；密钥不得明文写入 `settings.json`，应使用操作系统凭据存储或项目已有的安全存储机制。

## Open questions

无。
