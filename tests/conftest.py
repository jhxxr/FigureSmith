"""Shared pytest fixtures for FigureSmith.

Phase 4: disable session-token auth by default so Phase 2/3 TestClient suites
remain green. Auth-specific tests override this explicitly.
"""

from __future__ import annotations

import os

import pytest

# Apply early so modules that read env at import time see the bypass.
os.environ.setdefault("FIGURESMITH_DISABLE_AUTH", "1")


@pytest.fixture
def auth_token_env(monkeypatch: pytest.MonkeyPatch):
    """Enable Bearer auth and a valid scoped SSE ticket for tests."""
    import time

    token = "test-session-token-figuresmith-phase4"
    ticket = "test-sse-ticket-figuresmith"
    monkeypatch.delenv("FIGURESMITH_DISABLE_AUTH", raising=False)
    monkeypatch.setenv("FIGURESMITH_SESSION_TOKEN", token)
    monkeypatch.setenv("FIGURESMITH_SSE_TICKET", ticket)
    monkeypatch.setenv("FIGURESMITH_SSE_TICKET_EXPIRES_AT", str(time.time() + 300))
    monkeypatch.setenv("FIGURESMITH_DISABLE_AUTH", "0")
    return token
