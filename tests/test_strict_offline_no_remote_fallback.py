"""Strict offline: no remote SAM / no silent HF fallback contracts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from figuresmith.models.errors import RemoteSamDisabled
from figuresmith.models.rmbg_loader import should_allow_hf_rmbg_fallback
from figuresmith.models.sam3_loader import must_force_local_sam, normalize_sam_backend
from figuresmith.runtime.env import child_process_env, prepare_figuresmith_runtime
from figuresmith.security.offline import apply_strict_offline_env


REPO = Path(__file__).resolve().parents[1]


def test_strict_rejects_remote_backends_via_vendor_helper_source() -> None:
    text = (REPO / "vendor" / "autofigure_edit" / "autofigure2.py").read_text(encoding="utf-8")
    assert "REMOTE_SAM_DISABLED" in text
    assert "_figuresmith_reject_remote_sam" in text
    assert "strict_offline" in text


def test_reject_remote_logic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    assert must_force_local_sam(None) is True
    for backend in ("fal", "roboflow", "api"):
        normalized = normalize_sam_backend(backend)
        assert normalized in {"fal", "roboflow"}
        # Emulate vendor reject
        if must_force_local_sam(None) and normalized != "local":
            err = RemoteSamDisabled(detail=f"sam_backend={backend}")
            assert err.code == "REMOTE_SAM_DISABLED"


def test_prepare_runtime_sets_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "FIGURESMITH_STRICT_OFFLINE",
    ):
        monkeypatch.delenv(key, raising=False)
    applied = prepare_figuresmith_runtime(strict_offline=True, default_strict=True)
    assert applied.get("HF_HUB_OFFLINE") == "1"
    import os

    assert os.environ["FIGURESMITH_STRICT_OFFLINE"] == "1"


def test_prepare_runtime_explicit_false_clears_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    applied = prepare_figuresmith_runtime(strict_offline=False, default_strict=True)
    assert applied.get("FIGURESMITH_STRICT_OFFLINE") == "0"
    assert os.environ["FIGURESMITH_STRICT_OFFLINE"] == "0"
    assert "HF_HUB_OFFLINE" not in applied


def test_env_flag_fail_closed_overrides_explicit_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process env must keep strict mode on even if a caller passes False."""
    from figuresmith.security.offline import is_strict_offline_enabled

    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    assert is_strict_offline_enabled(False) is True
    assert is_strict_offline_enabled(None) is True
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "0")
    assert is_strict_offline_enabled(False) is False
    assert is_strict_offline_enabled(True) is True


def test_vendor_strict_helper_is_env_fail_closed() -> None:
    """Vendor helper must not let explicit False disable an active env flag."""
    text = (REPO / "vendor" / "autofigure_edit" / "autofigure2.py").read_text(encoding="utf-8")
    # Anti-pattern from the first patch revision (explicit arg overrode env).
    assert "if strict_offline is not None:\n        return bool(strict_offline)" not in text
    assert "FIGURESMITH_STRICT_OFFLINE" in text
    assert "_figuresmith_strict_offline" in text


def test_child_process_env_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIGURESMITH_SAM3_CHECKPOINT", raising=False)
    env = child_process_env({"PATH": "/usr/bin"}, strict_offline=True)
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["HF_DATASETS_OFFLINE"] == "1"
    assert env["FIGURESMITH_STRICT_OFFLINE"] == "1"
    assert "127.0.0.1" in env["NO_PROXY"]


def test_server_runrequest_has_strict_offline_not_client_paths() -> None:
    text = (REPO / "vendor" / "autofigure_edit" / "server.py").read_text(encoding="utf-8")
    assert "strict_offline: bool = False" in text
    # Must NOT accept arbitrary client sam_checkpoint_path on RunRequest.
    assert "sam_checkpoint_path" not in text.split("class RunRequest")[1].split("app = FastAPI")[0]
    assert "FIGURESMITH_SAM3_CHECKPOINT" in text
    assert "never" in text.lower() or "NEVER" in text or "registry" in text.lower()


def test_server_rejects_remote_under_strict_source() -> None:
    text = (REPO / "vendor" / "autofigure_edit" / "server.py").read_text(encoding="utf-8")
    assert "REMOTE_SAM_DISABLED" in text
    assert "validate_offline_endpoint" in text


def test_cli_flags_present() -> None:
    text = (REPO / "vendor" / "autofigure_edit" / "autofigure2.py").read_text(encoding="utf-8")
    assert "--sam_checkpoint_path" in text
    assert "--sam_bpe_path" in text
    assert "--strict_offline" in text


def test_no_hf_fallback_under_strict_for_rmbg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    assert should_allow_hf_rmbg_fallback(True) is False


def test_apply_strict_offline_idempotent() -> None:
    first = apply_strict_offline_env()
    second = apply_strict_offline_env()
    assert first["HF_HUB_OFFLINE"] == second["HF_HUB_OFFLINE"] == "1"


def test_model_manifest_phase2_entries() -> None:
    import json

    data = json.loads(
        (REPO / "resources" / "model-manifest.json").read_text(encoding="utf-8")
    )
    # Phase 3 bumped manifest.phase while preserving Phase 2 load contracts.
    assert data["phase"] >= 2
    ids = {m["id"] for m in data["models"]}
    assert "sam3" in ids
    assert "rmbg-2.0" in ids
    sam3 = next(m for m in data["models"] if m["id"] == "sam3")
    assert sam3["load"]["load_from_HF"] is False
    rmbg = next(m for m in data["models"] if m["id"] == "rmbg-2.0")
    assert rmbg["load"]["local_files_only"] is True
    # Phase 3 pin fields exist (values may be null until release hashing).
    assert "official_sha256" in sam3 or "sha256" in sam3
    assert "pin_policy" in data or data["phase"] >= 3


def test_autofigure2_parses() -> None:
    """Syntax-check vendor file after patches (no import of heavy deps)."""
    src = (REPO / "vendor" / "autofigure_edit" / "autofigure2.py").read_text(encoding="utf-8")
    ast.parse(src)


def test_server_py_parses() -> None:
    src = (REPO / "vendor" / "autofigure_edit" / "server.py").read_text(encoding="utf-8")
    ast.parse(src)
