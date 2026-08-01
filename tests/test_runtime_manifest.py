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


def _application_pack(root: Path) -> None:
    (root / "app" / "backend").mkdir(parents=True)
    (root / "app" / "vendor" / "autofigure_edit").mkdir(parents=True)
    (root / "app" / "backend" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "app" / "vendor" / "autofigure_edit" / "server.py").write_text(
        "app = object()\n", encoding="utf-8"
    )
    (root / "requirements-runtime.txt").write_text(
        "fastapi>=0.110,<1.0\n", encoding="utf-8"
    )


def test_application_manifest_round_trip_without_embedded_python(tmp_path: Path) -> None:
    root = tmp_path / "运行时 pack"
    root.mkdir()
    _application_pack(root)

    manifest_path = write_runtime_manifest(root, version="0.6.2")
    manifest = verify_runtime_manifest(manifest_path, root)

    assert manifest["product"] == "FigureSmith"
    assert manifest["application_only"] is True
    assert manifest["python_required"] == "external"
    assert manifest["runtime_complete"] is False
    assert manifest["contains_weights"] is False
    assert manifest["file_count"] == 3
    assert all("\\" not in item["path"] for item in manifest["files"])
    assert not (root / "python").exists()


def test_manifest_rejects_tampered_file_and_extra_file(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _application_pack(root)
    manifest_path = write_runtime_manifest(root, version="0.6.2")

    (root / "app" / "backend" / "main.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="SHA-256 mismatch|size mismatch"):
        verify_runtime_manifest(manifest_path, root)

    write_runtime_manifest(root, version="0.6.2")
    (root / "unexpected.txt").write_text("not listed\n", encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="inventory mismatch"):
        verify_runtime_manifest(manifest_path, root)


def test_manifest_rejects_weight_cache_and_embedded_python_files(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _application_pack(root)
    (root / "models").mkdir()
    (root / "models" / "sam3.pt").write_bytes(b"weights")
    with pytest.raises(RuntimeManifestError, match="weight-like file"):
        build_runtime_manifest(root, version="0.6.2")

    (root / "models" / "sam3.pt").unlink()
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "cache.pyc").write_bytes(b"cache")
    with pytest.raises(RuntimeManifestError, match="cache, build, or mutable-data"):
        build_runtime_manifest(root, version="0.6.2")

    (root / "__pycache__" / "cache.pyc").unlink()
    (root / "__pycache__").rmdir()
    (root / "python").mkdir()
    (root / "python" / "python.exe").write_bytes(b"interpreter")
    with pytest.raises(RuntimeManifestError, match="weight-like|embedded Python"):
        build_runtime_manifest(root, version="0.6.2")


def test_complete_legacy_mode_requires_python_but_is_not_the_default(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _application_pack(root)
    with pytest.raises(RuntimeManifestError, match="python.exe"):
        build_runtime_manifest(root, version="0.6.2", runtime_complete=True)


def test_manifest_without_application_only_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    _application_pack(root)
    manifest_path = write_runtime_manifest(root, version="0.6.2")
    data = manifest_path.read_text(encoding="utf-8").replace(
        '"application_only": true', '"application_only": false'
    )
    manifest_path.write_text(data, encoding="utf-8")
    with pytest.raises(RuntimeManifestError, match="application-only"):
        verify_runtime_manifest(manifest_path, root)
