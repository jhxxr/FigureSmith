"""Validation for reproducible Windows runtime input locks.

The lock files are build inputs, not dependency-resolution instructions.  Every
runtime wheel/source must be exact-versioned, fetched from an HTTPS URL, and
identified by a SHA-256 digest before assembly is allowed to use it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

LOCK_SCHEMA = 1
# Runtime V1 ships two variants from one assembly path. ``cu128`` carries the
# CUDA wheels; ``cpu`` carries a CPU-only Torch pair and no ``nvidia-*`` wheels.
SUPPORTED_VARIANTS = ("cpu", "cu128")
DEFAULT_VARIANT = "cu128"
REQUIREMENTS_LOCK_NAME = "requirements-win-py312-cu128.lock.json"
SOURCES_LOCK_NAME = "sources.lock.json"
WHEELHOUSE_MANIFEST_NAME = "wheelhouse-manifest.json"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)+(?:[+.-][0-9A-Za-z]+)*$")
_FORBIDDEN_SEGMENTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".staging",
    ".trash",
    "models",
    "outputs",
    "uploads",
}
_WEIGHT_SUFFIXES = {
    ".bin",
    ".ckpt",
    ".gguf",
    ".h5",
    ".onnx",
    ".pb",
    ".pt",
    ".pth",
    ".safetensors",
}


class RuntimeLockError(ValueError):
    """Raised when a committed lock or its verified cache is unsafe."""


def requirements_lock_name(variant: str = DEFAULT_VARIANT) -> str:
    """Return the committed requirements-lock filename for a variant."""
    if variant not in SUPPORTED_VARIANTS:
        raise RuntimeLockError(f"unsupported runtime variant: {variant!r}")
    return f"requirements-win-py312-{variant}.lock.json"


def sources_lock_name(variant: str = DEFAULT_VARIANT) -> str:
    """Return the committed sources-lock filename for a variant.

    CPython and the native DLL chain are identical across variants, but every
    lock file carries a variant stamp and a bundle must agree on it, so each
    variant gets its own copy rather than sharing one unstamped file.
    """
    if variant not in SUPPORTED_VARIANTS:
        raise RuntimeLockError(f"unsupported runtime variant: {variant!r}")
    return f"sources-{variant}.lock.json"


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeLockError(f"{label} must be a JSON object")
    return value


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeLockError(f"cannot read lock JSON: {path}") from exc
    return _object(value, str(path))


def _header(value: Mapping[str, Any], label: str) -> str:
    if value.get("schema") != LOCK_SCHEMA:
        raise RuntimeLockError(f"{label} has unsupported schema")
    if value.get("product") != "FigureSmith":
        raise RuntimeLockError(f"{label} product is not FigureSmith")
    runtime = _object(value.get("runtime"), f"{label}.runtime")
    if runtime.get("python") != "3.12" or runtime.get("platform") != "win_amd64":
        raise RuntimeLockError(
            f"{label} targets something other than Windows Python 3.12"
        )
    variant = runtime.get("cuda")
    if variant not in SUPPORTED_VARIANTS:
        raise RuntimeLockError(
            f"{label} variant must be one of {', '.join(SUPPORTED_VARIANTS)}"
        )
    return str(variant)


def _exact_version(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise RuntimeLockError(f"{label} must be an exact version, not a range")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise RuntimeLockError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _https_url(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise RuntimeLockError(f"{label} must be an HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeLockError(f"{label} must use HTTPS")
    return value


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeLockError(f"{label} must be a relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RuntimeLockError(f"{label} escapes its root")
    if any(part.lower() in _FORBIDDEN_SEGMENTS for part in path.parts):
        raise RuntimeLockError(f"{label} contains a forbidden cache/data segment")
    return path.as_posix()


def _wheel_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.endswith(".whl"):
        raise RuntimeLockError(f"{label} must name a wheel; sdists are forbidden")
    if "/" in value or "\\" in value or not value.strip():
        raise RuntimeLockError(f"{label} must be a wheel filename")
    return value


def validate_requirements_lock(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact wheel lock consumed by offline assembly."""
    variant = _header(value, "requirements lock")
    raw_packages = value.get("packages")
    if not isinstance(raw_packages, list) or not raw_packages:
        raise RuntimeLockError("requirements lock packages must be a non-empty list")
    names: set[str] = set()
    packages: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_packages):
        package = _object(raw, f"requirements lock packages[{index}]")
        name = package.get("name")
        if not isinstance(name, str) or not name.strip() or name.lower() in names:
            raise RuntimeLockError(
                f"requirements lock has duplicate/invalid package: {name!r}"
            )
        names.add(name.lower())
        version = _exact_version(package.get("version"), f"package {name}.version")
        wheel = _wheel_name(package.get("wheel"), f"package {name}.wheel")
        url = _https_url(package.get("url"), f"package {name}.url")
        digest = _sha256(package.get("sha256"), f"package {name}.sha256")
        tags = package.get("tags")
        if (
            not isinstance(tags, list)
            or not tags
            or not all(isinstance(tag, str) for tag in tags)
        ):
            raise RuntimeLockError(f"package {name}.tags must list wheel tags")
        license_name = package.get("license")
        if not isinstance(license_name, str) or not license_name.strip():
            raise RuntimeLockError(f"package {name}.license is required")
        packages.append(
            {
                "name": name,
                "version": version,
                "wheel": wheel,
                "url": url,
                "sha256": digest,
                "tags": list(tags),
                "license": license_name,
            }
        )
    return {"packages": packages, "package_count": len(packages), "variant": variant}


def validate_sources_lock(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate CPython/SAM3/source archives and immutable revisions."""
    variant = _header(value, "sources lock")
    raw_sources = value.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise RuntimeLockError("sources lock sources must be a non-empty list")
    names: set[str] = set()
    sources: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_sources):
        source = _object(raw, f"sources lock sources[{index}]")
        name = source.get("name")
        if not isinstance(name, str) or not name.strip() or name.lower() in names:
            raise RuntimeLockError(
                f"sources lock has duplicate/invalid source: {name!r}"
            )
        names.add(name.lower())
        kind = source.get("kind")
        if kind not in {"archive", "git"}:
            raise RuntimeLockError(f"source {name}.kind must be archive or git")
        version = _exact_version(source.get("version"), f"source {name}.version")
        url = _https_url(source.get("url"), f"source {name}.url")
        digest = _sha256(source.get("sha256"), f"source {name}.sha256")
        license_name = source.get("license")
        if not isinstance(license_name, str) or not license_name.strip():
            raise RuntimeLockError(f"source {name}.license is required")
        revision = source.get("revision")
        if kind == "git":
            if not isinstance(revision, str) or not _HEX40.fullmatch(revision):
                raise RuntimeLockError(
                    f"source {name}.revision must be a full commit hash"
                )
        elif revision is not None:
            raise RuntimeLockError(
                f"archive source {name} must not declare a git revision"
            )
        sources.append(
            {
                "name": name,
                "kind": kind,
                "version": version,
                "url": url,
                "sha256": digest,
                "license": license_name,
                **({"revision": revision} if revision is not None else {}),
            }
        )
    return {"sources": sources, "source_count": len(sources), "variant": variant}


def validate_wheelhouse_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the inventory of already acquired wheel files."""
    variant = _header(value, "wheelhouse manifest")
    raw_files = value.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise RuntimeLockError("wheelhouse manifest files must be a non-empty list")
    seen: set[str] = set()
    files: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_files):
        entry = _object(raw, f"wheelhouse files[{index}]")
        relative = _relative_path(entry.get("path"), f"wheelhouse files[{index}].path")
        if relative in seen:
            raise RuntimeLockError(
                f"wheelhouse manifest lists a file twice: {relative}"
            )
        seen.add(relative)
        if not relative.lower().endswith(".whl"):
            raise RuntimeLockError(f"wheelhouse entry is not a wheel: {relative}")
        if Path(relative).suffix.lower() in _WEIGHT_SUFFIXES:
            raise RuntimeLockError(
                f"wheelhouse entry looks like a model weight: {relative}"
            )
        size = entry.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise RuntimeLockError(f"wheelhouse size is invalid: {relative}")
        digest = _sha256(entry.get("sha256"), f"wheelhouse {relative}.sha256")
        files.append({"path": relative, "size_bytes": size, "sha256": digest})
    if value.get("file_count") != len(files):
        raise RuntimeLockError("wheelhouse file_count does not match files")
    return {"files": files, "file_count": len(files), "variant": variant}


def render_pip_requirements(value: Mapping[str, Any]) -> str:
    """Render a locked requirements file that pip verifies by digest.

    Assembly feeds this to ``pip install --require-hashes --no-deps
    --no-index``. Emitting ``==`` pins with ``--hash`` makes pip enforce the
    same digests this module checks, so a tampered wheelhouse fails twice
    rather than relying on our pre-check alone.
    """
    checked = validate_requirements_lock(value)
    lines = [
        "# Generated from the FigureSmith runtime lock. Do not edit by hand.",
        f"# variant: {checked['variant']}  packages: {checked['package_count']}",
        "--no-index",
        "",
    ]
    for package in sorted(checked["packages"], key=lambda item: item["name"].lower()):
        lines.append(
            f"{package['name']}=={package['version']} "
            f"--hash=sha256:{package['sha256']}"
        )
    return "\n".join(lines) + "\n"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_wheelhouse_files(
    manifest: Mapping[str, Any], wheelhouse_root: Path | str
) -> dict[str, Any]:
    """Verify every wheel in the inventory and reject unlisted files."""
    checked = validate_wheelhouse_manifest(manifest)
    root = Path(wheelhouse_root).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeLockError(f"wheelhouse directory is missing: {root}")
    expected = {entry["path"]: entry for entry in checked["files"]}
    actual: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeLockError(f"wheelhouse symlink is not allowed: {path}")
        if not path.is_file():
            continue
        try:
            relative_value = path.resolve().relative_to(root)
        except ValueError as exc:
            raise RuntimeLockError(f"wheelhouse file escapes its root: {path}") from exc
        relative = _relative_path(relative_value.as_posix(), "wheelhouse file")
        actual[relative] = path
    if set(actual) != set(expected):
        raise RuntimeLockError("wheelhouse file inventory does not match lock")
    for relative, entry in expected.items():
        path = actual[relative]
        if path.stat().st_size != entry["size_bytes"]:
            raise RuntimeLockError(f"wheel size mismatch: {relative}")
        if _sha256_file(path) != entry["sha256"]:
            raise RuntimeLockError(f"wheel SHA-256 mismatch: {relative}")
    return {"wheel_count": len(expected), "root": str(root)}


def validate_lock_bundle(
    lock_root: Path | str,
    *,
    wheelhouse_root: Path | str | None = None,
    variant: str | None = None,
) -> dict[str, Any]:
    """Validate all committed lock files and optionally their offline cache.

    ``variant`` selects which requirements lock to read. When omitted, any
    single committed variant is accepted; an ambiguous lock root is an error so
    a CPU pack can never be assembled from the CUDA lock by accident.
    """
    root = Path(lock_root).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeLockError(f"lock directory is missing: {root}")
    if variant is None:
        present = [
            name
            for name in SUPPORTED_VARIANTS
            if (root / requirements_lock_name(name)).is_file()
        ]
        if not present:
            raise RuntimeLockError(f"no requirements lock found under {root}")
        if len(present) > 1:
            raise RuntimeLockError(
                "lock root is ambiguous; pass variant explicitly: "
                + ", ".join(present)
            )
        variant = present[0]
    requirements_path = root / requirements_lock_name(variant)
    requirements = validate_requirements_lock(_read_json(requirements_path))
    sources = validate_sources_lock(_read_json(root / sources_lock_name(variant)))
    wheelhouse_value = _read_json(root / WHEELHOUSE_MANIFEST_NAME)
    wheelhouse = validate_wheelhouse_manifest(wheelhouse_value)
    # All three locks must agree on the variant they target.
    variants = {
        requirements.get("variant"),
        sources.get("variant"),
        wheelhouse.get("variant"),
    }
    if variants != {variant}:
        raise RuntimeLockError(
            f"lock bundle variants do not match {variant!r}: {sorted(variants)}"
        )
    result = {**requirements, **sources, **wheelhouse, "lock_root": str(root)}
    if wheelhouse_root is not None:
        result.update(verify_wheelhouse_files(wheelhouse_value, wheelhouse_root))
    return result


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate FigureSmith runtime locks")
    parser.add_argument("lock_root", type=Path)
    parser.add_argument("--wheelhouse", type=Path, default=None)
    parser.add_argument("--variant", choices=SUPPORTED_VARIANTS, default=None)
    parser.add_argument(
        "--emit-requirements",
        type=Path,
        default=None,
        help="write a pip --require-hashes requirements file for the variant",
    )
    args = parser.parse_args(argv)
    try:
        result = validate_lock_bundle(
            args.lock_root,
            wheelhouse_root=args.wheelhouse,
            variant=args.variant,
        )
        if args.emit_requirements is not None:
            lock_path = Path(result["lock_root"]) / requirements_lock_name(
                str(result["variant"])
            )
            rendered = render_pip_requirements(_read_json(lock_path))
            args.emit_requirements.parent.mkdir(parents=True, exist_ok=True)
            args.emit_requirements.write_text(rendered, encoding="utf-8", newline="\n")
            result["emitted_requirements"] = str(args.emit_requirements)
    except RuntimeLockError as exc:
        print(f"runtime lock validation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI smoke is shell-tested
    raise SystemExit(_main())


__all__ = [
    "DEFAULT_VARIANT",
    "LOCK_SCHEMA",
    "REQUIREMENTS_LOCK_NAME",
    "SOURCES_LOCK_NAME",
    "SUPPORTED_VARIANTS",
    "WHEELHOUSE_MANIFEST_NAME",
    "RuntimeLockError",
    "render_pip_requirements",
    "requirements_lock_name",
    "sources_lock_name",
    "validate_lock_bundle",
    "validate_requirements_lock",
    "validate_sources_lock",
    "validate_wheelhouse_manifest",
    "verify_wheelhouse_files",
]
