"""Resolve local SAM3 / RMBG model paths from env, settings, and defaults."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from figuresmith.models.paths import (
    get_app_data_dir,
    get_default_rmbg_model_dir,
    get_default_sam3_checkpoint,
    get_settings_path,
)

ENV_SAM3_CHECKPOINT = "FIGURESMITH_SAM3_CHECKPOINT"
ENV_SAM3_BPE = "FIGURESMITH_SAM3_BPE"
ENV_RMBG_MODEL_PATH = "FIGURESMITH_RMBG_MODEL_PATH"


@dataclass(frozen=True)
class ModelPaths:
    """Resolved model path hints (may not exist on disk yet)."""

    sam3_checkpoint: Optional[Path]
    sam3_bpe: Optional[Path]
    rmbg_model_dir: Optional[Path]
    source: str  # e.g. "cli", "env", "settings", "default", "mixed"


def _read_settings(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _settings_model_paths(settings: dict[str, Any]) -> dict[str, Optional[str]]:
    models = settings.get("models") if isinstance(settings.get("models"), dict) else {}
    # Support both nested models.* and flat keys.
    sam3 = models.get("sam3_checkpoint") or settings.get("sam3_checkpoint")
    bpe = models.get("sam3_bpe") or settings.get("sam3_bpe")
    rmbg = models.get("rmbg_model_path") or settings.get("rmbg_model_path")
    return {
        "sam3_checkpoint": str(sam3) if sam3 else None,
        "sam3_bpe": str(bpe) if bpe else None,
        "rmbg_model_path": str(rmbg) if rmbg else None,
    }


def resolve_model_paths(
    *,
    sam_checkpoint_path: Optional[str] = None,
    sam_bpe_path: Optional[str] = None,
    rmbg_model_path: Optional[str] = None,
    use_defaults: bool = True,
    settings_path: Optional[Path] = None,
    app_data_dir: Optional[Path] = None,
) -> ModelPaths:
    """Resolve model paths with CLI > env > settings > default layout order.

    Explicit CLI/function arguments always win for developer power-users.
    Server-side code should pass only registry/env-resolved values, never raw
    client filesystem paths.
    """
    app_data = app_data_dir if app_data_dir is not None else get_app_data_dir()
    settings_file = (
        settings_path
        if settings_path is not None
        else get_settings_path(app_data_dir=app_data, prefer_dev=True)
    )
    from_settings = _settings_model_paths(_read_settings(settings_file))

    sources: list[str] = []

    def pick(
        explicit: Optional[str],
        env_key: str,
        settings_key: str,
        default: Optional[Path],
        label: str,
    ) -> Optional[Path]:
        if explicit:
            sources.append(f"{label}:cli")
            return Path(explicit).expanduser()
        env_val = os.environ.get(env_key)
        if env_val and env_val.strip():
            sources.append(f"{label}:env")
            return Path(env_val.strip()).expanduser()
        settings_val = from_settings.get(settings_key)
        if settings_val:
            sources.append(f"{label}:settings")
            return Path(settings_val).expanduser()
        if use_defaults and default is not None:
            sources.append(f"{label}:default")
            return default
        sources.append(f"{label}:none")
        return None

    sam3 = pick(
        sam_checkpoint_path,
        ENV_SAM3_CHECKPOINT,
        "sam3_checkpoint",
        get_default_sam3_checkpoint(app_data) if use_defaults else None,
        "sam3",
    )
    bpe = pick(
        sam_bpe_path,
        ENV_SAM3_BPE,
        "sam3_bpe",
        None,  # package default handled by sam3 loader
        "bpe",
    )
    rmbg = pick(
        rmbg_model_path,
        ENV_RMBG_MODEL_PATH,
        "rmbg_model_path",
        get_default_rmbg_model_dir(app_data) if use_defaults else None,
        "rmbg",
    )

    # Collapse source tags into a short label (ignore unused "none" slots).
    unique = []
    for s in sources:
        tag = s.split(":", 1)[-1]
        if tag == "none":
            continue
        if tag not in unique:
            unique.append(tag)
    if len(unique) == 1:
        source = unique[0]
    elif not unique:
        source = "none"
    else:
        source = "mixed"

    return ModelPaths(
        sam3_checkpoint=sam3,
        sam3_bpe=bpe,
        rmbg_model_dir=rmbg,
        source=source,
    )


def export_path_env(paths: ModelPaths) -> dict[str, str]:
    """Build env var mapping for child processes (server → CLI)."""
    env: dict[str, str] = {}
    if paths.sam3_checkpoint is not None:
        env[ENV_SAM3_CHECKPOINT] = str(paths.sam3_checkpoint)
    if paths.sam3_bpe is not None:
        env[ENV_SAM3_BPE] = str(paths.sam3_bpe)
    if paths.rmbg_model_dir is not None:
        env[ENV_RMBG_MODEL_PATH] = str(paths.rmbg_model_dir)
    return env
