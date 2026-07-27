"""RMBG import tests: folder/ZIP, required files, pin policy, rollback."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from figuresmith.models.checksums import sha256_file
from figuresmith.models.errors import (
    ModelImportPinMismatch,
    RmbgModelInvalid,
    RmbgModelMissing,
)
from figuresmith.models.import_rmbg import import_rmbg_pack, verify_installed_rmbg
from figuresmith.models.manager import ModelManager
from figuresmith.models.manifest import evaluate_pin, require_pin_or_raise
from figuresmith.models.paths import get_default_rmbg_model_dir


def _make_rmbg_dir(root: Path, weight: bytes = b"fake-rmbg-weight") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text('{"model_type":"birefnet"}', encoding="utf-8")
    (root / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (root / "model.safetensors").write_bytes(weight)
    return root


def _zip_dir(src_dir: Path, zip_path: Path) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in src_dir.rglob("*"):
            if path.is_file():
                arc = path.relative_to(src_dir).as_posix()
                zf.write(path, arcname=arc)
    zip_path.write_bytes(buf.getvalue())
    return zip_path


def test_import_rmbg_from_folder(tmp_path: Path) -> None:
    src = _make_rmbg_dir(tmp_path / "RMBG-2.0")
    app_data = tmp_path / "appdata"
    result = import_rmbg_pack(src, kind="dir", app_data_dir=app_data, require_absolute=True)
    assert result.success is True
    dest = get_default_rmbg_model_dir(app_data)
    assert dest == result.destination or dest.resolve() == result.destination.resolve()
    assert (dest / "config.json").is_file()
    assert (dest / "model.safetensors").is_file()
    assert (dest / "metadata.json").is_file()
    meta = json.loads((dest / "metadata.json").read_text(encoding="utf-8"))
    assert meta["id"] == "rmbg-2.0"
    assert meta["official_verified"] is False
    assert any("trust_remote_code" in w.lower() or "可信" in w for w in result.warnings)

    settings = json.loads((app_data / "settings.json").read_text(encoding="utf-8"))
    assert Path(settings["models"]["rmbg_model_path"]) == dest.resolve() or settings[
        "models"
    ]["rmbg_model_path"] == str(dest)


def test_import_rmbg_from_zip(tmp_path: Path) -> None:
    src_dir = _make_rmbg_dir(tmp_path / "pack")
    zpath = _zip_dir(src_dir, tmp_path / "rmbg.zip")
    app_data = tmp_path / "ad"
    result = import_rmbg_pack(zpath, kind="zip", app_data_dir=app_data)
    assert result.success is True
    assert result.kind == "zip"
    assert (result.destination / "preprocessor_config.json").is_file()


def test_import_rmbg_zip_with_nested_root(tmp_path: Path) -> None:
    nested = _make_rmbg_dir(tmp_path / "wrap" / "RMBG-2.0")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in nested.rglob("*"):
            if path.is_file():
                arc = path.relative_to(tmp_path / "wrap").as_posix()
                zf.write(path, arcname=arc)
    zpath = tmp_path / "nested.zip"
    zpath.write_bytes(buf.getvalue())
    result = import_rmbg_pack(zpath, app_data_dir=tmp_path / "data")
    assert (result.destination / "model.safetensors").is_file()
    assert (result.destination / "config.json").is_file()


def test_import_rmbg_incomplete_dir_rejects(tmp_path: Path) -> None:
    d = tmp_path / "bad"
    d.mkdir()
    (d / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RmbgModelInvalid):
        import_rmbg_pack(d, kind="dir", app_data_dir=tmp_path / "ad")


def test_import_rmbg_rollback_keeps_old(tmp_path: Path) -> None:
    app_data = tmp_path / "app"
    good = _make_rmbg_dir(tmp_path / "good", weight=b"weight-v1")
    first = import_rmbg_pack(good, app_data_dir=app_data)
    old = (first.destination / "model.safetensors").read_bytes()

    bad = _make_rmbg_dir(tmp_path / "bad", weight=b"weight-v2")
    with patch(
        "figuresmith.models.import_rmbg.validate_rmbg_model_dir",
        side_effect=RmbgModelInvalid(detail="nope"),
    ):
        # Force failure after copy by patching _ensure_required_files path
        with patch(
            "figuresmith.models.import_rmbg._ensure_required_files",
            side_effect=RmbgModelInvalid(detail="incomplete"),
        ):
            with pytest.raises(RmbgModelInvalid):
                import_rmbg_pack(bad, app_data_dir=app_data)

    assert (first.destination / "model.safetensors").read_bytes() == old
    staging = app_data / "models" / ".staging"
    if staging.exists():
        assert list(staging.iterdir()) == []


def test_pin_policy_mismatch_and_allow(tmp_path: Path) -> None:
    weight = b"rmbg-pin-test"
    src = _make_rmbg_dir(tmp_path / "p", weight=weight)
    digest = sha256_file(src / "model.safetensors")
    manifest = {
        "models": [
            {
                "id": "rmbg-2.0",
                "official_sha256": "b" * 64,
                "files_sha256": {"model.safetensors": "b" * 64},
            }
        ]
    }
    rejected = evaluate_pin(
        "rmbg-2.0", digest, manifest=manifest, allow_unpinned=False
    )
    assert rejected.allowed is False
    with pytest.raises(ModelImportPinMismatch):
        require_pin_or_raise(
            "rmbg-2.0", digest, manifest=manifest, allow_unpinned=False
        )

    allowed = evaluate_pin(
        "rmbg-2.0", digest, manifest=manifest, allow_unpinned=True
    )
    assert allowed.allowed is True
    assert allowed.official_verified is False

    # Matching pin
    manifest_ok = {
        "models": [{"id": "rmbg-2.0", "official_sha256": digest}]
    }
    ok = evaluate_pin("rmbg-2.0", digest, manifest=manifest_ok)
    assert ok.official_verified is True
    assert ok.allowed is True

    # Import with mismatch + allow_unpinned
    result = import_rmbg_pack(
        src,
        app_data_dir=tmp_path / "ad2",
        allow_unpinned=True,
    )
    # Without pin in real manifest (null), official_verified false — still success
    assert result.success is True


def test_import_rmbg_pin_reject_integration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FIGURESMITH_ALLOW_UNPINNED_MODELS", raising=False)
    src = _make_rmbg_dir(tmp_path / "x")
    with patch(
        "figuresmith.models.import_rmbg.require_pin_or_raise",
        side_effect=ModelImportPinMismatch(detail="no"),
    ):
        with pytest.raises(ModelImportPinMismatch):
            import_rmbg_pack(src, app_data_dir=tmp_path / "ad")


def test_manager_rmbg_lifecycle(tmp_path: Path) -> None:
    app = tmp_path / "data"
    mgr = ModelManager(app_data_dir=app)
    src = _make_rmbg_dir(tmp_path / "src")
    mgr.import_rmbg(src, kind="dir")
    assert mgr.rmbg_status()["installed"] is True
    assert mgr.verify_rmbg()["verified"] is True
    mgr.delete_rmbg()
    assert mgr.rmbg_status()["installed"] is False
    with pytest.raises((RmbgModelMissing, Exception)):
        mgr.verify_rmbg()
