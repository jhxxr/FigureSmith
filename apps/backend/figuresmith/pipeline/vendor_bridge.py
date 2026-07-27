"""Vendor path helpers for the AutoFigure-Edit baseline.

Phase 1 keeps the upstream tree under ``vendor/autofigure_edit`` and only
exposes path resolution so the FigureSmith package can import/run it without
rewriting pipeline code.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _find_repo_root() -> Path:
    """Locate the monorepo root without assuming a fixed install layout.

    Preferred markers: ``vendor/autofigure_edit`` + ``apps/backend``.
    Falls back to the source-tree relative path used in Phase 1 development
    (``.../apps/backend/figuresmith/pipeline/this_file`` → 4 parents up).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "vendor" / "autofigure_edit").is_dir() and (
            parent / "apps" / "backend"
        ).is_dir():
            return parent
    # Source layout fallback: pipeline -> figuresmith -> backend -> apps -> root
    return here.parents[4]


_REPO_ROOT = _find_repo_root()
_VENDOR_ROOT = _REPO_ROOT / "vendor" / "autofigure_edit"

VENDOR_ROOT: Path = _VENDOR_ROOT


def get_vendor_root() -> Path:
    """Return the absolute path to ``vendor/autofigure_edit``."""
    return VENDOR_ROOT


def get_repo_root() -> Path:
    """Return the FigureSmith repository root."""
    return _REPO_ROOT


def ensure_vendor_on_sys_path() -> Path:
    """Insert the vendor root on ``sys.path`` if missing and return it.

    Vendor code is a flat module layout (``server.py``, ``autofigure2.py``),
    not an installable package, so path injection is required for imports.
    """
    root = get_vendor_root()
    if not root.is_dir():
        raise FileNotFoundError(
            f"Vendor AutoFigure-Edit tree not found at {root}. "
            "Expected Phase 1 import under vendor/autofigure_edit/."
        )
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def get_vendor_server_module_hint() -> str:
    """Return the uvicorn target string for the vendor FastAPI app."""
    return "server:app"


def get_svg_edit_vendor_path() -> Path:
    """Return the monorepo-level svg-edit copy (boundary tree)."""
    return _REPO_ROOT / "vendor" / "svg_edit"


def get_runtime_svg_edit_path() -> Path:
    """Return the svg-edit path used by the vendor web server at runtime."""
    return VENDOR_ROOT / "web" / "vendor" / "svg-edit"
