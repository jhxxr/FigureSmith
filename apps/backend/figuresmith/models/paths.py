"""App data directories and safe path joins for local model packs."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, Union

from figuresmith.models.errors import PathTraversalRejected

PathLike = Union[str, Path]

# Relative default layout under the app data / models root.
DEFAULT_SAM3_REL = Path("models") / "sam3" / "sam3.pt"
DEFAULT_RMBG_REL = Path("models") / "rmbg-2.0"
DEFAULT_SETTINGS_NAME = "settings.json"
DATA_DIR_NAME = "data"


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
    """Create ``path`` if needed and verify it is writable."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".fs_write_", dir=str(path))
        os.close(fd)
        Path(name).unlink(missing_ok=True)
        return True
    except OSError:
        return False


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


def get_app_data_dir() -> Path:
    """Return the FigureSmith application data directory (models, settings, …).

    Resolution order (first writable wins):

    1. ``FIGURESMITH_DATA_DIR`` — explicit user/admin override
    2. ``FIGURESMITH_INSTALL_ROOT/data`` — installer/portable root
    3. ``<executable_dir>/data`` — when frozen or executable name looks like FigureSmith
    4. ``<repo_root>/data`` — source / Runtime Pack layout (same drive as install tree)
    5. ``%LOCALAPPDATA%\\FigureSmith`` (or macOS/Linux equivalent) — last resort
       when the install directory is not writable (e.g. Program Files)

    This prefers “next to the app” so large model imports stay on the install
    drive instead of always filling the system C: user profile.
    """
    override = os.environ.get("FIGURESMITH_DATA_DIR")
    if override and override.strip():
        path = Path(override).expanduser().resolve()
        _ensure_writable_dir(path)
        return path

    candidates: list[Path] = []

    install_root = os.environ.get("FIGURESMITH_INSTALL_ROOT")
    if install_root and install_root.strip():
        candidates.append(Path(install_root).expanduser() / DATA_DIR_NAME)

    try:
        exe = Path(sys.executable).resolve()
        frozen = bool(getattr(sys, "frozen", False))
        name_l = exe.name.lower()
        if frozen or "figuresmith" in name_l:
            candidates.append(exe.parent / DATA_DIR_NAME)
    except (OSError, RuntimeError):
        pass

    repo = _find_repo_root()
    if repo is not None:
        candidates.append(repo / DATA_DIR_NAME)

    for cand in candidates:
        if _ensure_writable_dir(cand):
            return cand.resolve()

    fallback = _localappdata_fallback()
    _ensure_writable_dir(fallback)
    return fallback.resolve()


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

    When ``prefer_dev`` is True and ``<repo>/.figuresmith/settings.json`` exists,
    that file wins for developer workflows; otherwise app data settings path.
    """
    if prefer_dev:
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
