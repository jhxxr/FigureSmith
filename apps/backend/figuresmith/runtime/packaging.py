"""Packaging path filters — never ship model weights in dist artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

# Globs / suffixes that must never be copied into release packs.
WEIGHT_SUFFIXES = (
    ".pt",
    ".pth",
    ".onnx",
    ".safetensors",
    ".gguf",
    ".ckpt",
    ".h5",
    ".pb",
    ".bin",  # common HF weight shard; may over-exclude rare non-weight bins — acceptable for release safety
)

WEIGHT_DIR_NAMES = {
    "models",  # only when under app data style; still skip copy of any path segment carefully
}

# Path segment names that indicate weight storage (not Python package figuresmith/models).
WEIGHT_STORAGE_SEGMENTS = {
    ".staging",
    ".trash",
}

# Suffixes that a weight scan must not treat as fatal inside an installed
# site-packages tree. ``.pth`` there is an import hook (``distutils-precedence.pth``)
# and ``.bin`` is ordinary package payload, notably in the ``nvidia-*`` CUDA
# wheels. Both are still fatal anywhere else in a pack.
SITE_PACKAGES_ALLOWED_SUFFIXES = (".pth", ".bin")

# Path segments that mark a runtime's own interpreter tree.
_PYTHON_TREE_SEGMENTS = ("site-packages", "dist-packages")


def _in_site_packages(parts_lower: list[str]) -> bool:
    return any(segment in parts_lower for segment in _PYTHON_TREE_SEGMENTS)


def is_weight_file(path: Path | str, *, site_packages_root: Path | str | None = None) -> bool:
    """Return True if path looks like a model weight file.

    Detection is context-aware rather than suffix-only. A self-contained runtime
    legitimately ships ``python312._pth`` and ``.pth``/``.bin`` files inside
    ``site-packages``; a real ``sam3.pt`` must still be refused wherever it
    appears. Pass ``site_packages_root`` to treat a specific directory as the
    installed-package tree; otherwise a ``site-packages`` path segment is used.
    """
    p = Path(path)
    name = p.name.lower()
    suffix = p.suffix.lower()
    parts_lower = [part.lower() for part in p.parts]

    # An embeddable interpreter's isolation policy file must ship.
    if name.endswith("._pth"):
        return False

    in_site_packages = _in_site_packages(parts_lower)
    if not in_site_packages and site_packages_root is not None:
        try:
            p.resolve().relative_to(Path(site_packages_root).resolve())
            in_site_packages = True
        except (OSError, ValueError):
            in_site_packages = False

    # HuggingFace shard naming stays fatal even inside site-packages.
    if name.startswith("pytorch_model") and suffix == ".bin":
        return True
    if name.startswith("model") and suffix == ".safetensors":
        return True

    if in_site_packages and suffix in SITE_PACKAGES_ALLOWED_SUFFIXES:
        return False

    if suffix in WEIGHT_SUFFIXES:
        return True
    if name in {"model.safetensors.index.json"}:
        return False
    return False


def is_excluded_packaging_path(
    path: Path | str,
    *,
    root: Path | None = None,
    site_packages_root: Path | str | None = None,
) -> bool:
    """Return True if this path must not be copied into Runtime/Desktop packs.

    Excludes weight files and common cache/output dirs. Does **not** exclude the
    Python package ``figuresmith/models`` (source .py only), nor legitimate
    ``.pth``/``.bin`` files inside an installed ``site-packages`` tree.
    """
    p = Path(path)
    parts_lower = [x.lower() for x in p.parts]

    if is_weight_file(p, site_packages_root=site_packages_root):
        return True

    # Skip venv/caches/outputs
    skip_dirs = {
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "outputs",
        "uploads",
        "target",  # rust
        "dist",
    }
    if any(part in skip_dirs for part in parts_lower):
        return True

    # App-data style models weight trees: .../models/sam3/sam3.pt already weight;
    # also skip entire copied user models roots named exactly under resources/models
    if "resources" in parts_lower and "models" in parts_lower:
        # resources/models is weight staging
        try:
            idx = parts_lower.index("resources")
            if idx + 1 < len(parts_lower) and parts_lower[idx + 1] == "models":
                return True
        except ValueError:
            pass

    if any(seg in WEIGHT_STORAGE_SEGMENTS for seg in parts_lower):
        return True

    return False


def iter_packaging_files(
    source_root: Path, *, site_packages_root: Path | str | None = None
) -> Iterator[Path]:
    """Yield files under source_root that are safe to package."""
    source_root = Path(source_root)
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded_packaging_path(
            path, root=source_root, site_packages_root=site_packages_root
        ):
            continue
        yield path


def filter_packaging_paths(
    paths: Iterable[Path | str], *, site_packages_root: Path | str | None = None
) -> list[Path]:
    """Filter an iterable of paths to those allowed in packs."""
    return [
        Path(p)
        for p in paths
        if not is_excluded_packaging_path(p, site_packages_root=site_packages_root)
    ]


__all__ = [
    "SITE_PACKAGES_ALLOWED_SUFFIXES",
    "WEIGHT_SUFFIXES",
    "filter_packaging_paths",
    "is_excluded_packaging_path",
    "is_weight_file",
    "iter_packaging_files",
]
