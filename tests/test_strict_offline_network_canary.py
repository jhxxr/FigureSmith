"""Transport-level canaries for the strict-offline vendor boundary.

The full vendor module depends on optional ML packages that are not required by
the backend test environment. These tests load only its policy-bearing module
with lightweight import stubs, then prove the guard runs before a transport
client or socket can be reached.
"""

from __future__ import annotations

import importlib.util
import socket
import sys
import types
from pathlib import Path

import pytest

from figuresmith.models.errors import OfflineEndpointForbidden


REPO = Path(__file__).resolve().parents[1]


def _load_policy_module(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[types.ModuleType, types.ModuleType]:
    """Load autofigure2 with optional ML imports replaced by inert modules."""
    requests_mod = types.ModuleType("requests")
    requests_mod.get = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    requests_mod.post = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    requests_mod.exceptions = types.SimpleNamespace(RequestException=Exception)

    stubs: dict[str, types.ModuleType] = {
        "requests": requests_mod,
        "numpy": types.ModuleType("numpy"),
        "torch": types.ModuleType("torch"),
        "PIL": types.ModuleType("PIL"),
        "torchvision": types.ModuleType("torchvision"),
        "transformers": types.ModuleType("transformers"),
    }
    stubs["PIL"].Image = types.SimpleNamespace()  # type: ignore[attr-defined]
    stubs["PIL"].ImageDraw = types.SimpleNamespace()  # type: ignore[attr-defined]
    stubs["PIL"].ImageFont = types.SimpleNamespace()  # type: ignore[attr-defined]
    stubs["PIL"].ImageOps = types.SimpleNamespace()  # type: ignore[attr-defined]
    stubs["torchvision"].transforms = types.SimpleNamespace()  # type: ignore[attr-defined]
    stubs["transformers"].AutoModelForImageSegmentation = object  # type: ignore[attr-defined]
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    module_name = "figuresmith_autofigure_network_canary"
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO / "vendor" / "autofigure_edit" / "autofigure2.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load vendor policy module")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module, requests_mod


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("strict-offline canary reached a network transport")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def test_default_provider_is_rejected_before_socket_or_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    _block_network(monkeypatch)
    module, requests_mod = _load_policy_module(monkeypatch)
    monkeypatch.setattr(requests_mod, "get", lambda *args, **kwargs: pytest.fail("HTTP GET reached"))
    monkeypatch.setattr(requests_mod, "post", lambda *args, **kwargs: pytest.fail("HTTP POST reached"))

    # Omitted URLs resolve to the public bianxie defaults inside method_to_svg.
    # The effective policy must reject them before API keys, files, or clients
    # are touched.
    with pytest.raises(OfflineEndpointForbidden):
        module.method_to_svg(
            method_text="a local scientific figure",
            provider="bianxie",
            strict_offline=True,
        )


def test_remote_provider_asset_is_rejected_before_http_get(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    _block_network(monkeypatch)
    module, requests_mod = _load_policy_module(monkeypatch)
    monkeypatch.setattr(requests_mod, "get", lambda *args, **kwargs: pytest.fail("remote asset GET reached"))

    with pytest.raises(OfflineEndpointForbidden):
        module._figuresmith_get_asset("https://assets.example.invalid/icon.png", timeout=1)


def test_loopback_asset_redirect_is_not_followed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGURESMITH_STRICT_OFFLINE", "1")
    _block_network(monkeypatch)
    module, requests_mod = _load_policy_module(monkeypatch)
    calls: list[dict[str, object]] = []

    class Redirect:
        status_code = 302

    def get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return Redirect()

    monkeypatch.setattr(requests_mod, "get", get)
    with pytest.raises(RuntimeError, match="OFFLINE_REDIRECT_FORBIDDEN"):
        module._figuresmith_get_asset("http://127.0.0.1:8765/icon.png", timeout=1)
    assert calls == [
        {
            "url": "http://127.0.0.1:8765/icon.png",
            "timeout": 1,
            "allow_redirects": False,
        }
    ]
