"""Pure helpers for local SAM3 checkpoint validation and load kwargs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Union

from figuresmith.models.errors import Sam3ModelInvalid, Sam3ModelMissing
from figuresmith.models.registry import ENV_SAM3_BPE, ENV_SAM3_CHECKPOINT

# Lazy-import offline helpers inside functions to avoid circular imports
# (security.offline -> models.errors -> models package -> sam3_loader).

PathLike = Union[str, Path]

# Remote backends rejected under strict offline / force-local.
REMOTE_SAM_BACKENDS = frozenset({"fal", "roboflow", "api"})
STRICT_OFFLINE_ENV = "FIGURESMITH_STRICT_OFFLINE"
FORCE_LOCAL_SAM_ENV = "FIGURESMITH_FORCE_LOCAL_SAM"


def resolve_checkpoint_path(
    sam_checkpoint_path: Optional[str] = None,
) -> Optional[Path]:
    """Resolve checkpoint from explicit arg or ``FIGURESMITH_SAM3_CHECKPOINT``."""
    if sam_checkpoint_path and str(sam_checkpoint_path).strip():
        return Path(str(sam_checkpoint_path).strip()).expanduser()
    env_val = os.environ.get(ENV_SAM3_CHECKPOINT)
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser()
    return None


def resolve_bpe_path(sam_bpe_path: Optional[str] = None) -> Optional[Path]:
    if sam_bpe_path and str(sam_bpe_path).strip():
        return Path(str(sam_bpe_path).strip()).expanduser()
    env_val = os.environ.get(ENV_SAM3_BPE)
    if env_val and env_val.strip():
        return Path(env_val.strip()).expanduser()
    return None


def validate_sam3_checkpoint(path: Optional[PathLike]) -> Path:
    """Ensure checkpoint path is set and points to an existing readable file.

    Raises:
        Sam3ModelMissing: path unset or file does not exist
        Sam3ModelInvalid: path exists but is not a readable regular file
    """
    if path is None or not str(path).strip():
        raise Sam3ModelMissing(
            detail=(
                "No SAM3 checkpoint configured. Set --sam_checkpoint_path, "
                f"{ENV_SAM3_CHECKPOINT}, or import weights under the app data models/ folder."
            )
        )
    p = Path(path).expanduser()
    if not p.exists():
        raise Sam3ModelMissing(detail=f"SAM3 checkpoint not found: {p}")
    if not p.is_file():
        raise Sam3ModelInvalid(detail=f"SAM3 checkpoint is not a file: {p}")
    try:
        if p.stat().st_size <= 0:
            raise Sam3ModelInvalid(detail=f"SAM3 checkpoint is empty: {p}")
    except OSError as exc:
        raise Sam3ModelInvalid(detail=f"Cannot stat SAM3 checkpoint {p}: {exc}") from exc
    # Touch-readability check without loading the full weight into memory.
    try:
        with open(p, "rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise Sam3ModelInvalid(detail=f"Cannot read SAM3 checkpoint {p}: {exc}") from exc
    return p.resolve()


def build_sam3_load_kwargs(
    *,
    device: str,
    checkpoint_path: PathLike,
    bpe_path: Optional[PathLike] = None,
) -> dict[str, Any]:
    """Return kwargs for ``build_sam3_image_model`` with local-only loading.

    Always sets ``load_from_HF=False`` and an explicit ``checkpoint_path``.
    """
    ckpt = validate_sam3_checkpoint(checkpoint_path)
    kwargs: dict[str, Any] = {
        "device": device,
        "checkpoint_path": str(ckpt),
        "load_from_HF": False,
    }
    if bpe_path is not None and str(bpe_path).strip():
        bpe = Path(bpe_path).expanduser()
        if bpe.exists():
            kwargs["bpe_path"] = str(bpe)
        else:
            # Explicit missing BPE is a soft warning path for callers; still pass
            # None rather than a broken path so sam3 can use package default.
            kwargs["bpe_path"] = None
    else:
        kwargs["bpe_path"] = None
    return kwargs


def must_force_local_sam(strict_offline: Optional[bool] = None) -> bool:
    """True when remote SAM backends must be rejected."""
    from figuresmith.security.offline import env_flag_true, is_strict_offline_enabled

    if is_strict_offline_enabled(strict_offline, default=False):
        return True
    if env_flag_true(FORCE_LOCAL_SAM_ENV, default=False):
        return True
    if env_flag_true(STRICT_OFFLINE_ENV, default=False):
        return True
    return False


def normalize_sam_backend(sam_backend: str) -> str:
    backend = (sam_backend or "local").strip().lower()
    if backend == "api":
        return "fal"
    return backend
