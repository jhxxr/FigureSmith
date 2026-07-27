"""RMBG-2.0 pack import: ZIP (Zip Slip safe) or folder → stage → pin → promote."""

from __future__ import annotations

import os
import shutil
import stat
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from figuresmith.models.checksums import sha256_file, write_checksum_file
from figuresmith.models.errors import (
    ModelImportError,
    ModelImportInvalidSource,
    ModelImportZipSlip,
    RmbgModelInvalid,
)
from figuresmith.models.manifest import get_required_files, require_pin_or_raise
from figuresmith.models.paths import get_app_data_dir, get_default_rmbg_model_dir
from figuresmith.models.rmbg_loader import WEIGHT_CANDIDATES, validate_rmbg_model_dir
from figuresmith.models.settings_io import update_model_settings
from figuresmith.models.staging import (
    atomic_promote,
    cleanup_dir,
    create_staging_dir,
    stream_copy_file,
)
from figuresmith.security.offline import env_flag_true

PathLike = Union[str, Path]

MODEL_ID = "rmbg-2.0"
METADATA_NAME = "metadata.json"
DEFAULT_MAX_FILES = 200
DEFAULT_MAX_UNCOMPRESSED = 8 * 1024 * 1024 * 1024  # 8 GiB
ENV_MAX_FILES = "FIGURESMITH_RMBG_ZIP_MAX_FILES"
ENV_MAX_UNCOMPRESSED = "FIGURESMITH_RMBG_ZIP_MAX_UNCOMPRESSED"
ENV_LOAD_PROBE = "FIGURESMITH_MODEL_LOAD_PROBE"

# Manifest-aligned required names (phase 2 loader also accepts alternate weights).
DEFAULT_REQUIRED_FILES: tuple[str, ...] = (
    "config.json",
    "preprocessor_config.json",
    "model.safetensors",
)

# Optional BiRefNet / trust_remote_code python modules often shipped with the pack.
OPTIONAL_CODE_HINTS: tuple[str, ...] = (
    "birefnet.py",
    "BiRefNet.py",
    "modeling_birefnet.py",
    "configuration_birefnet.py",
)

TRUST_REMOTE_CODE_WARNING = (
    "RMBG-2.0 may execute local Python model code via trust_remote_code. "
    "Only import packs from trusted sources. "
    "源码许可 ≠ 权重许可；请仅从可信来源导入 RMBG 模型包。"
)


@dataclass
class RmbgImportResult:
    success: bool
    destination: Path
    metadata: dict[str, Any]
    sha256: str
    official_verified: bool
    load_verified: str
    kind: str
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


def detect_rmbg_kind(source_path: Path) -> str:
    if source_path.is_dir():
        return "dir"
    if source_path.is_file() and source_path.suffix.lower() in {".zip"}:
        return "zip"
    raise ModelImportInvalidSource(
        detail=f"RMBG source must be a .zip file or a directory, got: {source_path}"
    )


def validate_rmbg_source(
    source_path: PathLike,
    *,
    kind: Optional[str] = None,
    require_absolute: bool = True,
) -> tuple[Path, str]:
    if source_path is None or not str(source_path).strip():
        raise ModelImportInvalidSource(detail="empty source_path")
    raw = Path(str(source_path).strip())
    if require_absolute and not raw.is_absolute():
        raise ModelImportInvalidSource(
            detail=f"source_path must be an absolute local path, got: {raw}"
        )
    if not raw.exists():
        raise ModelImportInvalidSource(detail=f"source path does not exist: {raw}")

    resolved_kind = (kind or "auto").strip().lower()
    if resolved_kind in {"", "auto"}:
        resolved_kind = detect_rmbg_kind(raw)
    elif resolved_kind not in {"zip", "dir"}:
        raise ModelImportInvalidSource(detail=f"invalid kind={kind!r}; expected zip|dir|auto")

    if resolved_kind == "zip":
        if not raw.is_file():
            raise ModelImportInvalidSource(detail=f"kind=zip but path is not a file: {raw}")
        if raw.suffix.lower() != ".zip":
            raise ModelImportInvalidSource(detail=f"kind=zip expects .zip extension: {raw}")
    else:
        if not raw.is_dir():
            raise ModelImportInvalidSource(detail=f"kind=dir but path is not a directory: {raw}")

    return raw.resolve(), resolved_kind


def _is_dangerous_zip_member(name: str) -> Optional[str]:
    """Return a reason string if the ZIP member name is unsafe, else None."""
    if not name or not str(name).strip():
        return "empty member name"
    if "\x00" in name:
        return f"NUL byte in member path: {name!r}"
    # Normalize separators but do not resolve against filesystem yet.
    norm = name.replace("\\", "/")
    if norm.startswith("/") or norm.startswith("\\"):
        return f"absolute member path: {name}"
    # Windows drive-absolute: C:/..., //server/share
    if len(norm) >= 2 and norm[1] == ":":
        return f"absolute member path (drive): {name}"
    if norm.startswith("//") or norm.startswith("\\\\"):
        return f"UNC/absolute member path: {name}"
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return f"parent traversal in member path: {name}"
    return None


def _member_is_symlink(info: zipfile.ZipInfo) -> bool:
    # External attributes: upper 16 bits are Unix mode when created on Unix.
    mode = (info.external_attr >> 16) & 0xFFFF
    if mode and stat.S_ISLNK(mode):
        return True
    # Some zips mark symlinks via create_system + extra fields; be conservative
    # if the header bit indicates a symlink-like type.
    if info.create_system == 3 and mode == 0 and info.file_size == 0:
        # Not reliable enough alone; only flag when external attr says link.
        return False
    return False


def safe_extract_zip(
    zip_path: PathLike,
    destination: PathLike,
    *,
    max_files: Optional[int] = None,
    max_uncompressed_bytes: Optional[int] = None,
    reject_symlinks: bool = True,
) -> list[str]:
    """Extract a ZIP under ``destination`` with Zip Slip and bomb guards.

    Returns the list of extracted relative member paths.
    """
    zpath = Path(zip_path)
    dest_root = Path(destination).resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    max_n = (
        max_files
        if max_files is not None
        else _env_int(ENV_MAX_FILES, DEFAULT_MAX_FILES)
    )
    max_bytes = (
        max_uncompressed_bytes
        if max_uncompressed_bytes is not None
        else _env_int(ENV_MAX_UNCOMPRESSED, DEFAULT_MAX_UNCOMPRESSED)
    )

    extracted: list[str] = []
    total_uncompressed = 0

    try:
        zf = zipfile.ZipFile(zpath, "r")
    except zipfile.BadZipFile as exc:
        raise ModelImportInvalidSource(detail=f"invalid zip file: {zpath}: {exc}") from exc

    with zf:
        infos = zf.infolist()
        # Count file members (not dirs) toward max_files.
        file_members = [i for i in infos if not i.is_dir()]
        if len(file_members) > max_n:
            raise ModelImportZipSlip(
                detail=f"zip contains too many files ({len(file_members)} > max {max_n})"
            )

        # Early reject on declared sizes (fast path) before writing anything.
        declared_total = sum(max(0, int(i.file_size)) for i in file_members)
        if declared_total > max_bytes:
            raise ModelImportZipSlip(
                detail=(
                    f"zip uncompressed size exceeds limit "
                    f"({declared_total} > {max_bytes})"
                )
            )

        for info in infos:
            reason = _is_dangerous_zip_member(info.filename)
            if reason:
                raise ModelImportZipSlip(detail=reason)

            if reject_symlinks and _member_is_symlink(info):
                raise ModelImportZipSlip(
                    detail=f"symlink members are not allowed: {info.filename}"
                )

            # Build target path and ensure it stays under dest_root.
            rel = info.filename.replace("\\", "/")
            while rel.startswith("./"):
                rel = rel[2:]
            if not rel or rel in {".", "./"}:
                continue

            target = (dest_root / rel).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise ModelImportZipSlip(
                    detail=f"zip member escapes destination: {info.filename}"
                ) from exc

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            # Stream extract and count *actual* decompressed bytes so a lying
            # local file header cannot bypass the uncompressed size cap.
            try:
                with zf.open(info, "r") as src, open(target, "wb") as out:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        total_uncompressed += len(chunk)
                        if total_uncompressed > max_bytes:
                            raise ModelImportZipSlip(
                                detail=(
                                    f"zip uncompressed size exceeds limit "
                                    f"({total_uncompressed} > {max_bytes})"
                                )
                            )
                        out.write(chunk)
            except Exception:
                try:
                    target.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

            extracted.append(rel)

    return extracted


def _copy_tree_safe(src_dir: Path, dest_dir: Path) -> None:
    """Copy a directory tree, refusing to follow symlinks out of the source."""
    src_root = src_dir.resolve()
    dest_root = dest_dir.resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    for root, dirnames, filenames in os.walk(src_root, followlinks=False):
        root_path = Path(root)
        # Prune symlinked directories.
        live_dirs: list[str] = []
        for d in list(dirnames):
            child = root_path / d
            if child.is_symlink():
                raise ModelImportZipSlip(
                    detail=f"refusing to follow symlink directory during import: {child}"
                )
            live_dirs.append(d)
        dirnames[:] = live_dirs

        rel_root = root_path.relative_to(src_root)
        target_root = dest_root / rel_root
        target_root.mkdir(parents=True, exist_ok=True)

        for name in filenames:
            src_file = root_path / name
            if src_file.is_symlink():
                raise ModelImportZipSlip(
                    detail=f"refusing to copy symlink file during import: {src_file}"
                )
            if not src_file.is_file():
                continue
            dest_file = target_root / name
            stream_copy_file(src_file, dest_file)


def _find_pack_root(staging: Path) -> Path:
    """If the archive extracted a single top-level folder, use that as pack root."""
    entries = [p for p in staging.iterdir() if p.name not in {METADATA_NAME, "checksum.sha256"}]
    if len(entries) == 1 and entries[0].is_dir():
        # Prefer nested root when it looks like a transformers snapshot.
        candidate = entries[0]
        if (candidate / "config.json").is_file() or (candidate / "model.safetensors").is_file():
            return candidate
    return staging


def _flatten_pack_into_staging(staging: Path) -> Path:
    """Ensure required files live directly under staging (promote target)."""
    pack_root = _find_pack_root(staging)
    if pack_root == staging:
        return staging

    # Move nested content up into staging.
    for child in list(pack_root.iterdir()):
        target = staging / child.name
        if target.exists():
            if target.is_dir():
                cleanup_dir(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))
    # Remove emptied nest.
    cleanup_dir(pack_root)
    return staging


def _primary_weight_path(model_dir: Path) -> Path:
    for name in WEIGHT_CANDIDATES:
        candidate = model_dir / name
        if candidate.is_file():
            return candidate
    safes = sorted(model_dir.glob("*.safetensors"))
    if safes:
        return safes[0]
    bins = sorted(model_dir.glob("*.bin"))
    if bins:
        return bins[0]
    raise RmbgModelInvalid(detail=f"no weight file found under {model_dir}")


def _ensure_required_files(
    model_dir: Path,
    *,
    required: Optional[Sequence[str]] = None,
) -> None:
    req = list(required) if required is not None else list(
        get_required_files(MODEL_ID) or DEFAULT_REQUIRED_FILES
    )
    # Phase 2 loader allows alternate weight names; if manifest pins model.safetensors
    # but only pytorch_model.bin exists, still accept via validate_rmbg_model_dir.
    missing_config = [
        name
        for name in req
        if name not in WEIGHT_CANDIDATES and not (model_dir / name).is_file()
    ]
    if missing_config:
        raise RmbgModelInvalid(
            detail=f"RMBG pack missing required files: {', '.join(missing_config)}"
        )
    # Weight presence
    has_listed_weight = any((model_dir / name).is_file() for name in req if name in WEIGHT_CANDIDATES)
    if not has_listed_weight:
        # Fall back to phase2 weight discovery.
        validate_rmbg_model_dir(model_dir)
    else:
        validate_rmbg_model_dir(model_dir)


def _optional_load_probe(model_dir: Path) -> str:
    if not env_flag_true(ENV_LOAD_PROBE, default=False):
        return "skipped"
    try:
        import torch  # type: ignore
    except Exception:
        return "skipped"
    if not getattr(torch, "cuda", None) or not torch.cuda.is_available():
        return "skipped"
    # Real from_pretrained is heavy; mark skipped unless explicitly expanded later.
    return "skipped"


def _write_metadata(staging: Path, metadata: dict[str, Any]) -> Path:
    import json

    path = staging / METADATA_NAME
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def import_rmbg_pack(
    source_path: PathLike,
    *,
    kind: str = "auto",
    app_data_dir: Optional[Path] = None,
    require_absolute: bool = True,
    update_settings: bool = True,
    allow_unpinned: Optional[bool] = None,
    max_files: Optional[int] = None,
    max_uncompressed_bytes: Optional[int] = None,
    required_files: Optional[Sequence[str]] = None,
) -> RmbgImportResult:
    """Import RMBG-2.0 from a ZIP or folder into app data with rollback safety."""
    app_data = app_data_dir if app_data_dir is not None else get_app_data_dir()
    source, resolved_kind = validate_rmbg_source(
        source_path, kind=kind, require_absolute=require_absolute
    )

    staging: Optional[Path] = None
    warnings = [TRUST_REMOTE_CODE_WARNING]

    try:
        staging = create_staging_dir(MODEL_ID, app_data_dir=app_data)

        if resolved_kind == "zip":
            safe_extract_zip(
                source,
                staging,
                max_files=max_files,
                max_uncompressed_bytes=max_uncompressed_bytes,
            )
        else:
            _copy_tree_safe(source, staging)

        _flatten_pack_into_staging(staging)
        _ensure_required_files(staging, required=required_files)

        weight = _primary_weight_path(staging)
        digest = sha256_file(weight)
        pin = require_pin_or_raise(
            MODEL_ID,
            digest,
            allow_unpinned=allow_unpinned,
        )
        if pin.warning:
            warnings.append(pin.warning)

        load_verified = _optional_load_probe(staging)
        metadata: dict[str, Any] = {
            "id": MODEL_ID,
            "display_name": "BRIA RMBG 2.0",
            "sha256": digest,
            "weight_file": weight.name,
            "imported_at": _utc_now_iso(),
            "verified": True,
            "load_verified": load_verified,
            "source": "user_import",
            "kind": resolved_kind,
            "official_verified": pin.official_verified,
            "source_path": str(source),
            "trust_remote_code_warning": TRUST_REMOTE_CODE_WARNING,
        }
        _write_metadata(staging, metadata)
        write_checksum_file(staging, digest, labeled_name=weight.name)

        destination = get_default_rmbg_model_dir(app_data)
        promote = atomic_promote(
            staging,
            destination,
            app_data_dir=app_data,
            model_id=MODEL_ID,
        )
        staging = None

        if update_settings:
            update_model_settings(
                rmbg_model_path=promote.destination,
                app_data_dir=app_data,
            )

        return RmbgImportResult(
            success=True,
            destination=Path(promote.destination),
            metadata=metadata,
            sha256=digest,
            official_verified=pin.official_verified,
            load_verified=load_verified,
            kind=resolved_kind,
            warnings=warnings,
            replaced_existing=promote.replaced_existing,
        )
    except Exception:
        cleanup_dir(staging)
        raise


def verify_installed_rmbg(
    *,
    app_data_dir: Optional[Path] = None,
    model_dir: Optional[PathLike] = None,
) -> dict[str, Any]:
    app_data = app_data_dir if app_data_dir is not None else get_app_data_dir()
    directory = (
        Path(model_dir) if model_dir is not None else get_default_rmbg_model_dir(app_data)
    )
    validated = validate_rmbg_model_dir(directory)
    weight = _primary_weight_path(validated)
    digest = sha256_file(weight)
    meta_path = validated / METADATA_NAME
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
        "official_verified": bool(pin.official_verified and pin.pin_present),
        "metadata": metadata,
        "load_verified": metadata.get("load_verified", "skipped"),
        "trust_remote_code_warning": TRUST_REMOTE_CODE_WARNING,
    }
