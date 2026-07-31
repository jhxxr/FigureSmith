"""Unit tests for model path resolution and safe joins."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figuresmith.models.errors import PathTraversalRejected
from figuresmith.models.paths import (
    get_app_data_dir,
    get_default_rmbg_model_dir,
    get_default_sam3_checkpoint,
    safe_join_under_root,
)
from figuresmith.models.registry import (
    ENV_RMBG_MODEL_PATH,
    ENV_SAM3_CHECKPOINT,
    export_path_env,
    resolve_model_paths,
)


def test_safe_join_under_root_ok(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    target = safe_join_under_root(root, "sam3", "sam3.pt")
    assert target == (root / "sam3" / "sam3.pt").resolve()


def test_safe_join_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    with pytest.raises(PathTraversalRejected) as exc_info:
        safe_join_under_root(root, "..", "etc", "passwd")
    assert exc_info.value.code == "PATH_TRAVERSAL_REJECTED"


def test_resolve_prefers_cli_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_SAM3_CHECKPOINT, str(tmp_path / "env.pt"))
    monkeypatch.setenv(ENV_RMBG_MODEL_PATH, str(tmp_path / "env-rmbg"))
    cli_ckpt = tmp_path / "cli.pt"
    paths = resolve_model_paths(
        sam_checkpoint_path=str(cli_ckpt),
        use_defaults=False,
        app_data_dir=tmp_path / "appdata",
        settings_path=tmp_path / "missing-settings.json",
    )
    assert paths.sam3_checkpoint == Path(cli_ckpt)
    assert paths.source in {"cli", "mixed"}


def test_resolve_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ckpt = tmp_path / "from-env.pt"
    rmbg = tmp_path / "rmbg-env"
    monkeypatch.setenv(ENV_SAM3_CHECKPOINT, str(ckpt))
    monkeypatch.setenv(ENV_RMBG_MODEL_PATH, str(rmbg))
    paths = resolve_model_paths(
        use_defaults=False,
        app_data_dir=tmp_path / "appdata",
        settings_path=tmp_path / "nope.json",
    )
    assert paths.sam3_checkpoint == Path(ckpt)
    assert paths.rmbg_model_dir == Path(rmbg)


def test_resolve_from_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_SAM3_CHECKPOINT, raising=False)
    monkeypatch.delenv(ENV_RMBG_MODEL_PATH, raising=False)
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "models": {
                    "sam3_checkpoint": str(tmp_path / "settings-sam3.pt"),
                    "rmbg_model_path": str(tmp_path / "settings-rmbg"),
                }
            }
        ),
        encoding="utf-8",
    )
    paths = resolve_model_paths(
        use_defaults=False,
        app_data_dir=tmp_path / "appdata",
        settings_path=settings,
    )
    assert paths.sam3_checkpoint == Path(tmp_path / "settings-sam3.pt")
    assert paths.rmbg_model_dir == Path(tmp_path / "settings-rmbg")
    assert paths.source == "settings"


def test_default_layout_under_app_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_SAM3_CHECKPOINT, raising=False)
    monkeypatch.delenv(ENV_RMBG_MODEL_PATH, raising=False)
    monkeypatch.delenv("FIGURESMITH_DATA_DIR", raising=False)
    app_data = tmp_path / "FigureSmithData"
    paths = resolve_model_paths(
        use_defaults=True,
        app_data_dir=app_data,
        settings_path=tmp_path / "missing.json",
    )
    assert paths.sam3_checkpoint == get_default_sam3_checkpoint(app_data)
    assert paths.rmbg_model_dir == get_default_rmbg_model_dir(app_data)


def test_export_path_env(tmp_path: Path) -> None:
    from figuresmith.models.registry import ModelPaths

    paths = ModelPaths(
        sam3_checkpoint=tmp_path / "a.pt",
        sam3_bpe=None,
        rmbg_model_dir=tmp_path / "rmbg",
        source="cli",
    )
    env = export_path_env(paths)
    assert env[ENV_SAM3_CHECKPOINT] == str(tmp_path / "a.pt")
    assert env[ENV_RMBG_MODEL_PATH] == str(tmp_path / "rmbg")
    assert "FIGURESMITH_SAM3_BPE" not in env


def test_get_app_data_dir_honors_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_DATA_DIR", str(tmp_path / "custom-data"))
    assert get_app_data_dir() == (tmp_path / "custom-data").resolve()


def test_get_app_data_dir_does_not_trust_unwritable_explicit_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_local = tmp_path / "LocalAppData"
    fake_local.mkdir()
    blocked = tmp_path / "blocked-file"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setenv("FIGURESMITH_DATA_DIR", str(blocked))
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))
    monkeypatch.delenv("FIGURESMITH_INSTALL_ROOT", raising=False)
    monkeypatch.setattr("figuresmith.models.paths._find_repo_root", lambda: None)

    assert get_app_data_dir() == (fake_local / "FigureSmith").resolve()


def test_get_app_data_dir_uses_install_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer <install_root>/data over LOCALAPPDATA when install root is writable."""
    monkeypatch.delenv("FIGURESMITH_DATA_DIR", raising=False)
    install = tmp_path / "InstallFigureSmith"
    install.mkdir()
    monkeypatch.setenv("FIGURESMITH_INSTALL_ROOT", str(install))
    # Avoid accidental LOCALAPPDATA pollution assertions by ensuring install wins.
    got = get_app_data_dir()
    assert got == (install / "data").resolve()
    assert got.is_dir()


def test_get_app_data_dir_falls_back_when_install_not_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If install data dir cannot be created, fall back to LOCALAPPDATA-style path."""
    monkeypatch.delenv("FIGURESMITH_DATA_DIR", raising=False)
    monkeypatch.delenv("FIGURESMITH_INSTALL_ROOT", raising=False)

    # Point LOCALAPPDATA to temp so we don't touch the real profile.
    fake_local = tmp_path / "LocalAppData"
    fake_local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    # Force install root to a non-writable path by mocking _ensure_writable_dir
    # via an install root on a fake unwritable tree: use a file path as "root".
    blocked = tmp_path / "blocked-file"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setenv("FIGURESMITH_INSTALL_ROOT", str(blocked))

    # Also prevent repo_root/data from winning if the monorepo is writable —
    # monkeypatch _find_repo_root to None for this test.
    import figuresmith.models.paths as paths_mod

    monkeypatch.setattr(paths_mod, "_find_repo_root", lambda: None)

    got = get_app_data_dir()
    assert got == (fake_local / "FigureSmith").resolve()
