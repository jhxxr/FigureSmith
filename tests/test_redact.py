"""Unit tests for figuresmith.security.redact helpers."""

from __future__ import annotations

from figuresmith.security.redact import (
    redact_home_paths,
    redact_log_line,
    redact_mapping,
    redact_secrets_text,
)


def test_redact_secrets_text_masks_bearer_and_sk() -> None:
    text = "Authorization: Bearer super-secret-token-value sk-abcdefghijklmnop"
    out = redact_secrets_text(text)
    assert "super-secret-token-value" not in out
    assert "sk-abcdefghijklmnop" not in out
    assert "[REDACTED]" in out


def test_redact_secrets_text_masks_api_key_assignment() -> None:
    text = 'api_key=my-secret-key-123 and "api-key": "another-secret"'
    out = redact_secrets_text(text)
    assert "my-secret-key-123" not in out
    assert "another-secret" not in out


def test_redact_home_paths() -> None:
    home = "C:\\Users\\alice"
    text = f"wrote {home}\\AppData\\FigureSmith\\models\\sam3.pt"
    out = redact_home_paths(text, home=home)
    assert "alice" not in out
    assert "[HOME]" in out


def test_redact_log_line_combines() -> None:
    home = "/home/bob"
    text = f"Authorization: Bearer tok123 path={home}/secret"
    out = redact_log_line(text, extra_secrets=["tok123"], home=home)
    assert "tok123" not in out
    assert "[REDACTED]" in out
    assert home not in out
    assert "[HOME]" in out


def test_redact_mapping() -> None:
    data = {
        "api_key": "secret-key",
        "message": "ok",
        "sam_api_key": "sam-secret",
        "count": 3,
    }
    out = redact_mapping(data)
    assert out["api_key"] == "[REDACTED]"
    assert out["sam_api_key"] == "[REDACTED]"
    assert out["message"] == "ok"
    assert out["count"] == 3
