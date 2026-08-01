"""Runtime manifest generation and verification contracts."""

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


def test_manifest_import_does_not_require_backend_runtime_dependencies() -> None:
    env = dict(os.environ)
    backend_root = Path(__file__).parents[1] / "apps" / "backend"
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


def _complete_runtime(root: Path) -> None:
    (root / "app" / "backend").mkdir(parents=True)
    (root / "app" / "vendor" / "autofigure_edit").mkdir(parents=True)
    (root / "app" / "backend" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "app" / "vendor" / "autofigure_edit" / "server.py").write_text(
        "app = object()\n", encoding="utf-8"
    )
    # A tiny fixture is enough; the assembly pipeline supplies the real
    # embeddable interpreter before marking a runtime complete.
    (root / "python.exe").write_bytes(b"python-fixture")


def test_complete_manifest_round_trip_with_unicode_root(tmp_path: Path) -> None:
    root = tmp_path / "运行时 pack"
    root.mkdir()
    _complete_runtime(root)

    manifest_path = write_runtime_manifest(root, version="0.6.0")
    manifest = verify_runtime_manifest(manifest_path, root)

    assert manifest["product"] == "FigureSmith"
    assert manifest["runtime_complete"] is True
    assert manifest["contains_weights"] is False
    assert manifest["file_count"] == 3
    assert all("\\" not in item["path"] for item in manifest["files"])


def test_manifest_rejects_tampered_file_and_extra_file(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _complete_runtime(root)
    manifest_path = write_runtime_manifest(root, version="0.6.0")

    (root / "app" / "backend" / "main.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="SHA-256 mismatch|size mismatch"):
        verify_runtime_manifest(manifest_path, root)

    # Rebuild the inventory, then add an unlisted file to exercise the second
    # independent check.
    write_runtime_manifest(root, version="0.6.0")
    (root / "unexpected.txt").write_text("not listed\n", encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="inventory mismatch"):
        verify_runtime_manifest(manifest_path, root)


def test_manifest_rejects_weight_and_cache_files(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _complete_runtime(root)
    (root / "models").mkdir()
    (root / "models" / "sam3.pt").write_bytes(b"weights")
    with pytest.raises(RuntimeManifestError, match="weight-like file"):
        build_runtime_manifest(root, version="0.6.0")

    (root / "models" / "sam3.pt").unlink()
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "cache.pyc").write_bytes(b"cache")
    with pytest.raises(RuntimeManifestError, match="cache, build, or mutable-data"):
        build_runtime_manifest(root, version="0.6.0")


def test_incomplete_manifest_is_explicitly_not_release_runtime(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "README.md").write_text("dependency-install pack\n", encoding="utf-8")

    manifest_path = write_runtime_manifest(
        root,
        version="0.6.0",
        runtime_complete=False,
    )
    verify_runtime_manifest(manifest_path, root, require_complete=False)
    with pytest.raises(RuntimeManifestError, match="not a complete packaged runtime"):
        verify_runtime_manifest(manifest_path, root)
