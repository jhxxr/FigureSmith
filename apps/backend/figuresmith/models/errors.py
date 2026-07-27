"""Structured model/offline errors for FigureSmith Phase 2."""

from __future__ import annotations

from typing import Optional


class FigureSmithError(Exception):
    """Base error with stable code and bilingual user messages."""

    code: str = "FIGURESMITH_ERROR"
    message_zh: str = "发生错误"
    message_en: str = "An error occurred"

    def __init__(
        self,
        detail: Optional[str] = None,
        *,
        message_zh: Optional[str] = None,
        message_en: Optional[str] = None,
        code: Optional[str] = None,
    ) -> None:
        if code is not None:
            self.code = code
        if message_zh is not None:
            self.message_zh = message_zh
        if message_en is not None:
            self.message_en = message_en
        self.detail = detail
        super().__init__(self.format_message())

    def format_message(self) -> str:
        base = f"[{self.code}] {self.message_zh} / {self.message_en}"
        if self.detail:
            return f"{base}\n{self.detail}"
        return base

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message_zh": self.message_zh,
            "message_en": self.message_en,
            "detail": self.detail,
        }


class Sam3ModelMissing(FigureSmithError):
    code = "SAM3_MODEL_MISSING"
    message_zh = "请先配置或导入 SAM3 权重文件"
    message_en = "Configure or import the SAM3 checkpoint first"


class Sam3ModelInvalid(FigureSmithError):
    code = "SAM3_MODEL_INVALID"
    message_zh = "SAM3 权重文件无效或不可读"
    message_en = "SAM3 checkpoint is invalid or unreadable"


class RmbgModelMissing(FigureSmithError):
    code = "RMBG_MODEL_MISSING"
    message_zh = "请先导入本地 RMBG-2.0 模型目录"
    message_en = "Import the local RMBG-2.0 model directory first"


class RmbgModelInvalid(FigureSmithError):
    code = "RMBG_MODEL_INVALID"
    message_zh = "本地 RMBG-2.0 模型目录不完整或无效"
    message_en = "Local RMBG-2.0 model directory is incomplete or invalid"


class RemoteSamDisabled(FigureSmithError):
    code = "REMOTE_SAM_DISABLED"
    message_zh = "严格离线模式下禁止使用远程 SAM 后端（fal/roboflow/api）"
    message_en = "Remote SAM backends (fal/roboflow/api) are disabled in strict offline mode"


class OfflineEndpointForbidden(FigureSmithError):
    code = "OFFLINE_ENDPOINT_FORBIDDEN"
    message_zh = "严格离线模式下仅允许本机 loopback 端点"
    message_en = "Only loopback endpoints are allowed in strict offline mode"


class PathTraversalRejected(FigureSmithError):
    code = "PATH_TRAVERSAL_REJECTED"
    message_zh = "拒绝不安全的模型路径（路径穿越）"
    message_en = "Rejected unsafe model path (path traversal)"
