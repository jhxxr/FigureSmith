"""FastAPI routes for Phase 3 model manager (local path import only)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from figuresmith.models.errors import FigureSmithError
from figuresmith.models.manager import ModelManager, error_payload

router = APIRouter(prefix="/api/models", tags=["models"])


class ImportSam3Request(BaseModel):
    source_path: str = Field(..., description="Absolute local path to sam3.pt / .pth")
    min_bytes: Optional[int] = Field(
        default=None,
        description="Optional minimum size override (tests/dev)",
    )
    max_bytes: Optional[int] = Field(default=None, description="Optional maximum size override")


class ImportRmbgRequest(BaseModel):
    source_path: str = Field(..., description="Absolute local path to ZIP or model directory")
    kind: Literal["auto", "zip", "dir"] = "auto"


def _manager_from_request(request: Request) -> ModelManager:
    """Prefer app.state override (tests), else FIGURESMITH_DATA_DIR / default."""
    override = getattr(request.app.state, "figuresmith_app_data_dir", None)
    if override:
        return ModelManager(app_data_dir=Path(override))
    env_dir = os.environ.get("FIGURESMITH_DATA_DIR")
    if env_dir and str(env_dir).strip():
        return ModelManager(app_data_dir=Path(env_dir))
    return ModelManager()


def _http_error(exc: BaseException) -> HTTPException:
    payload = error_payload(exc)
    status = 400
    code = payload.get("code") or ""
    if code in {"MODEL_NOT_INSTALLED", "SAM3_MODEL_MISSING", "RMBG_MODEL_MISSING"}:
        status = 404
    elif code in {"MODEL_IMPORT_PIN_MISMATCH", "MODEL_IMPORT_ZIP_SLIP", "PATH_TRAVERSAL_REJECTED"}:
        status = 400
    elif code == "INTERNAL_ERROR":
        status = 500
    return HTTPException(status_code=status, detail=payload)


@router.get("")
def list_models(request: Request) -> dict[str, Any]:
    """List installed model status under app data."""
    mgr = _manager_from_request(request)
    return mgr.list_models()


@router.get("/paths")
def model_paths(request: Request) -> dict[str, Any]:
    """Return resolved model paths (no secrets)."""
    mgr = _manager_from_request(request)
    return mgr.get_paths()


@router.post("/sam3/import")
def import_sam3(body: ImportSam3Request, request: Request) -> dict[str, Any]:
    """Import SAM3 checkpoint from a local absolute path (no multipart upload)."""
    mgr = _manager_from_request(request)
    try:
        result = mgr.import_sam3(
            body.source_path,
            min_bytes=body.min_bytes,
            max_bytes=body.max_bytes,
            require_absolute=True,
        )
        return {"ok": True, **result}
    except FigureSmithError as exc:
        raise _http_error(exc) from exc
    except Exception as exc:  # pragma: no cover - unexpected
        raise _http_error(exc) from exc


@router.post("/sam3/verify")
def verify_sam3(request: Request) -> dict[str, Any]:
    mgr = _manager_from_request(request)
    try:
        result = mgr.verify_sam3()
        return {"ok": True, **result}
    except FigureSmithError as exc:
        raise _http_error(exc) from exc


@router.delete("/sam3")
def delete_sam3(request: Request) -> dict[str, Any]:
    mgr = _manager_from_request(request)
    try:
        result = mgr.delete_sam3()
        return {"ok": True, **result}
    except FigureSmithError as exc:
        raise _http_error(exc) from exc


@router.post("/rmbg/import")
def import_rmbg(body: ImportRmbgRequest, request: Request) -> dict[str, Any]:
    """Import RMBG pack from a local absolute ZIP or directory path."""
    mgr = _manager_from_request(request)
    try:
        result = mgr.import_rmbg(
            body.source_path,
            kind=body.kind,
            require_absolute=True,
        )
        return {"ok": True, **result}
    except FigureSmithError as exc:
        raise _http_error(exc) from exc
    except Exception as exc:  # pragma: no cover
        raise _http_error(exc) from exc


@router.post("/rmbg/verify")
def verify_rmbg(request: Request) -> dict[str, Any]:
    mgr = _manager_from_request(request)
    try:
        result = mgr.verify_rmbg()
        return {"ok": True, **result}
    except FigureSmithError as exc:
        raise _http_error(exc) from exc


@router.delete("/rmbg")
def delete_rmbg(request: Request) -> dict[str, Any]:
    mgr = _manager_from_request(request)
    try:
        result = mgr.delete_rmbg()
        return {"ok": True, **result}
    except FigureSmithError as exc:
        raise _http_error(exc) from exc


def create_models_app(*, app_data_dir: Optional[Path] = None):
    """Standalone FastAPI app with only model routes (tests / minimal server)."""
    from fastapi import FastAPI

    app = FastAPI(title="FigureSmith Model Manager", version="0.3.0")
    if app_data_dir is not None:
        app.state.figuresmith_app_data_dir = str(app_data_dir)
    app.include_router(router)
    return app


def mount_models_routes(app, *, app_data_dir: Optional[Path] = None) -> None:
    """Attach model manager routes onto an existing FastAPI app (vendor server)."""
    if app_data_dir is not None:
        app.state.figuresmith_app_data_dir = str(app_data_dir)
    app.include_router(router)
