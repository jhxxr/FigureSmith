"""Staging directories, trash, and atomic promote for model imports."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from figuresmith.models.errors import ModelImportError
from figuresmith.models.paths import get_app_data_dir, get_models_root

PathLike = Union[str, Path]

STAGING_DIRNAME = ".staging"
TRASH_DIRNAME = ".trash"
DEFAULT_TRASH_KEEP = 3


@dataclass
class PromoteResult:
    destination: Path
    trash_path: Optional[Path]
    replaced_existing: bool


def get_staging_root(app_data_dir: Optional[Path] = None) -> Path:
    return get_models_root(app_data_dir) / STAGING_DIRNAME


def get_trash_root(app_data_dir: Optional[Path] = None) -> Path:
    return get_models_root(app_data_dir) / TRASH_DIRNAME


def create_staging_dir(
    model_id: str,
    *,
    app_data_dir: Optional[Path] = None,
) -> Path:
    """Create ``models/.staging/<id>-<uuid>/`` and return it."""
    safe_id = "".join(c if c.isalnum() or c in "-_." else "-" for c in model_id) or "model"
    staging_root = get_staging_root(app_data_dir)
    staging_root.mkdir(parents=True, exist_ok=True)
    path = staging_root / f"{safe_id}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()


def cleanup_dir(path: Optional[PathLike], *, missing_ok: bool = True) -> None:
    """Remove a directory tree (used for failed staging cleanup)."""
    if path is None:
        return
    p = Path(path)
    if not p.exists():
        if missing_ok:
            return
        raise FileNotFoundError(str(p))
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=False)
    else:
        p.unlink(missing_ok=True)


def _move_path(src: Path, dst: Path) -> None:
    """Move ``src`` to ``dst`` with limited Windows lock retries."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Optional[BaseException] = None
    for attempt in range(5):
        try:
            if dst.exists():
                # Should not happen for promote targets we manage; be explicit.
                raise ModelImportError(
                    detail=f"destination already exists during move: {dst}"
                )
            shutil.move(str(src), str(dst))
            return
        except (PermissionError, OSError) as exc:
            last_exc = exc
            time.sleep(0.05 * (attempt + 1))
    raise ModelImportError(
        detail=f"failed to move {src} → {dst}: {last_exc}"
    ) from last_exc


def atomic_promote(
    staging_dir: PathLike,
    destination: PathLike,
    *,
    app_data_dir: Optional[Path] = None,
    model_id: str = "model",
    keep_trash: int = DEFAULT_TRASH_KEEP,
) -> PromoteResult:
    """Atomically promote a validated staging directory to the final model path.

    Steps:
      1. If destination exists → move to ``models/.trash/<id>-<ts>/``
      2. Move staging → destination
      3. On failure after step 1 → restore trash back to destination
      4. On success → optionally prune old trash entries
    """
    staging = Path(staging_dir).resolve()
    dest = Path(destination)
    if not staging.is_dir():
        raise ModelImportError(detail=f"staging directory missing: {staging}")

    # Ensure parent of destination exists (e.g. models/).
    dest.parent.mkdir(parents=True, exist_ok=True)

    trash_path: Optional[Path] = None
    replaced = False
    dest_existed = dest.exists()

    try:
        if dest_existed:
            trash_root = get_trash_root(app_data_dir)
            trash_root.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%dT%H%M%S")
            trash_path = trash_root / f"{model_id}-{ts}-{uuid.uuid4().hex[:8]}"
            _move_path(dest, trash_path)
            replaced = True

        _move_path(staging, dest)
    except Exception:
        # Best-effort restore of previous model.
        if trash_path is not None and trash_path.exists() and not dest.exists():
            try:
                _move_path(trash_path, dest)
                trash_path = None
            except Exception:
                pass
        # Staging may still exist if move failed early — leave caller to clean,
        # but try if dest was never claimed.
        raise

    if keep_trash >= 0:
        try:
            prune_trash(model_id=model_id, app_data_dir=app_data_dir, keep=keep_trash)
        except OSError:
            pass

    return PromoteResult(
        destination=dest.resolve() if dest.exists() else dest,
        trash_path=trash_path.resolve() if trash_path and trash_path.exists() else trash_path,
        replaced_existing=replaced,
    )


def prune_trash(
    *,
    model_id: Optional[str] = None,
    app_data_dir: Optional[Path] = None,
    keep: int = DEFAULT_TRASH_KEEP,
) -> int:
    """Delete older trash entries, keeping the newest ``keep`` per model prefix.

    Returns the number of removed entries.
    """
    trash_root = get_trash_root(app_data_dir)
    if not trash_root.is_dir():
        return 0
    entries = [p for p in trash_root.iterdir() if p.is_dir()]
    if model_id:
        prefix = f"{model_id}-"
        entries = [p for p in entries if p.name.startswith(prefix)]
    entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for stale in entries[max(0, keep) :]:
        cleanup_dir(stale)
        removed += 1
    return removed


def same_volume(a: PathLike, b: PathLike) -> bool:
    """Best-effort check that two paths share a drive/volume (copy perf hint)."""
    pa = Path(a).resolve()
    pb = Path(b).resolve()
    if os.name == "nt":
        return pa.drive.upper() == pb.drive.upper() and bool(pa.drive)
    try:
        return os.stat(pa).st_dev == os.stat(pb).st_dev
    except OSError:
        return False


def stream_copy_file(src: PathLike, dst: PathLike, *, chunk_size: int = 1024 * 1024) -> int:
    """Copy a (possibly multi-GB) file in chunks. Returns bytes written."""
    source = Path(src)
    target = Path(dst)
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(source, "rb") as rin, open(target, "wb") as rout:
        while True:
            chunk = rin.read(chunk_size)
            if not chunk:
                break
            rout.write(chunk)
            written += len(chunk)
    try:
        shutil.copystat(source, target, follow_symlinks=True)
    except OSError:
        pass
    return written
