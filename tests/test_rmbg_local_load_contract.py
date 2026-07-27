"""RMBG local load contract tests (no GPU / no real weights required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from figuresmith.models.errors import RmbgModelInvalid, RmbgModelMissing
from figuresmith.models.rmbg_loader import (
    build_rmbg_from_pretrained_kwargs,
    should_allow_hf_rmbg_fallback,
    validate_rmbg_model_dir,
)


def _make_valid_rmbg_dir(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_text("{}", encoding="utf-8")
    (root / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (root / "model.safetensors").write_bytes(b"fake")
    return root


def test_validate_missing_dir_raises() -> None:
    with pytest.raises(RmbgModelMissing) as exc_info:
        validate_rmbg_model_dir(None)
    assert exc_info.value.code == "RMBG_MODEL_MISSING"


def test_validate_nonexistent_raises(tmp_path: Path) -> None:
    with pytest.raises(RmbgModelMissing):
        validate_rmbg_model_dir(tmp_path / "nope")


def test_validate_incomplete_dir_raises(tmp_path: Path) -> None:
    d = tmp_path / "rmbg"
    d.mkdir()
    (d / "config.json").write_text("{}", encoding="utf-8")
    # missing preprocessor + weights
    with pytest.raises(RmbgModelInvalid):
        validate_rmbg_model_dir(d)


def test_validate_missing_weights_raises(tmp_path: Path) -> None:
    d = tmp_path / "rmbg"
    d.mkdir()
    (d / "config.json").write_text("{}", encoding="utf-8")
    (d / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RmbgModelInvalid) as exc_info:
        validate_rmbg_model_dir(d)
    assert "weight" in str(exc_info.value).lower() or "model.safetensors" in str(exc_info.value)


def test_validate_ok(tmp_path: Path) -> None:
    d = _make_valid_rmbg_dir(tmp_path / "rmbg-2.0")
    assert validate_rmbg_model_dir(d) == d.resolve()


def test_build_from_pretrained_kwargs_local_only(tmp_path: Path) -> None:
    d = _make_valid_rmbg_dir(tmp_path / "rmbg-2.0")
    kwargs = build_rmbg_from_pretrained_kwargs(d)
    assert kwargs["local_files_only"] is True
    assert kwargs["trust_remote_code"] is True
    assert kwargs["pretrained_model_name_or_path"] == str(d.resolve())


def test_should_allow_hf_fallback_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    monkeypatch.delenv("FIGURESMITH_ALLOW_HF_RMBG", raising=False)
    assert should_allow_hf_rmbg_fallback(None) is False
    assert should_allow_hf_rmbg_fallback(True) is False


def test_vendor_rmbg_markers_and_local_files_only() -> None:
    repo = Path(__file__).resolve().parents[1]
    text = (repo / "vendor" / "autofigure_edit" / "autofigure2.py").read_text(encoding="utf-8")
    assert "local_files_only=True" in text
    assert "FIGURESMITH-BEGIN: rmbg-local-load" in text
    assert "RMBG_MODEL_MISSING" in text
    # Strict path must raise before HF download branch.
    assert "Strict offline mode disables Hugging Face download fallback" in text or (
        "does not download from Hugging Face" in text
    )


def test_mocked_from_pretrained_gets_local_files_only(tmp_path: Path) -> None:
    d = _make_valid_rmbg_dir(tmp_path / "rmbg")
    kwargs = build_rmbg_from_pretrained_kwargs(d)
    mock_fp = MagicMock()
    # Simulate transformers-style signature: first positional is model id/path.
    path = kwargs.pop("pretrained_model_name_or_path")
    mock_fp(path, **kwargs)
    assert mock_fp.call_args.kwargs["local_files_only"] is True
    assert mock_fp.call_args.args[0] == str(d.resolve())
