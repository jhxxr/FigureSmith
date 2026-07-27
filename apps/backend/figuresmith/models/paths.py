"""App data directories and safe path joins for local model packs."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Union

from figuresmith.models.errors import PathTraversalRejected

PathLike = Union[str, Path]

# Relative default layout under the app data / models root.
DEFAULT_SAM3_REL = Path("models") / "sam3" / "sam3.pt"
DEFAULT_RMBG_REL = Path("models") / "rmbg-2.0"
DEFAULT_SETTINGS_NAME = "settings.json"


def get_app_data_dir() -> Path:
    """Return the FigureSmith application data directory.

    Resolution order:
    1. ``FIGURESMITH_DATA_DIR``
    2. Windows: ``%LOCALAPPDATA%\\FigureSmith``
    3. macOS: ``~/Library/Application Support/FigureSmith``
    4. Linux/other: ``$XDG_DATA_HOME/figuresmith`` or ``~/.local/share/figuresmith``
    """
    override = os.environ.get("FIGURESMITH_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

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
        root = repo_root
        if root is None:
            # Best-effort: walk up from this file looking for monorepo markers.
            here = Path(__file__).resolve()
            for parent in here.parents:
                if (parent / "vendor" / "autofigure_edit").is_dir() and (
                    parent / "apps" / "backend"
                ).is_dir():
                    root = parent
                    break
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
    # Disallow absolute segments and empty ".." only after resolve check.
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
