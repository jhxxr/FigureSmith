"""Smoke test: figuresmith package imports and reports a version."""

from __future__ import annotations


def test_figuresmith_import_and_version() -> None:
    import figuresmith

    assert hasattr(figuresmith, "__version__")
    assert figuresmith.__version__ == "0.5.0"


def test_vendor_bridge_paths() -> None:
    from figuresmith.pipeline.vendor_bridge import (
        VENDOR_ROOT,
        ensure_vendor_on_sys_path,
        get_repo_root,
        get_vendor_root,
        get_vendor_server_module_hint,
    )

    repo = get_repo_root()
    assert (repo / "apps" / "backend").is_dir()
    assert (repo / "vendor" / "autofigure_edit").is_dir()

    root = get_vendor_root()
    assert root == VENDOR_ROOT
    assert root == repo / "vendor" / "autofigure_edit"
    assert root.is_dir()
    assert (root / "server.py").is_file()
    assert (root / "autofigure2.py").is_file()
    assert get_vendor_server_module_hint() == "server:app"
    ensure_vendor_on_sys_path()
