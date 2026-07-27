"""Pure helpers for local RMBG-2.0 directory validation and load kwargs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from figuresmith.models.errors import RmbgModelInvalid, RmbgModelMissing
from figuresmith.models.registry import ENV_RMBG_MODEL_PATH

# NOTE: do not import figuresmith.security at module top-level — offline.py
# imports model errors and would create a circular import through models/__init__.

PathLike = Union[str, Path]

# Minimum files expected in a local Transformers snapshot of RMBG-2.0.
REQUIRED_RMBG_FILES: tuple[str, ...] = (
    "config.json",
    "preprocessor_config.json",
)

# At least one of these weight filenames must exist.
WEIGHT_CANDIDATES: tuple[str, ...] = (
    "model.safetensors",
    "pytorch_model.bin",
    "model.safetensors.index.json",
)


def resolve_rmbg_model_path(rmbg_model_path: Optional[str] = None) -> Optional[Path]:
    if rmbg_model_path and str(rmbg_model_path).strip():
        return Path(str(rmbg_model_path).strip()).expanduser()
    env_val = os.environ.get(ENV_RMBG_MODEL_PATH)
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser()
    return None


def _has_weight_file(directory: Path) -> bool:
    for name in WEIGHT_CANDIDATES:
        if (directory / name).is_file():
            return True
    # Some exports nest weights under subdirs; accept any *.safetensors at top level.
    if any(directory.glob("*.safetensors")):
        return True
    if any(directory.glob("*.bin")):
        return True
    return False


def validate_rmbg_model_dir(
    path: Optional[PathLike],
    *,
    required_files: Sequence[str] = REQUIRED_RMBG_FILES,
) -> Path:
    """Validate a local RMBG model directory.

    Raises:
        RmbgModelMissing: path unset or directory does not exist
        RmbgModelInvalid: directory exists but required files are missing
    """
    if path is None or not str(path).strip():
        raise RmbgModelMissing(
            detail=(
                "No local RMBG-2.0 directory configured. Set --rmbg_model_path, "
                f"{ENV_RMBG_MODEL_PATH}, or import the model pack under app data models/."
            )
        )
    p = Path(path).expanduser()
    if not p.exists():
        raise RmbgModelMissing(detail=f"RMBG model directory not found: {p}")
    if not p.is_dir():
        raise RmbgModelInvalid(detail=f"RMBG model path is not a directory: {p}")

    missing = [name for name in required_files if not (p / name).is_file()]
    if missing:
        raise RmbgModelInvalid(
            detail=f"RMBG model directory {p} missing required files: {', '.join(missing)}"
        )
    if not _has_weight_file(p):
        raise RmbgModelInvalid(
            detail=(
                f"RMBG model directory {p} has no weight file "
                f"(expected one of: {', '.join(WEIGHT_CANDIDATES)})"
            )
        )
    return p.resolve()


def build_rmbg_from_pretrained_kwargs(
    model_dir: PathLike,
    *,
    trust_remote_code: bool = True,
) -> dict[str, Any]:
    """Return kwargs for ``AutoModelForImageSegmentation.from_pretrained``.

    Always sets ``local_files_only=True`` so Transformers will not hit the hub.
    """
    validated = validate_rmbg_model_dir(model_dir)
    return {
        "pretrained_model_name_or_path": str(validated),
        "trust_remote_code": trust_remote_code,
        "local_files_only": True,
    }


def should_allow_hf_rmbg_fallback(strict_offline: Optional[bool] = None) -> bool:
    """HF repo download fallback is forbidden under strict offline."""
    from figuresmith.security.offline import is_strict_offline_enabled

    if is_strict_offline_enabled(strict_offline, default=False):
        return False
    # FigureSmith desktop default: also forbid when FORCE path is set via env.
    if os.environ.get("FIGURESMITH_ALLOW_HF_RMBG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    # Default for FigureSmith integrations: no HF fallback.
    # Vendor CLI without strict flag may still use legacy path when figuresmith
    # helpers are not enforcing; callers decide.
    return False
