"""Tests for packaging weight-exclusion helpers."""

from __future__ import annotations

from pathlib import Path

from figuresmith.runtime.packaging import (
    filter_packaging_paths,
    is_excluded_packaging_path,
    is_weight_file,
    iter_packaging_files,
)


def test_is_weight_file() -> None:
    assert is_weight_file("sam3.pt")
    assert is_weight_file("model.safetensors")
    assert is_weight_file(Path("x/y/model.onnx"))
    assert not is_weight_file("manager.py")
    assert not is_weight_file("readme.md")
    assert is_weight_file("python/python312._pth")
    assert is_weight_file("third_party/model.pth")


def test_excludes_weights_but_keeps_python_models_pkg(tmp_path: Path) -> None:
    py = tmp_path / "apps" / "backend" / "figuresmith" / "models" / "manager.py"
    py.parent.mkdir(parents=True)
    py.write_text("# ok", encoding="utf-8")
    weight = tmp_path / "apps" / "backend" / "figuresmith" / "models" / "sam3.pt"
    weight.write_bytes(b"w")

    assert not is_excluded_packaging_path(py)
    assert is_excluded_packaging_path(weight)

    allowed = list(iter_packaging_files(tmp_path))
    assert py in allowed or any(p.name == "manager.py" for p in allowed)
    assert all(p.suffix != ".pt" for p in allowed)


def test_excludes_resources_models_and_caches(tmp_path: Path) -> None:
    staged = tmp_path / "resources" / "models" / "x.pt"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"w")
    cache = tmp_path / "foo" / "__pycache__" / "a.pyc"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"c")
    assert is_excluded_packaging_path(staged)
    assert is_excluded_packaging_path(cache)


def test_filter_packaging_paths() -> None:
    paths = [
        Path("a.py"),
        Path("w.pt"),
        Path("model.safetensors"),
        Path("readme.md"),
    ]
    out = filter_packaging_paths(paths)
    names = {p.name for p in out}
    assert "a.py" in names
    assert "readme.md" in names
    assert "w.pt" not in names
    assert "model.safetensors" not in names
