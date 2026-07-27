"""Model manager facade: list / import / verify / delete local model packs."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional, Union

from figuresmith.models.errors import (
    FigureSmithError,
    ModelDeleteError,
    ModelNotInstalled,
    RmbgModelMissing,
    Sam3ModelMissing,
)
from figuresmith.models.import_rmbg import (
    MODEL_ID as RMBG_ID,
    RmbgImportResult,
    import_rmbg_pack,
    verify_installed_rmbg,
)
from figuresmith.models.import_sam3 import (
    MODEL_ID as SAM3_ID,
    Sam3ImportResult,
    import_sam3_checkpoint,
    verify_installed_sam3,
)
from figuresmith.models.paths import (
    get_app_data_dir,
    get_default_rmbg_model_dir,
    get_default_sam3_checkpoint,
    get_models_root,
)
from figuresmith.models.registry import resolve_model_paths
from figuresmith.models.settings_io import update_model_settings

PathLike = Union[str, Path]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _result_to_dict(result: Any) -> dict[str, Any]:
    if is_dataclass(result):
        raw = asdict(result)
    elif isinstance(result, dict):
        raw = dict(result)
    else:
        raw = {"value": result}
    # Path → str
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, Path):
            out[key] = str(value)
        else:
            out[key] = value
    return out


class ModelManager:
    """High-level lifecycle API used by FastAPI routes and CLI."""

    def __init__(self, app_data_dir: Optional[PathLike] = None) -> None:
        self.app_data_dir = (
            Path(app_data_dir).resolve()
            if app_data_dir is not None
            else get_app_data_dir()
        )

    # ------------------------------------------------------------------ list
    def list_models(self) -> dict[str, Any]:
        return {
            "app_data_dir": str(self.app_data_dir),
            "models_root": str(get_models_root(self.app_data_dir)),
            "models": [self.sam3_status(), self.rmbg_status()],
        }

    def sam3_status(self) -> dict[str, Any]:
        ckpt = get_default_sam3_checkpoint(self.app_data_dir)
        meta = _read_json(ckpt.parent / "metadata.json")
        installed = ckpt.is_file()
        status: dict[str, Any] = {
            "id": SAM3_ID,
            "display_name": meta.get("display_name") or "SAM 3",
            "installed": installed,
            "path": str(ckpt) if installed else str(ckpt),
            "directory": str(ckpt.parent),
            "verified": bool(meta.get("verified")) if installed else False,
            "official_verified": bool(meta.get("official_verified", False)),
            "load_verified": meta.get("load_verified", "skipped" if installed else None),
            "sha256": meta.get("sha256"),
            "imported_at": meta.get("imported_at"),
            "metadata": meta or None,
        }
        if installed:
            try:
                size = ckpt.stat().st_size
            except OSError:
                size = None
            status["size_bytes"] = size
        return status

    def rmbg_status(self) -> dict[str, Any]:
        directory = get_default_rmbg_model_dir(self.app_data_dir)
        meta = _read_json(directory / "metadata.json")
        installed = directory.is_dir() and (
            (directory / "config.json").is_file()
            or (directory / "model.safetensors").is_file()
            or bool(meta)
        )
        status: dict[str, Any] = {
            "id": RMBG_ID,
            "display_name": meta.get("display_name") or "BRIA RMBG 2.0",
            "installed": installed,
            "path": str(directory),
            "directory": str(directory),
            "verified": bool(meta.get("verified")) if installed else False,
            "official_verified": bool(meta.get("official_verified", False)),
            "load_verified": meta.get("load_verified", "skipped" if installed else None),
            "sha256": meta.get("sha256"),
            "imported_at": meta.get("imported_at"),
            "metadata": meta or None,
            "trust_remote_code_warning": meta.get("trust_remote_code_warning"),
        }
        return status

    def get_paths(self) -> dict[str, Any]:
        """Resolved paths for UI (no secrets)."""
        resolved = resolve_model_paths(
            use_defaults=True,
            app_data_dir=self.app_data_dir,
            settings_path=self.app_data_dir / "settings.json",
        )
        return {
            "app_data_dir": str(self.app_data_dir),
            "models_root": str(get_models_root(self.app_data_dir)),
            "sam3_checkpoint": str(resolved.sam3_checkpoint)
            if resolved.sam3_checkpoint
            else None,
            "sam3_bpe": str(resolved.sam3_bpe) if resolved.sam3_bpe else None,
            "rmbg_model_dir": str(resolved.rmbg_model_dir)
            if resolved.rmbg_model_dir
            else None,
            "source": resolved.source,
            "default_sam3": str(get_default_sam3_checkpoint(self.app_data_dir)),
            "default_rmbg": str(get_default_rmbg_model_dir(self.app_data_dir)),
        }

    # ---------------------------------------------------------------- import
    def import_sam3(
        self,
        source_path: PathLike,
        *,
        min_bytes: Optional[int] = None,
        max_bytes: Optional[int] = None,
        require_absolute: bool = True,
        allow_unpinned: Optional[bool] = None,
    ) -> dict[str, Any]:
        result = import_sam3_checkpoint(
            source_path,
            app_data_dir=self.app_data_dir,
            min_bytes=min_bytes,
            max_bytes=max_bytes,
            require_absolute=require_absolute,
            allow_unpinned=allow_unpinned,
        )
        return _result_to_dict(result)

    def import_rmbg(
        self,
        source_path: PathLike,
        *,
        kind: str = "auto",
        require_absolute: bool = True,
        allow_unpinned: Optional[bool] = None,
        max_files: Optional[int] = None,
        max_uncompressed_bytes: Optional[int] = None,
    ) -> dict[str, Any]:
        result = import_rmbg_pack(
            source_path,
            kind=kind,
            app_data_dir=self.app_data_dir,
            require_absolute=require_absolute,
            allow_unpinned=allow_unpinned,
            max_files=max_files,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )
        return _result_to_dict(result)

    # ---------------------------------------------------------------- verify
    def verify_sam3(self) -> dict[str, Any]:
        try:
            return verify_installed_sam3(app_data_dir=self.app_data_dir)
        except Sam3ModelMissing as exc:
            raise ModelNotInstalled(detail=exc.detail or str(exc)) from exc

    def verify_rmbg(self) -> dict[str, Any]:
        try:
            return verify_installed_rmbg(app_data_dir=self.app_data_dir)
        except RmbgModelMissing as exc:
            raise ModelNotInstalled(detail=exc.detail or str(exc)) from exc

    # ---------------------------------------------------------------- delete
    def delete_sam3(self) -> dict[str, Any]:
        ckpt = get_default_sam3_checkpoint(self.app_data_dir)
        directory = ckpt.parent
        if not directory.exists() and not ckpt.exists():
            raise ModelNotInstalled(detail=f"SAM3 not installed at {directory}")
        try:
            if directory.is_dir():
                shutil.rmtree(directory)
            elif ckpt.is_file():
                ckpt.unlink()
        except OSError as exc:
            raise ModelDeleteError(detail=f"failed to delete SAM3 at {directory}: {exc}") from exc
        update_model_settings(clear_sam3=True, app_data_dir=self.app_data_dir)
        return {"id": SAM3_ID, "deleted": True, "path": str(directory)}

    def delete_rmbg(self) -> dict[str, Any]:
        directory = get_default_rmbg_model_dir(self.app_data_dir)
        if not directory.exists():
            raise ModelNotInstalled(detail=f"RMBG not installed at {directory}")
        try:
            shutil.rmtree(directory)
        except OSError as exc:
            raise ModelDeleteError(detail=f"failed to delete RMBG at {directory}: {exc}") from exc
        update_model_settings(clear_rmbg=True, app_data_dir=self.app_data_dir)
        return {"id": RMBG_ID, "deleted": True, "path": str(directory)}


def default_manager(app_data_dir: Optional[PathLike] = None) -> ModelManager:
    return ModelManager(app_data_dir=app_data_dir)


def error_payload(exc: BaseException) -> dict[str, Any]:
    """Serialize errors for HTTP/CLI responses."""
    if isinstance(exc, FigureSmithError):
        payload = exc.to_dict()
        payload["ok"] = False
        return payload
    return {
        "ok": False,
        "code": "INTERNAL_ERROR",
        "message_zh": "内部错误",
        "message_en": "Internal error",
        "detail": str(exc),
    }
