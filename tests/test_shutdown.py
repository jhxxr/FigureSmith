"""Tests for Phase 4 POST /api/shutdown (token-protected when auth on)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from figuresmith.api.models_routes import create_models_app  # noqa: E402
from figuresmith.api.system_routes import reset_shutdown_state_for_tests  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_shutdown_latch() -> None:
    reset_shutdown_state_for_tests()
    yield
    reset_shutdown_state_for_tests()


def test_shutdown_requires_token_when_auth_on(auth_token_env: str, tmp_path: Path) -> None:
    app = create_models_app(
        app_data_dir=tmp_path / "appdata",
        install_auth=True,
        install_system=True,
    )
    client = TestClient(app)

    denied = client.post("/api/shutdown")
    assert denied.status_code == 401

    with mock.patch("figuresmith.api.system_routes._delayed_exit") as exit_fn:
        # Prevent real process exit; still exercise route + thread start path.
        exit_fn.side_effect = None
        ok = client.post(
            "/api/shutdown",
            headers={"Authorization": f"Bearer {auth_token_env}"},
        )
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True
    assert body["status"] == "shutting_down"


def test_shutdown_allowed_when_auth_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    monkeypatch.delenv("FIGURESMITH_SESSION_TOKEN", raising=False)
    app = create_models_app(
        app_data_dir=tmp_path / "appdata",
        install_auth=True,
        install_system=True,
    )
    client = TestClient(app)

    # Patch os._exit so the delayed thread cannot kill the test runner if it races.
    with mock.patch("figuresmith.api.system_routes.os._exit"):
        with mock.patch("figuresmith.api.system_routes.time.sleep"):
            # Replace delayed exit body by patching Thread to run sync no-op.
            with mock.patch("figuresmith.api.system_routes.threading.Thread") as th:
                th.return_value.start = mock.Mock()
                ok = client.post("/api/shutdown")
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
