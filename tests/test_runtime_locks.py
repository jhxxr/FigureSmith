"""Runtime lock schema and offline wheelhouse verification contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from figuresmith.runtime.locks import (
    REQUIREMENTS_LOCK_NAME,
    SOURCES_LOCK_NAME,
    WHEELHOUSE_MANIFEST_NAME,
    RuntimeLockError,
    validate_lock_bundle,
    validate_requirements_lock,
    validate_sources_lock,
    validate_wheelhouse_manifest,
)


RUNTIME = {"python": "3.12", "platform": "win_amd64", "cuda": "cu128"}


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_bundle(tmp_path: Path) -> tuple[Path, Path]:
    lock_root = tmp_path / "locks"
    wheelhouse = tmp_path / "wheelhouse"
    lock_root.mkdir()
    wheelhouse.mkdir()
    wheel_name = "fastapi-1.2.3-py3-none-any.whl"
    wheel_bytes = b"wheel fixture"
    (wheelhouse / wheel_name).write_bytes(wheel_bytes)

    _write_json(
        lock_root / REQUIREMENTS_LOCK_NAME,
        {
            "schema": 1,
            "product": "FigureSmith",
            "runtime": RUNTIME,
            "packages": [
                {
                    "name": "fastapi",
                    "version": "1.2.3",
                    "wheel": wheel_name,
                    "url": "https://files.example.invalid/fastapi.whl",
                    "sha256": _digest(wheel_bytes),
                    "tags": ["py3-none-any"],
                    "license": "MIT",
                }
            ],
        },
    )
    _write_json(
        lock_root / SOURCES_LOCK_NAME,
        {
            "schema": 1,
            "product": "FigureSmith",
            "runtime": RUNTIME,
            "sources": [
                {
                    "name": "cpython-embeddable",
                    "kind": "archive",
                    "version": "3.12.4",
                    "url": "https://www.python.org/ftp/python/3.12.4/python.zip",
                    "sha256": "a" * 64,
                    "license": "PSF-2.0",
                },
                {
                    "name": "sam3-source",
                    "kind": "git",
                    "version": "0.1.0",
                    "revision": "b" * 40,
                    "url": "https://github.com/facebookresearch/sam3.git",
                    "sha256": "c" * 64,
                    "license": "Apache-2.0",
                },
            ],
        },
    )
    _write_json(
        lock_root / WHEELHOUSE_MANIFEST_NAME,
        {
            "schema": 1,
            "product": "FigureSmith",
            "runtime": RUNTIME,
            "file_count": 1,
            "files": [
                {
                    "path": wheel_name,
                    "size_bytes": len(wheel_bytes),
                    "sha256": _digest(wheel_bytes),
                }
            ],
        },
    )
    return lock_root, wheelhouse


def test_lock_bundle_validates_exact_inputs_and_cache_hashes(tmp_path: Path) -> None:
    lock_root, wheelhouse = _write_bundle(tmp_path)

    result = validate_lock_bundle(lock_root, wheelhouse_root=wheelhouse)

    assert result["package_count"] == 1
    assert result["source_count"] == 2
    assert result["wheel_count"] == 1


def test_requirements_lock_rejects_ranges_and_sdists(tmp_path: Path) -> None:
    lock_root, _ = _write_bundle(tmp_path)
    requirements = json.loads(
        (lock_root / REQUIREMENTS_LOCK_NAME).read_text(encoding="utf-8")
    )
    requirements["packages"][0]["version"] = ">=1.2"
    with pytest.raises(RuntimeLockError, match="exact version"):
        validate_requirements_lock(requirements)

    requirements["packages"][0]["version"] = "1.2.3"
    requirements["packages"][0]["wheel"] = "fastapi-1.2.3.tar.gz"
    with pytest.raises(RuntimeLockError, match="sdists"):
        validate_requirements_lock(requirements)


def test_sources_lock_requires_immutable_git_revision(tmp_path: Path) -> None:
    lock_root, _ = _write_bundle(tmp_path)
    sources = json.loads((lock_root / SOURCES_LOCK_NAME).read_text(encoding="utf-8"))
    sources["sources"][1]["revision"] = "main"

    with pytest.raises(RuntimeLockError, match="full commit hash"):
        validate_sources_lock(sources)


def test_wheelhouse_verification_rejects_tamper_and_unlisted_files(
    tmp_path: Path,
) -> None:
    lock_root, wheelhouse = _write_bundle(tmp_path)
    manifest = json.loads(
        (lock_root / WHEELHOUSE_MANIFEST_NAME).read_text(encoding="utf-8")
    )
    validate_wheelhouse_manifest(manifest)

    wheel = next(wheelhouse.glob("*.whl"))
    wheel.write_bytes(b"tampered-data")
    with pytest.raises(RuntimeLockError, match="SHA-256 mismatch"):
        validate_lock_bundle(lock_root, wheelhouse_root=wheelhouse)

    wheel.write_bytes(b"wheel fixture")
    (wheelhouse / "extra.whl").write_bytes(b"unlisted")
    with pytest.raises(RuntimeLockError, match="inventory"):
        validate_lock_bundle(lock_root, wheelhouse_root=wheelhouse)


def test_wheelhouse_manifest_rejects_weight_like_path(tmp_path: Path) -> None:
    lock_root, _ = _write_bundle(tmp_path)
    manifest = json.loads(
        (lock_root / WHEELHOUSE_MANIFEST_NAME).read_text(encoding="utf-8")
    )
    manifest["files"][0]["path"] = "models/sam3.pt"
    with pytest.raises(RuntimeLockError, match="forbidden cache/data segment"):
        validate_wheelhouse_manifest(manifest)
