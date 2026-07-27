"""SAM3 checkpoint import: validate → stage → checksum → metadata → promote."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from figuresmith.models.checksums import sha256_file, write_checksum_file
from figuresmith.models.errors import (
    ModelImportError,
    ModelImportInvalidSource,
    ModelImportSizeError,
    Sam3ModelInvalid,
)
from figuresmith.models.manifest import require_pin_or_raise
from figuresmith.models.paths import get_app_data_dir, get_default_sam3_checkpoint
from figuresmith.models.sam3_loader import validate_sam3_checkpoint
from figuresmith.models.settings_io import update_model_settings
from figuresmith.models.staging import (
    atomic_promote,
    cleanup_dir,
    create_staging_dir,
    stream_copy_file,
)
from figuresmith.security.offline import env_flag_true

PathLike = Union[str, Path]

MODEL_ID = "sam3"
CHECKPOINT_NAME = "sam3.pt"
METADATA_NAME = "metadata.json"
ALLOWED_EXTENSIONS = {".pt", ".pth"}

# Defaults: >1 MiB and <20 GiB. Tests override via args or env.
DEFAULT_MIN_BYTES = 1_048_576
DEFAULT_MAX_BYTES = 20 * 1024 * 1024 * 1024
ENV_MIN_BYTES = "FIGURESMITH_SAM3_MIN_BYTES"
ENV_MAX_BYTES = "FIGURESMITH_SAM3_MAX_BYTES"
ENV_LOAD_PROBE = "FIGURESMITH_MODEL_LOAD_PROBE"


@dataclass
class Sam3ImportResult:
    success: bool
    destination: Path
    checkpoint: Path
    metadata: dict[str, Any]
    sha256: str
    official_verified: bool
    load_verified: str
    warnings: list[str] = field(default_factory=list)
    replaced_existing: bool = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip(), 10)
    except ValueError:
        return default


def resolve_size_limits(
    *,
    min_bytes: Optional[int] = None,
    max_bytes: Optional[int] = None,
) -> tuple[int, int]:
    lo = min_bytes if min_bytes is not None else _env_int(ENV_MIN_BYTES, DEFAULT_MIN_BYTES)
    hi = max_bytes if max_bytes is not None else _env_int(ENV_MAX_BYTES, DEFAULT_MAX_BYTES)
    return lo, hi


def validate_sam3_source(
    source_path: PathLike,
    *,
    min_bytes: Optional[int] = None,
    max_bytes: Optional[int] = None,
    require_absolute: bool = True,
) -> Path:
    """Validate user-selected SAM3 source path (extension, existence, size)."""
    if source_path is None or not str(source_path).strip():
        raise ModelImportInvalidSource(detail="empty source_path")

    raw = Path(str(source_path).strip())
    if require_absolute and not raw.is_absolute():
        raise ModelImportInvalidSource(
            detail=f"source_path must be an absolute local path, got: {raw}"
        )
    if not raw.exists():
        raise ModelImportInvalidSource(detail=f"source file does not exist: {raw}")
    if not raw.is_file():
        raise ModelImportInvalidSource(detail=f"source_path is not a file: {raw}")

    suffix = raw.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ModelImportInvalidSource(
            detail=(
                f"unsupported extension {suffix!r}; expected one of "
                f"{sorted(ALLOWED_EXTENSIONS)}"
            )
        )

    try:
        size = raw.stat().st_size
    except OSError as exc:
        raise ModelImportInvalidSource(detail=f"cannot stat source: {exc}") from exc

    lo, hi = resolve_size_limits(min_bytes=min_bytes, max_bytes=max_bytes)
    if size < lo:
        raise ModelImportSizeError(
            detail=f"SAM3 checkpoint too small ({size} bytes < min {lo})"
        )
    if size > hi:
        raise ModelImportSizeError(
            detail=f"SAM3 checkpoint too large ({size} bytes > max {hi})"
        )
    return raw.resolve()


def _optional_load_probe(checkpoint: Path) -> str:
    """Optional torch load probe; skipped without CUDA or when disabled."""
    if not env_flag_true(ENV_LOAD_PROBE, default=False):
        return "skipped"
    try:
        import torch  # type: ignore
    except Exception:
        return "skipped"
    if not getattr(torch, "cuda", None) or not torch.cuda.is_available():
        return "skipped"
    try:
        # Map location CPU still exercises file format without full GPU residency.
        obj = torch.load(str(checkpoint), map_location="cpu", weights_only=True)  # type: ignore[call-arg]
        del obj
        return "true"
    except TypeError:
        # Older torch without weights_only=
        try:
            obj = torch.load(str(checkpoint), map_location="cpu")
            del obj
            return "true"
        except Exception as exc:
            raise Sam3ModelInvalid(detail=f"load probe failed: {exc}") from exc
    except Exception as exc:
        raise Sam3ModelInvalid(detail=f"load probe failed: {exc}") from exc


def _write_metadata(staging: Path, metadata: dict[str, Any]) -> Path:
    import json

    path = staging / METADATA_NAME
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def import_sam3_checkpoint(
    source_path: PathLike,
    *,
    app_data_dir: Optional[Path] = None,
    min_bytes: Optional[int] = None,
    max_bytes: Optional[int] = None,
    require_absolute: bool = True,
    update_settings: bool = True,
    allow_unpinned: Optional[bool] = None,
    run_load_probe: Optional[bool] = None,
) -> Sam3ImportResult:
    """Import a local SAM3 ``.pt`` into app data with staging + atomic promote.

    Failure never overwrites an already-verified destination: staging is cleaned
    and any mid-promote trash restore is handled by :func:`atomic_promote`.
    """
    app_data = app_data_dir if app_data_dir is not None else get_app_data_dir()
    source = validate_sam3_source(
        source_path,
        min_bytes=min_bytes,
        max_bytes=max_bytes,
        require_absolute=require_absolute,
    )

    digest = sha256_file(source)
    pin = require_pin_or_raise(
        MODEL_ID,
        digest,
        allow_unpinned=allow_unpinned,
    )

    staging: Optional[Path] = None
    warnings = [w for w in [pin.warning] if w]

    try:
        staging = create_staging_dir(MODEL_ID, app_data_dir=app_data)
        staged_ckpt = staging / CHECKPOINT_NAME
        stream_copy_file(source, staged_ckpt)

        # File-level validation (phase 2 helper) on the staged copy.
        validate_sam3_checkpoint(staged_ckpt)

        # Re-hash staged copy to ensure copy integrity.
        staged_digest = sha256_file(staged_ckpt)
        if staged_digest != digest:
            raise ModelImportError(
                detail=(
                    f"staged checksum mismatch: source={digest} staged={staged_digest}"
                )
            )

        load_verified = "skipped"
        if run_load_probe is True or (
            run_load_probe is None and env_flag_true(ENV_LOAD_PROBE, default=False)
        ):
            load_verified = _optional_load_probe(staged_ckpt)
        else:
            load_verified = "skipped"

        metadata: dict[str, Any] = {
            "id": MODEL_ID,
            "display_name": "SAM 3",
            "checkpoint": CHECKPOINT_NAME,
            "sha256": staged_digest,
            "imported_at": _utc_now_iso(),
            "verified": True,
            "load_verified": load_verified,
            "source": "user_import",
            "official_verified": pin.official_verified,
            "source_path": str(source),
        }
        _write_metadata(staging, metadata)
        write_checksum_file(staging, staged_digest, labeled_name=CHECKPOINT_NAME)

        destination_dir = get_default_sam3_checkpoint(app_data).parent
        promote = atomic_promote(
            staging,
            destination_dir,
            app_data_dir=app_data,
            model_id=MODEL_ID,
        )
        staging = None  # ownership transferred

        final_ckpt = Path(promote.destination) / CHECKPOINT_NAME
        if update_settings:
            update_model_settings(
                sam3_checkpoint=final_ckpt,
                app_data_dir=app_data,
            )

        return Sam3ImportResult(
            success=True,
            destination=Path(promote.destination),
            checkpoint=final_ckpt,
            metadata=metadata,
            sha256=staged_digest,
            official_verified=pin.official_verified,
            load_verified=load_verified,
            warnings=warnings,
            replaced_existing=promote.replaced_existing,
        )
    except Exception:
        cleanup_dir(staging)
        raise


def verify_installed_sam3(
    *,
    app_data_dir: Optional[Path] = None,
    checkpoint: Optional[PathLike] = None,
) -> dict[str, Any]:
    """Re-validate an installed SAM3 checkpoint and refresh checksum if present."""
    app_data = app_data_dir if app_data_dir is not None else get_app_data_dir()
    ckpt = (
        Path(checkpoint)
        if checkpoint is not None
        else get_default_sam3_checkpoint(app_data)
    )
    validated = validate_sam3_checkpoint(ckpt)
    digest = sha256_file(validated)
    meta_path = validated.parent / METADATA_NAME
    metadata: dict[str, Any] = {}
    if meta_path.is_file():
        import json

        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
    pin = require_pin_or_raise(MODEL_ID, digest, allow_unpinned=True)
    return {
        "id": MODEL_ID,
        "installed": True,
        "path": str(validated),
        "sha256": digest,
        "verified": True,
        "official_verified": pin.official_verified and pin.pin_present and (
            (metadata.get("sha256") or digest) == digest
        ),
        "metadata": metadata,
        "load_verified": metadata.get("load_verified", "skipped"),
    }
