"""SAM3 import + rollback tests (tiny fixtures, no real weights)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from figuresmith.models.errors import (
    ModelImportInvalidSource,
    ModelImportPinMismatch,
    ModelImportSizeError,
    Sam3ModelInvalid,
)
from figuresmith.models.import_sam3 import import_sam3_checkpoint, verify_installed_sam3
from figuresmith.models.manager import ModelManager
from figuresmith.models.paths import get_default_sam3_checkpoint


def _fake_pt(path: Path, payload: bytes = b"fake-sam3-weights") -> Path:
    path.write_bytes(payload)
    return path


def test_import_sam3_success(tmp_path: Path) -> None:
    source = tmp_path / "user" / "sam3.pt"
    source.parent.mkdir(parents=True, exist_ok=True)
    _fake_pt(source)

    app_data = tmp_path / "appdata"
    result = import_sam3_checkpoint(
        source,
        app_data_dir=app_data,
        min_bytes=1,
        require_absolute=True,
    )
    assert result.success is True
    assert result.checkpoint.is_file()
    assert result.checkpoint == get_default_sam3_checkpoint(app_data)
    assert (result.destination / "metadata.json").is_file()
    assert (result.destination / "checksum.sha256").is_file()
    meta = json.loads((result.destination / "metadata.json").read_text(encoding="utf-8"))
    assert meta["id"] == "sam3"
    assert meta["verified"] is True
    assert meta["sha256"] == result.sha256
    assert meta["load_verified"] == "skipped"
    assert meta["official_verified"] is False

    # settings mirror
    settings = json.loads((app_data / "settings.json").read_text(encoding="utf-8"))
    assert settings["models"]["sam3_checkpoint"] == str(result.checkpoint)


def test_import_sam3_rejects_relative(tmp_path: Path) -> None:
    with pytest.raises(ModelImportInvalidSource):
        import_sam3_checkpoint("relative/sam3.pt", app_data_dir=tmp_path, min_bytes=1)


def test_import_sam3_rejects_bad_extension(tmp_path: Path) -> None:
    bad = tmp_path / "model.bin"
    bad.write_bytes(b"x" * 10)
    with pytest.raises(ModelImportInvalidSource):
        import_sam3_checkpoint(bad, app_data_dir=tmp_path, min_bytes=1)


def test_import_sam3_size_too_small(tmp_path: Path) -> None:
    src = tmp_path / "sam3.pt"
    src.write_bytes(b"tiny")
    with pytest.raises(ModelImportSizeError):
        import_sam3_checkpoint(src, app_data_dir=tmp_path, min_bytes=1000, max_bytes=10_000)


def test_import_sam3_rollback_leaves_old_intact(tmp_path: Path) -> None:
    app_data = tmp_path / "appdata"
    # Install a good first model.
    good = tmp_path / "good.pt"
    good.write_bytes(b"good-weights-v1")
    first = import_sam3_checkpoint(
        good, app_data_dir=app_data, min_bytes=1, require_absolute=True
    )
    old_bytes = first.checkpoint.read_bytes()
    old_meta = (first.destination / "metadata.json").read_text(encoding="utf-8")

    # Second import fails during validation after staging copy.
    bad_src = tmp_path / "bad.pt"
    bad_src.write_bytes(b"bad-weights-v2")

    with patch(
        "figuresmith.models.import_sam3.validate_sam3_checkpoint",
        side_effect=Sam3ModelInvalid(detail="boom"),
    ):
        with pytest.raises(Sam3ModelInvalid):
            import_sam3_checkpoint(
                bad_src, app_data_dir=app_data, min_bytes=1, require_absolute=True
            )

    # Old model intact; no leftover staging.
    assert first.checkpoint.read_bytes() == old_bytes
    assert (first.destination / "metadata.json").read_text(encoding="utf-8") == old_meta
    staging_root = app_data / "models" / ".staging"
    if staging_root.exists():
        assert list(staging_root.iterdir()) == []


def test_import_sam3_pin_mismatch_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FIGURESMITH_ALLOW_UNPINNED_MODELS", raising=False)
    src = tmp_path / "sam3.pt"
    src.write_bytes(b"pinned-or-not")

    fake_manifest = {
        "models": [
            {
                "id": "sam3",
                "official_sha256": "0" * 64,
            }
        ]
    }
    with patch(
        "figuresmith.models.import_sam3.require_pin_or_raise",
        side_effect=ModelImportPinMismatch(detail="mismatch"),
    ):
        with pytest.raises(ModelImportPinMismatch):
            import_sam3_checkpoint(src, app_data_dir=tmp_path / "ad", min_bytes=1)

    # Also exercise real pin path via evaluate through require with patched manifest loader.
    from figuresmith.models.manifest import require_pin_or_raise
    from figuresmith.models.checksums import sha256_file

    with pytest.raises(ModelImportPinMismatch):
        require_pin_or_raise(
            "sam3",
            sha256_file(src),
            manifest=fake_manifest,
            allow_unpinned=False,
        )


def test_import_sam3_pin_mismatch_allowed_with_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIGURESMITH_ALLOW_UNPINNED_MODELS", "1")
    src = tmp_path / "sam3.pt"
    src.write_bytes(b"dev-weights")
    manifest = {"models": [{"id": "sam3", "official_sha256": "a" * 64}]}

    from figuresmith.models.checksums import sha256_file
    from figuresmith.models.manifest import evaluate_pin

    pin = evaluate_pin("sam3", sha256_file(src), manifest=manifest, allow_unpinned=True)
    assert pin.allowed is True
    assert pin.official_verified is False

    # Full import with patched require that still allows
    result = import_sam3_checkpoint(
        src,
        app_data_dir=tmp_path / "app",
        min_bytes=1,
        allow_unpinned=True,
    )
    assert result.success is True


def test_manager_list_verify_delete(tmp_path: Path) -> None:
    app_data = tmp_path / "data"
    mgr = ModelManager(app_data_dir=app_data)
    listed = mgr.list_models()
    assert listed["models"][0]["id"] == "sam3"
    assert listed["models"][0]["installed"] is False

    src = tmp_path / "sam3.pt"
    src.write_bytes(b"mgr-weights")
    mgr.import_sam3(src, min_bytes=1, require_absolute=True)
    assert mgr.sam3_status()["installed"] is True
    verified = mgr.verify_sam3()
    assert verified["verified"] is True
    deleted = mgr.delete_sam3()
    assert deleted["deleted"] is True
    assert mgr.sam3_status()["installed"] is False


def test_verify_installed_sam3(tmp_path: Path) -> None:
    app_data = tmp_path / "ad"
    src = tmp_path / "s.pt"
    src.write_bytes(b"vv")
    import_sam3_checkpoint(src, app_data_dir=app_data, min_bytes=1)
    info = verify_installed_sam3(app_data_dir=app_data)
    assert info["installed"] is True
    assert len(info["sha256"]) == 64
