"""Vendor bridge discovery for source and packaged runtime layouts."""

from __future__ import annotations

from pathlib import Path

from figuresmith.pipeline.vendor_bridge import _find_repo_root_from


def _module_path(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True)
    path.write_text("# fixture\n", encoding="utf-8")
    return path


def test_vendor_bridge_finds_source_root(tmp_path: Path) -> None:
    root = tmp_path / "source"
    (root / "vendor" / "autofigure_edit").mkdir(parents=True)
    (root / "apps" / "backend").mkdir(parents=True)
    module = _module_path(
        root, "apps", "backend", "figuresmith", "pipeline", "vendor_bridge.py"
    )

    assert _find_repo_root_from(module) == root.resolve()


def test_vendor_bridge_finds_packaged_app_root(tmp_path: Path) -> None:
    root = tmp_path / "runtime" / "app"
    (root / "vendor" / "autofigure_edit").mkdir(parents=True)
    (root / "backend").mkdir(parents=True)
    module = _module_path(
        root, "backend", "figuresmith", "pipeline", "vendor_bridge.py"
    )

    assert _find_repo_root_from(module) == root.resolve()
