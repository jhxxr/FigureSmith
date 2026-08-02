"""Application-only runtime manifest contracts."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from figuresmith.runtime.manifest import (
    RuntimeManifestError,
    build_runtime_manifest,
    verify_runtime_manifest,
    write_runtime_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_import_does_not_require_backend_runtime_dependencies() -> None:
    env = dict(os.environ)
    backend_root = ROOT / "apps" / "backend"
    env["PYTHONPATH"] = str(backend_root)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import figuresmith.runtime.manifest; "
                "assert 'figuresmith.runtime.env' not in sys.modules"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _runtime_pack(root: Path) -> None:
    """A minimal self-contained pack: interpreter, site-packages, application."""
    (root / "app" / "backend").mkdir(parents=True)
    (root / "app" / "vendor" / "autofigure_edit").mkdir(parents=True)
    (root / "app" / "backend" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "app" / "vendor" / "autofigure_edit" / "server.py").write_text(
        "app = object()\n", encoding="utf-8"
    )
    site_packages = root / "python" / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    (root / "python" / "python.exe").write_bytes(b"interpreter")
    (root / "python" / "python312.dll").write_bytes(b"runtime library")
    (root / "python" / "python312._pth").write_text(
        "python312.zip\nLib\\site-packages\n", encoding="utf-8"
    )
    (site_packages / "fastapi").mkdir()
    (site_packages / "fastapi" / "__init__.py").write_text("", encoding="utf-8")


def _write(root: Path, **overrides: object) -> Path:
    kwargs: dict = {"version": "0.7.0", "variant": "cpu", "python_version": "3.12.10"}
    kwargs.update(overrides)
    return write_runtime_manifest(root, **kwargs)


def test_self_contained_manifest_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "运行时 pack"
    root.mkdir()
    _runtime_pack(root)

    manifest_path = _write(root, locks={"requirements": "a" * 64})
    manifest = verify_runtime_manifest(manifest_path, root)

    assert manifest["product"] == "FigureSmith"
    assert manifest["schema"] == 2
    assert manifest["variant"] == "cpu"
    assert manifest["python"]["version"] == "3.12.10"
    assert manifest["runtime_complete"] is True
    assert manifest["contains_weights"] is False
    assert manifest["locks"] == {"requirements": "a" * 64}
    assert all("\\" not in item["path"] for item in manifest["files"])
    # The interpreter and its isolation policy file must be inventoried.
    paths = {item["path"] for item in manifest["files"]}
    assert "python/python.exe" in paths
    assert "python/python312._pth" in paths
    assert "python/Lib/site-packages/fastapi/__init__.py" in paths


def test_pack_without_interpreter_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    (root / "python" / "python.exe").unlink()

    with pytest.raises(RuntimeManifestError, match="python/python.exe"):
        build_runtime_manifest(
            root, version="0.7.0", variant="cpu", python_version="3.12.10"
        )


def test_site_packages_pth_and_bin_ship_but_checkpoints_never_do(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    site_packages = root / "python" / "Lib" / "site-packages"
    (site_packages / "distutils-precedence.pth").write_text("x\n", encoding="utf-8")
    (site_packages / "torch" / "lib").mkdir(parents=True)
    (site_packages / "torch" / "lib" / "cudnn.bin").write_bytes(b"cuda payload")

    manifest_path = _write(root)
    paths = {
        item["path"] for item in verify_runtime_manifest(manifest_path, root)["files"]
    }
    assert "python/Lib/site-packages/distutils-precedence.pth" in paths
    assert "python/Lib/site-packages/torch/lib/cudnn.bin" in paths

    # A real checkpoint is refused even inside site-packages.
    (site_packages / "torch" / "sam3.pt").write_bytes(b"weights")
    with pytest.raises(RuntimeManifestError, match="weight-like file"):
        build_runtime_manifest(
            root, version="0.7.0", variant="cpu", python_version="3.12.10"
        )


def test_loose_wheels_are_refused(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    (root / "fastapi-1.2.3-py3-none-any.whl").write_bytes(b"wheel")

    with pytest.raises(RuntimeManifestError, match="loose wheel"):
        build_runtime_manifest(
            root, version="0.7.0", variant="cpu", python_version="3.12.10"
        )


def test_unknown_variant_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)

    with pytest.raises(RuntimeManifestError, match="unsupported runtime variant"):
        build_runtime_manifest(
            root, version="0.7.0", variant="cu999", python_version="3.12.10"
        )


def test_manifest_rejects_tampered_file_and_extra_file(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    manifest_path = _write(root)

    (root / "app" / "backend" / "main.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="SHA-256 mismatch|size mismatch"):
        verify_runtime_manifest(manifest_path, root)

    _write(root)
    (root / "unexpected.txt").write_text("not listed\n", encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="inventory mismatch"):
        verify_runtime_manifest(manifest_path, root)


def test_manifest_rejects_weights_and_caches(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    (root / "models").mkdir()
    (root / "models" / "sam3.pt").write_bytes(b"weights")
    with pytest.raises(RuntimeManifestError, match="weight-like file"):
        build_runtime_manifest(
            root, version="0.7.0", variant="cpu", python_version="3.12.10"
        )

    (root / "models" / "sam3.pt").unlink()
    # pip leaves __pycache__ behind; .pyc files embed absolute paths and mtimes,
    # so shipping them would break reproducibility and contains_cache=false.
    cache = root / "python" / "Lib" / "site-packages" / "fastapi" / "__pycache__"
    cache.mkdir()
    (cache / "__init__.cpython-312.pyc").write_bytes(b"cache")
    with pytest.raises(RuntimeManifestError, match="cache, build, or mutable-data"):
        build_runtime_manifest(
            root, version="0.7.0", variant="cpu", python_version="3.12.10"
        )


def test_manifest_claiming_incomplete_runtime_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    manifest_path = _write(root)
    data = manifest_path.read_text(encoding="utf-8").replace(
        '"runtime_complete": true', '"runtime_complete": false'
    )
    manifest_path.write_text(data, encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="self-contained"):
        verify_runtime_manifest(manifest_path, root)


def test_schema_1_manifest_is_refused(tmp_path: Path) -> None:
    # An old application-only pack must not verify against Runtime V1.
    root = tmp_path / "runtime"
    root.mkdir()
    _runtime_pack(root)
    manifest_path = _write(root)
    data = manifest_path.read_text(encoding="utf-8").replace(
        '"schema": 2', '"schema": 1'
    )
    manifest_path.write_text(data, encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="unsupported runtime manifest schema"):
        verify_runtime_manifest(manifest_path, root)
