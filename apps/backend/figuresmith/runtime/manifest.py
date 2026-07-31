"""Generate and verify immutable runtime manifests.

The desktop resolver uses a small identity check before it starts Python.  This
module owns the stronger, build-time contract: every staged file is listed with
its size and SHA-256 digest, and weight/cache/user-data paths are rejected
instead of silently omitted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from figuresmith.runtime.packaging import is_weight_file

MANIFEST_NAME = "runtime-manifest.json"
MANIFEST_SCHEMA = 1
REQUIRED_FILES = (
    "app/backend/main.py",
    "app/vendor/autofigure_edit/server.py",
)
PYTHON_FILES = ("python.exe", "python/python.exe")

_FORBIDDEN_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".staging",
    ".trash",
    "__pycache__",
    "node_modules",
    "outputs",
    "target",
    "uploads",
    ".venv",
    "venv",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RuntimeManifestError(ValueError):
    """Raised when a runtime tree or manifest violates the release contract."""


def _root_dir(root: Path | str) -> Path:
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeManifestError(f"runtime root is not a directory: {path}")
    return path


def _relative_path(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root)
    except ValueError as exc:
        raise RuntimeManifestError(f"runtime file escapes root: {path}") from exc
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise RuntimeManifestError(f"invalid runtime relative path: {path}")
    return PurePosixPath(*relative.parts).as_posix()


def _forbidden_reason(root: Path, path: Path) -> str | None:
    relative = path.relative_to(root)
    parts = [part.lower() for part in relative.parts]
    if is_weight_file(path):
        return "weight-like file"
    if any(part in _FORBIDDEN_DIR_NAMES for part in parts):
        return "cache, build, or mutable-data directory"
    if len(parts) >= 2 and parts[0:2] == ["resources", "models"]:
        return "model staging directory"
    return None


def _iter_runtime_files(root: Path) -> list[Path]:
    offenders: list[str] = []
    files: list[Path] = []
    manifest_path = root / MANIFEST_NAME

    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path == manifest_path:
            continue
        if path.is_symlink():
            offenders.append(f"{path}: symlink is not allowed")
            continue
        if not path.is_file():
            continue
        _relative_path(root, path)
        reason = _forbidden_reason(root, path)
        if reason is not None:
            offenders.append(f"{path}: {reason}")
            continue
        files.append(path)

    if offenders:
        detail = "; ".join(offenders[:20])
        if len(offenders) > 20:
            detail += f"; and {len(offenders) - 20} more"
        raise RuntimeManifestError(f"runtime tree contains forbidden files: {detail}")
    return files


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_required_file(paths: Iterable[str], candidates: Iterable[str]) -> bool:
    values = set(paths)
    return any(candidate in values for candidate in candidates)


def build_runtime_manifest(
    root: Path | str,
    *,
    version: str,
    platform: str = "Windows",
    arch: str = "x86_64",
    runtime_complete: bool = True,
) -> dict[str, Any]:
    """Build a deterministic manifest for an already assembled runtime tree."""
    runtime_root = _root_dir(root)
    files = _iter_runtime_files(runtime_root)
    entries = [
        {
            "path": _relative_path(runtime_root, path),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in files
    ]
    listed_paths = [entry["path"] for entry in entries]

    if runtime_complete:
        missing = [name for name in REQUIRED_FILES if name not in listed_paths]
        if not _has_required_file(listed_paths, PYTHON_FILES):
            missing.append("python.exe or python/python.exe")
        if missing:
            raise RuntimeManifestError(
                "complete runtime is missing required files: " + ", ".join(missing)
            )

    return {
        "schema": MANIFEST_SCHEMA,
        "product": "FigureSmith",
        "version": str(version),
        "platform": str(platform),
        "arch": str(arch),
        "runtime_complete": bool(runtime_complete),
        "contains_weights": False,
        "contains_cache": False,
        "file_count": len(entries),
        "files": entries,
    }


def write_runtime_manifest(
    root: Path | str,
    *,
    version: str,
    platform: str = "Windows",
    arch: str = "x86_64",
    runtime_complete: bool = True,
    output: Path | str | None = None,
) -> Path:
    """Write a manifest atomically and return its canonical path."""
    runtime_root = _root_dir(root)
    output_path = (
        runtime_root / MANIFEST_NAME
        if output is None
        else Path(output).expanduser().resolve()
    )
    if output_path.name != MANIFEST_NAME:
        raise RuntimeManifestError(
            f"runtime manifest must be named {MANIFEST_NAME}: {output_path}"
        )
    if output_path != runtime_root / MANIFEST_NAME:
        raise RuntimeManifestError("runtime manifest must live at the runtime root")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_runtime_manifest(
        runtime_root,
        version=version,
        platform=platform,
        arch=arch,
        runtime_complete=runtime_complete,
    )
    encoded = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{MANIFEST_NAME}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output_path


def _manifest_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeManifestError(
            f"manifest contains invalid relative path: {value!r}"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RuntimeManifestError(
            f"manifest contains invalid relative path: {value!r}"
        )
    return path.as_posix()


def _validate_manifest_shape(
    manifest: Mapping[str, Any], *, require_complete: bool
) -> list[dict[str, Any]]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise RuntimeManifestError("unsupported runtime manifest schema")
    if manifest.get("product") != "FigureSmith":
        raise RuntimeManifestError("runtime manifest product is not FigureSmith")
    if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
        raise RuntimeManifestError("runtime manifest version is missing")
    if manifest.get("contains_weights") is not False:
        raise RuntimeManifestError(
            "runtime manifest does not prove contains_weights=false"
        )
    if manifest.get("contains_cache") is not False:
        raise RuntimeManifestError(
            "runtime manifest does not prove contains_cache=false"
        )
    if require_complete and manifest.get("runtime_complete") is not True:
        raise RuntimeManifestError(
            "runtime manifest is not a complete packaged runtime"
        )

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise RuntimeManifestError("runtime manifest files must be a list")
    entries: list[dict[str, Any]] = []
    paths: set[str] = set()
    for raw in raw_files:
        if not isinstance(raw, Mapping):
            raise RuntimeManifestError("runtime manifest file entry is not an object")
        relative = _manifest_relative_path(raw.get("path"))
        if relative in paths:
            raise RuntimeManifestError(
                f"runtime manifest lists a file twice: {relative}"
            )
        size = raw.get("size_bytes")
        digest = raw.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise RuntimeManifestError(f"invalid size for runtime file: {relative}")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise RuntimeManifestError(f"invalid SHA-256 for runtime file: {relative}")
        paths.add(relative)
        entries.append({"path": relative, "size_bytes": size, "sha256": digest})

    if manifest.get("file_count") != len(entries):
        raise RuntimeManifestError("runtime manifest file_count does not match files")
    if require_complete:
        missing = [name for name in REQUIRED_FILES if name not in paths]
        if not _has_required_file(paths, PYTHON_FILES):
            missing.append("python.exe or python/python.exe")
        if missing:
            raise RuntimeManifestError(
                "complete runtime manifest is missing required files: "
                + ", ".join(missing)
            )
    return entries


def verify_runtime_manifest(
    manifest_path: Path | str,
    runtime_root: Path | str | None = None,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Verify manifest metadata and, when supplied, every staged file hash."""
    manifest_file = Path(manifest_path).expanduser().resolve()
    if manifest_file.name != MANIFEST_NAME:
        raise RuntimeManifestError(f"unexpected runtime manifest name: {manifest_file}")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeManifestError(
            f"runtime manifest is unreadable: {manifest_file}"
        ) from exc
    if not isinstance(manifest, Mapping):
        raise RuntimeManifestError("runtime manifest must be a JSON object")
    entries = _validate_manifest_shape(manifest, require_complete=require_complete)

    if runtime_root is None:
        runtime_root_path = manifest_file.parent
    else:
        runtime_root_path = _root_dir(runtime_root)
    expected_manifest = runtime_root_path / MANIFEST_NAME
    if manifest_file != expected_manifest:
        raise RuntimeManifestError("runtime manifest must live at the runtime root")

    actual_files = _iter_runtime_files(runtime_root_path)
    actual_by_path = {
        _relative_path(runtime_root_path, path): path for path in actual_files
    }
    expected_by_path = {entry["path"]: entry for entry in entries}
    if set(actual_by_path) != set(expected_by_path):
        missing = sorted(set(expected_by_path) - set(actual_by_path))
        extra = sorted(set(actual_by_path) - set(expected_by_path))
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing[:10]))
        if extra:
            details.append("extra=" + ",".join(extra[:10]))
        raise RuntimeManifestError(
            "runtime file inventory mismatch (" + "; ".join(details) + ")"
        )

    for relative, entry in expected_by_path.items():
        path = actual_by_path[relative]
        if path.stat().st_size != entry["size_bytes"]:
            raise RuntimeManifestError(f"runtime file size mismatch: {relative}")
        if _sha256_file(path) != entry["sha256"]:
            raise RuntimeManifestError(f"runtime file SHA-256 mismatch: {relative}")
    return dict(manifest)


__all__ = [
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA",
    "REQUIRED_FILES",
    "RuntimeManifestError",
    "build_runtime_manifest",
    "verify_runtime_manifest",
    "write_runtime_manifest",
]
