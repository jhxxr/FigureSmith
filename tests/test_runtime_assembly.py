"""Focused tests for Runtime V1 acquisition and offline assembly helpers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from figuresmith.runtime.locks import (
    requirements_lock_name,
    sources_lock_name,
    wheelhouse_manifest_name,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / "runtime" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fetch_script() -> ModuleType:
    return _load_script("fetch_wheelhouse")


@pytest.fixture
def assembly_script() -> ModuleType:
    return _load_script("assemble_runtime")


def test_resolver_decodes_percent_escaped_wheel_filename() -> None:
    resolver = _load_script("resolve_locks")
    assert resolver._wheel_filename(
        "https://download-r2.pytorch.org/whl/cu128/"
        "torch-2.11.0%2Bcu128-cp312-cp312-win_amd64.whl"
    ) == "torch-2.11.0+cu128-cp312-cp312-win_amd64.whl"


def test_fetch_writes_variant_specific_manifest_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetch_script: ModuleType
) -> None:
    payload = b"wheel bytes"
    digest = hashlib.sha256(payload).hexdigest()
    lock_root = tmp_path / "locks"
    lock_root.mkdir()
    lock = {
        "schema": 1,
        "product": "FigureSmith",
        "runtime": {"python": "3.12", "platform": "win_amd64", "cuda": "cpu"},
        "packages": [{
            "name": "demo",
            "version": "1.0.0",
            "wheel": "demo-1.0.0-py3-none-any.whl",
            "url": "https://example.invalid/demo.whl",
            "sha256": digest,
            "tags": ["py3-none-any"],
            "license": "MIT",
        }],
    }
    (lock_root / requirements_lock_name("cpu")).write_text(
        json.dumps(lock), encoding="utf-8"
    )

    def fake_download(url: str, target: Path, expected: str) -> int:
        assert expected == digest
        target.write_bytes(payload)
        return len(payload)

    monkeypatch.setattr(fetch_script, "_download", fake_download)
    out = tmp_path / "wheels"
    fetch_script.fetch("cpu", lock_root, out)

    manifest_path = lock_root / wheelhouse_manifest_name("cpu")
    assert manifest_path.is_file()
    assert not (lock_root / wheelhouse_manifest_name("cu128")).exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["runtime"]["cuda"] == "cpu"
    assert manifest["files"][0]["sha256"] == digest


def test_assembly_copies_and_hashes_all_consumed_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, assembly_script: ModuleType
) -> None:
    variant = "cpu"
    lock_root = tmp_path / "locks"
    lock_root.mkdir()
    names = (
        requirements_lock_name(variant),
        sources_lock_name(variant),
        wheelhouse_manifest_name(variant),
    )
    for index, name in enumerate(names):
        (lock_root / name).write_bytes(f"lock-{index}".encode())

    cpython_digest = "a" * 64
    monkeypatch.setattr(assembly_script, "_read_lock", lambda path: {"path": path.name})
    monkeypatch.setattr(
        assembly_script,
        "validate_requirements_lock",
        lambda value: {"variant": variant, "package_count": 1},
    )
    monkeypatch.setattr(
        assembly_script,
        "validate_sources_lock",
        lambda value: {
            "variant": variant,
            "sources": [{
                "name": "cpython-embeddable",
                "version": "3.12.10",
                "url": "https://example.invalid/python.zip",
                "sha256": cpython_digest,
            }],
        },
    )
    bundle_calls: list[tuple[Path, Path, str]] = []
    monkeypatch.setattr(
        assembly_script,
        "validate_lock_bundle",
        lambda root, *, wheelhouse_root, variant: bundle_calls.append(
            (root, wheelhouse_root, variant)
        ),
    )
    monkeypatch.setattr(assembly_script, "_assert_builder_python", lambda path: None)
    archive = tmp_path / "python.zip"
    archive.write_bytes(b"archive")
    monkeypatch.setattr(assembly_script, "_cached_source", lambda *args: archive)

    def fake_extract(source: Path, python_dir: Path) -> None:
        python_dir.mkdir(parents=True)
        (python_dir / "python.exe").write_bytes(b"python")
        (python_dir / "python312._pth").write_text(
            assembly_script.PTH_CONTENT, encoding="utf-8"
        )

    def fake_copy(pack: Path) -> None:
        (pack / "app/backend").mkdir(parents=True)
        (pack / "app/backend/main.py").write_text("", encoding="utf-8")
        (pack / "app/vendor/autofigure_edit").mkdir(parents=True)
        (pack / "app/vendor/autofigure_edit/server.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(assembly_script, "_extract_cpython", fake_extract)
    monkeypatch.setattr(assembly_script, "_copy_application", fake_copy)
    monkeypatch.setattr(assembly_script, "_install_packages", lambda *args: None)
    monkeypatch.setattr(assembly_script, "render_pip_requirements", lambda value: "")
    monkeypatch.setattr(
        assembly_script,
        "_strip_non_runtime_install_artifacts",
        lambda pack: (0, 0),
    )
    monkeypatch.setattr(assembly_script, "_strip_caches", lambda pack: 0)
    captured: dict[str, object] = {}

    def fake_write(root: Path, **kwargs: object) -> Path:
        captured.update(kwargs)
        path = root / "runtime-manifest.json"
        path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(assembly_script, "write_runtime_manifest", fake_write)
    monkeypatch.setattr(
        assembly_script,
        "verify_runtime_manifest",
        lambda *args: {"file_count": 4, "python": {"version": "3.12.10"}},
    )

    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    out = tmp_path / "out"
    assembly_script.assemble(
        variant=variant,
        lock_root=lock_root,
        wheelhouse=wheelhouse,
        out=out,
        cache=tmp_path / "cache",
        version="0.7.0",
        builder_python=Path("python.exe"),
    )

    assert bundle_calls == [(lock_root, wheelhouse, variant)]
    assert captured["python_source_sha256"] == cpython_digest
    assert captured["locks"] == {
        "requirements": hashlib.sha256(b"lock-0").hexdigest(),
        "sources": hashlib.sha256(b"lock-1").hexdigest(),
        "wheelhouse": hashlib.sha256(b"lock-2").hexdigest(),
    }
    assert {path.name for path in (out / "locks").iterdir()} >= set(names)


def test_assembly_requires_cpython_312_builder(
    monkeypatch: pytest.MonkeyPatch, assembly_script: ModuleType
) -> None:
    monkeypatch.setattr(
        assembly_script.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="CPython\n3.11\n", stderr=""
        ),
    )

    with pytest.raises(assembly_script.AssemblyError, match="requires CPython 3.12"):
        assembly_script._assert_builder_python(Path("python.exe"))


def test_offline_source_cache_refuses_missing_and_tampered_archives(
    tmp_path: Path, assembly_script: ModuleType
) -> None:
    cache = tmp_path / "source-cache"
    url = "https://example.invalid/python-3.12.10-embed-amd64.zip"
    payload = b"pinned archive"
    digest = hashlib.sha256(payload).hexdigest()
    target = assembly_script._source_cache_path(url, digest, cache)

    with pytest.raises(assembly_script.AssemblyError, match="missing from the offline cache"):
        assembly_script._cached_source(url, digest, cache)

    target.parent.mkdir(parents=True)
    target.write_bytes(b"tampered")
    with pytest.raises(assembly_script.AssemblyError, match="digest mismatch"):
        assembly_script._cached_source(url, digest, cache)

    target.write_bytes(payload)
    assert assembly_script._cached_source(url, digest, cache) == target


def test_strip_install_artifacts_removes_launchers_records_and_bytecode(
    tmp_path: Path, assembly_script: ModuleType
) -> None:
    pack = tmp_path / "pack"
    site = pack / "python/Lib/site-packages"
    (site / "bin").mkdir(parents=True)
    (site / "bin/tool.exe").write_bytes(b"launcher")
    (site / "demo.dist-info").mkdir()
    (site / "demo.dist-info/RECORD").write_text("generated", encoding="utf-8")
    (site / "demo/__pycache__").mkdir(parents=True)
    (site / "demo/__pycache__/x.pyc").write_bytes(b"cache")

    assert assembly_script._strip_non_runtime_install_artifacts(pack) == (1, 1)
    assert assembly_script._strip_caches(pack) == 1
    assert not (site / "bin").exists()
    assert not (site / "demo.dist-info/RECORD").exists()
    assert not (site / "demo/__pycache__").exists()
