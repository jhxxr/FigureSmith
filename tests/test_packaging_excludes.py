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
    assert is_weight_file("third_party/model.pth")


def test_embeddable_isolation_policy_file_is_not_a_weight() -> None:
    # A self-contained runtime cannot start without its ._pth isolation policy,
    # so suffix-only detection must not classify it as a model weight.
    assert not is_weight_file("python/python312._pth")
    assert not is_weight_file(Path("runtime/python/python313._pth"))


def test_site_packages_payload_is_allowed_but_weights_still_refused() -> None:
    site = "python/Lib/site-packages"
    # Import hooks and CUDA wheel payload ship inside site-packages.
    assert not is_weight_file(f"{site}/distutils-precedence.pth")
    assert not is_weight_file(f"{site}/nvidia/cublas/bin/cublas64_12.bin")
    assert not is_weight_file(f"{site}/torch/_inductor/config.bin")
    # Real weights stay fatal wherever they appear.
    assert is_weight_file(f"{site}/sam3/sam3.pt")
    assert is_weight_file(f"{site}/transformers/pytorch_model.bin")
    assert is_weight_file(f"{site}/some_pkg/model.safetensors")
    # The same suffixes outside site-packages remain fatal.
    assert is_weight_file("app/resources/thing.bin")
    assert is_weight_file("app/backend/checkpoint.pth")


def test_site_packages_root_overrides_path_segment_detection(tmp_path: Path) -> None:
    # A tree installed under a non-standard directory name still counts when the
    # caller names it explicitly.
    root = tmp_path / "runtime" / "pylibs"
    payload = root / "nvidia" / "cudnn.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"x")
    assert is_weight_file(payload)
    assert not is_weight_file(payload, site_packages_root=root)
    weight = root / "sam3.pt"
    weight.write_bytes(b"w")
    assert is_weight_file(weight, site_packages_root=root)


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
