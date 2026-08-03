"""App data directories and safe path joins for local model packs."""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from figuresmith.models.errors import DataDirNotWritable, PathTraversalRejected

PathLike = Union[str, Path]

# Relative default layout under the app data / models root.
DEFAULT_SAM3_REL = Path("models") / "sam3" / "sam3.pt"
DEFAULT_RMBG_REL = Path("models") / "rmbg-2.0"
DEFAULT_SETTINGS_NAME = "settings.json"
DATA_DIR_NAME = "data"
DEV_MODE_ENV = "FIGURESMITH_DEV_MODE"


def _find_repo_root() -> Optional[Path]:
    """Locate monorepo root (vendor/autofigure_edit + apps/backend)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "vendor" / "autofigure_edit").is_dir() and (
            parent / "apps" / "backend"
        ).is_dir():
            return parent
    return None


def _ensure_writable_dir(path: Path) -> bool:
    """Create ``path`` and verify write, flush, atomic replace, and delete."""
    first: Optional[Path] = None
    second: Optional[Path] = None
    try:
        path.mkdir(parents=True, exist_ok=True)
        first = path / f".fs_probe_{uuid.uuid4().hex}.tmp"
        second = path / f".fs_probe_{uuid.uuid4().hex}.tmp"
        with first.open("wb") as handle:
            handle.write(b"figuresmith-writable-probe\n")
            handle.flush()
            os.fsync(handle.fileno())
        second.touch(exist_ok=False)
        os.replace(first, second)
        second.unlink()
        return True
    except OSError:
        return False
    finally:
        for probe in (first, second):
            if probe is not None:
                try:
                    probe.unlink(missing_ok=True)
                except OSError:
                    pass


def _localappdata_fallback() -> Path:
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "FigureSmith"
        return Path.home() / "AppData" / "Local" / "FigureSmith"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FigureSmith"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "figuresmith"
    return Path.home() / ".local" / "share" / "figuresmith"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _data_dir_error(path: Path) -> DataDirNotWritable:
    return DataDirNotWritable(detail=f"write probe failed for application data root: {path}")


def get_app_data_dir(*, development: Optional[bool] = None) -> Path:
    """Return the FigureSmith application data directory (models, settings, …).

    Resolution order (first writable wins):

    1. ``FIGURESMITH_DATA_DIR`` — explicit user/admin override
    2. ``FIGURESMITH_INSTALL_ROOT/data`` — installer root
    3. ``<repo_root>/data`` — only when explicit development mode is enabled
    4. ``%LOCALAPPDATA%\\FigureSmith`` (or macOS/Linux equivalent) — last resort
       when the install directory is not writable (e.g. Program Files)

    This prefers “next to the app” so large model imports stay on the install
    drive instead of always filling the system C: user profile.
    """
    override = os.environ.get("FIGURESMITH_DATA_DIR")
    if override and override.strip():
        path = Path(override).expanduser().resolve()
        if not _ensure_writable_dir(path):
            raise _data_dir_error(path)
        return path

    candidates: list[Path] = []

    install_root = os.environ.get("FIGURESMITH_INSTALL_ROOT")
    if install_root and install_root.strip():
        candidates.append(Path(install_root).expanduser() / DATA_DIR_NAME)

    dev_enabled = _env_flag(DEV_MODE_ENV, default=False) if development is None else development
    if dev_enabled:
        repo = _find_repo_root()
        if repo is not None:
            candidates.append(repo / DATA_DIR_NAME)

    for cand in candidates:
        if _ensure_writable_dir(cand):
            return cand.resolve()

    fallback = _localappdata_fallback()
    if _ensure_writable_dir(fallback):
        return fallback.resolve()
    raise _data_dir_error(fallback)


@dataclass(frozen=True)
class AppPaths:
    """Canonical mutable directories derived from one verified data root."""

    root: Path
    settings: Path
    models: Path
    jobs: Path
    uploads: Path
    outputs: Path
    temp: Path
    logs: Path
    svg_cache: Path


def resolve_app_paths(
    *,
    app_data_dir: Optional[Path] = None,
    development: Optional[bool] = None,
) -> AppPaths:
    """Resolve and eagerly probe the complete application data layout."""
    root = (
        Path(app_data_dir).expanduser().resolve()
        if app_data_dir is not None
        else get_app_data_dir(development=development)
    )
    if not _ensure_writable_dir(root):
        raise _data_dir_error(root)

    paths = AppPaths(
        root=root,
        settings=root / DEFAULT_SETTINGS_NAME,
        models=root / "models",
        jobs=root / "jobs",
        uploads=root / "uploads",
        outputs=root / "outputs",
        temp=root / "temp",
        logs=root / "logs",
        svg_cache=root / "cache" / "svg-v1",
    )
    for directory in (
        paths.models,
        paths.jobs,
        paths.uploads,
        paths.outputs,
        paths.temp,
        paths.logs,
        paths.svg_cache,
    ):
        if not _ensure_writable_dir(directory):
            raise _data_dir_error(directory)
    return paths


def get_models_root(app_data_dir: Optional[Path] = None) -> Path:
    """Return ``<app_data>/models`` root used for default pack layout."""
    base = app_data_dir if app_data_dir is not None else get_app_data_dir()
    return Path(base) / "models"


def get_default_sam3_checkpoint(app_data_dir: Optional[Path] = None) -> Path:
    base = app_data_dir if app_data_dir is not None else get_app_data_dir()
    return Path(base) / DEFAULT_SAM3_REL


def get_default_rmbg_model_dir(app_data_dir: Optional[Path] = None) -> Path:
    base = app_data_dir if app_data_dir is not None else get_app_data_dir()
    return Path(base) / DEFAULT_RMBG_REL


def get_settings_path(
    *,
    app_data_dir: Optional[Path] = None,
    prefer_dev: bool = True,
    repo_root: Optional[Path] = None,
) -> Path:
    """Return preferred settings.json path.

    When ``prefer_dev`` is True, ``FIGURESMITH_DEV_MODE`` is enabled, and
    ``<repo>/.figuresmith/settings.json`` exists, that file wins for developer
    workflows; production resolves settings under the verified app root.
    """
    if prefer_dev and _env_flag(DEV_MODE_ENV, default=False):
        root = repo_root if repo_root is not None else _find_repo_root()
        if root is not None:
            dev_settings = Path(root) / ".figuresmith" / DEFAULT_SETTINGS_NAME
            if dev_settings.is_file():
                return dev_settings

    base = app_data_dir if app_data_dir is not None else get_app_data_dir()
    return Path(base) / DEFAULT_SETTINGS_NAME


def safe_join_under_root(root: PathLike, *parts: str) -> Path:
    """Join ``parts`` under ``root`` and reject path traversal escapes.

    Raises:
        PathTraversalRejected: if the resolved path is outside ``root``.
    """
    root_path = Path(root).resolve()
    candidate = root_path.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise PathTraversalRejected(
            detail=f"path {candidate} escapes models root {root_path}"
        ) from exc
    return candidate


def ensure_under_root(root: PathLike, path: PathLike) -> Path:
    """Resolve ``path`` and ensure it stays under ``root``."""
    root_path = Path(root).resolve()
    candidate = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise PathTraversalRejected(
            detail=f"path {candidate} escapes root {root_path}"
        ) from exc
    return candidate
