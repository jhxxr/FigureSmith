"""Unit tests for Phase 4 session-token auth middleware."""

from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from figuresmith.api.models_routes import create_models_app  # noqa: E402
from figuresmith.security.auth import (  # noqa: E402
    allows_query_token,
    extract_bearer_token,
    extract_query_token,
    path_requires_auth,
    redact_secrets,
    tokens_match,
)


def test_path_requires_auth_matrix() -> None:
    assert path_requires_auth("/healthz") is False
    assert path_requires_auth("/healthz/") is False
    assert path_requires_auth("/") is False
    assert path_requires_auth("/index.html") is False
    assert path_requires_auth("/figuresmith-bridge.js") is False
    assert path_requires_auth("/api/models") is True
    assert path_requires_auth("/api/models/sam3/import") is True
    assert path_requires_auth("/api/shutdown") is True
    assert path_requires_auth("/api") is True


def test_extract_bearer_token() -> None:
    assert extract_bearer_token(None) is None
    assert extract_bearer_token("") is None
    assert extract_bearer_token("Basic abc") is None
    assert extract_bearer_token("Bearer") is None
    assert extract_bearer_token("Bearer secret-token") == "secret-token"
    assert extract_bearer_token("bearer secret-token") == "secret-token"


def test_tokens_match_constant_time() -> None:
    assert tokens_match("abc", "abc") is True
    assert tokens_match("abc", "abd") is False
    assert tokens_match("abc", None) is False
    # Unequal lengths must not raise (portable across Python builds).
    assert tokens_match("short", "much-longer-token-value") is False


def test_query_token_helpers() -> None:
    assert allows_query_token("/api/events/job-1") is True
    assert allows_query_token("/api/events") is True
    assert allows_query_token("/api/models") is False
    assert extract_query_token("fs_token=abc123") == "abc123"
    assert extract_query_token("token=xyz&other=1") == "xyz"
    assert extract_query_token("foo=bar") is None


def test_redact_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_SESSION_TOKEN", "super-secret-token-value")
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "0")
    text = "header Bearer super-secret-token-value trailing"
    redacted = redact_secrets(text)
    assert "super-secret-token-value" not in redacted
    assert "[REDACTED_SESSION_TOKEN]" in redacted


def test_api_requires_token_when_enabled(auth_token_env: str, tmp_path: Path) -> None:
    app = create_models_app(app_data_dir=tmp_path / "appdata", install_auth=True)
    client = TestClient(app)

    # healthz public
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # API without token → 401
    r401 = client.get("/api/models")
    assert r401.status_code == 401
    detail = r401.json()["detail"]
    assert detail["code"] == "UNAUTHORIZED"

    # Wrong token → 401
    bad = client.get(
        "/api/models",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert bad.status_code == 401

    # Correct token → 200
    ok = client.get(
        "/api/models",
        headers={"Authorization": f"Bearer {auth_token_env}"},
    )
    assert ok.status_code == 200
    assert "models" in ok.json()


def test_disable_auth_bypass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FIGURESMITH_SESSION_TOKEN", "still-set-but-bypassed")
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "1")
    app = create_models_app(app_data_dir=tmp_path / "appdata", install_auth=True)
    client = TestClient(app)
    r = client.get("/api/models")
    assert r.status_code == 200


def test_no_token_means_auth_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FIGURESMITH_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "0")
    app = create_models_app(app_data_dir=tmp_path / "appdata", install_auth=True)
    client = TestClient(app)
    r = client.get("/api/models")
    assert r.status_code == 200


def test_events_path_accepts_query_token(auth_token_env: str) -> None:
    """EventSource cannot send Authorization; scoped query token is allowed."""
    from fastapi import FastAPI

    from figuresmith.security.auth import install_auth_middleware

    app = FastAPI()
    install_auth_middleware(app)

    @app.get("/api/events/{job_id}")
    def events(job_id: str) -> dict:
        return {"job_id": job_id, "ok": True}

    @app.get("/api/models")
    def models() -> dict:
        return {"models": []}

    client = TestClient(app)

    denied = client.get("/api/events/j1")
    assert denied.status_code == 401

    ok = client.get(f"/api/events/j1?fs_token={auth_token_env}")
    assert ok.status_code == 200
    assert ok.json()["job_id"] == "j1"

    # Query token must not open non-events API routes.
    still_denied = client.get(f"/api/models?fs_token={auth_token_env}")
    assert still_denied.status_code == 401
