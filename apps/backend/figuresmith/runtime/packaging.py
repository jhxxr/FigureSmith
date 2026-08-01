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


def is_weight_file(path: Path | str) -> bool:
    """Return True if path looks like a model weight file."""
    p = Path(path)
    name = p.name.lower()
    suffix = p.suffix.lower()
    if name == "python312._pth":
        return True
    if suffix in WEIGHT_SUFFIXES:
        return True
    # HuggingFace style: model-00001-of-00002.safetensors already caught; pytorch_model.bin
    if name.startswith("pytorch_model") and suffix == ".bin":
        return True
    if name in {"model.safetensors.index.json"}:
        return False
    return False


def is_excluded_packaging_path(path: Path | str, *, root: Path | None = None) -> bool:
    """Return True if this path must not be copied into Runtime/Desktop packs.

    Excludes weight files and common cache/output dirs. Does **not** exclude the
    Python package ``figuresmith/models`` (source .py only).
    """
    p = Path(path)
    parts_lower = [x.lower() for x in p.parts]

    if is_weight_file(p):
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


def iter_packaging_files(source_root: Path) -> Iterator[Path]:
    """Yield files under source_root that are safe to package."""
    source_root = Path(source_root)
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded_packaging_path(path, root=source_root):
            continue
        yield path


def filter_packaging_paths(paths: Iterable[Path | str]) -> list[Path]:
    """Filter an iterable of paths to those allowed in packs."""
    return [Path(p) for p in paths if not is_excluded_packaging_path(p)]


__all__ = [
    "WEIGHT_SUFFIXES",
    "filter_packaging_paths",
    "is_excluded_packaging_path",
    "is_weight_file",
    "iter_packaging_files",
]
