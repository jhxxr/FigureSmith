"""Unit tests for strict offline endpoint validation."""

from __future__ import annotations

import pytest

from figuresmith.models.errors import OfflineEndpointForbidden
from figuresmith.security.offline import (
    apply_strict_offline_env,
    is_loopback_host,
    validate_offline_endpoint,
)


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST",
        "127.0.0.1",
        "::1",
        "[::1]",
    ],
)
def test_is_loopback_host_allows(host: str) -> None:
    # Bracket form is normalized inside validate path; is_loopback_host expects bare.
    bare = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    assert is_loopback_host(bare) is True


@pytest.mark.parametrize(
    "host",
    [
        "localhost.example.com",
        "localhost.evil.com",
        "127.0.0.1.example.com",
        "127.0.0.1.nip.io",
        "example.com",
        "192.168.1.1",
        "8.8.8.8",
        "localhostname",
        "notlocalhost",
        "",
        "google.com",
    ],
)
def test_is_loopback_host_denies(host: str) -> None:
    assert is_loopback_host(host) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8765",
        "http://localhost:8000/v1",
        "http://[::1]/8080",
        "https://localhost/v1",
        "127.0.0.1:9000",
    ],
)
def test_validate_offline_endpoint_allows(url: str) -> None:
    validate_offline_endpoint(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost.example.com/v1",
        "https://localhost.evil.com",
        "http://127.0.0.1.example.com",
        "http://127.0.0.1.nip.io/v1",
        "https://api.openai.com/v1",
        "http://192.168.0.5:8080",
        "http://8.8.8.8",
        "https://huggingface.co",
    ],
)
def test_validate_offline_endpoint_denies(url: str) -> None:
    with pytest.raises(OfflineEndpointForbidden) as exc_info:
        validate_offline_endpoint(url)
    assert exc_info.value.code == "OFFLINE_ENDPOINT_FORBIDDEN"


def test_validate_offline_endpoint_empty() -> None:
    with pytest.raises(OfflineEndpointForbidden):
        validate_offline_endpoint("   ")


def test_apply_strict_offline_env_sets_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "NO_PROXY",
        "no_proxy",
        "FIGURESMITH_STRICT_OFFLINE",
        "FIGURESMITH_FORCE_LOCAL_SAM",
    ):
        monkeypatch.delenv(key, raising=False)

    applied = apply_strict_offline_env()
    assert applied["HF_HUB_OFFLINE"] == "1"
    assert applied["TRANSFORMERS_OFFLINE"] == "1"
    assert applied["HF_DATASETS_OFFLINE"] == "1"
    assert "127.0.0.1" in applied["NO_PROXY"]
    assert "localhost" in applied["NO_PROXY"]
    import os

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["FIGURESMITH_STRICT_OFFLINE"] == "1"
