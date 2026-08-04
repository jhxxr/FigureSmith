"""Strict offline helpers: env flags and endpoint host validation."""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Iterable, Optional
from urllib.parse import urlparse

# NOTE: Do not import figuresmith.models at module top-level.
# models.manifest → security.offline, and models/__init__ pulls manager →
# a top-level models import here creates an order-dependent circular import
# when auth is loaded first (figuresmith.security.auth → offline → models).

# Environment keys set when strict offline is active.
OFFLINE_ENV_KEYS = (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
)

STRICT_OFFLINE_ENV = "FIGURESMITH_STRICT_OFFLINE"
FORCE_LOCAL_SAM_ENV = "FIGURESMITH_FORCE_LOCAL_SAM"

_LOOPBACK_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.",
        "ip6-localhost",
        "ip6-loopback",
    }
)


def env_flag_true(name: str, default: bool = False) -> bool:
    """Parse common truthy environment flag values."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_strict_offline_enabled(
    strict_offline: Optional[bool] = None,
    *,
    default: bool = False,
) -> bool:
    """Return whether strict offline mode is active.

    Fail-closed on env: a truthy ``FIGURESMITH_STRICT_OFFLINE`` always enables
    strict mode. Explicit ``True`` also enables. Explicit ``False`` only wins when
    the env flag is unset/false (developer opt-out should set the env to ``0``).
    """
    if env_flag_true(STRICT_OFFLINE_ENV, default=False):
        return True
    if strict_offline is not None:
        return bool(strict_offline)
    return bool(default)


def apply_strict_offline_env(
    *,
    overwrite: bool = True,
    extra_no_proxy: Optional[Iterable[str]] = None,
) -> dict[str, str]:
    """Set Hugging Face / transformers offline flags and NO_PROXY for loopback.

    Returns the dict of values applied (for logging/tests).
    """
    applied: dict[str, str] = {}
    for key in OFFLINE_ENV_KEYS:
        if overwrite or key not in os.environ:
            os.environ[key] = "1"
            applied[key] = "1"

    no_proxy_parts = ["127.0.0.1", "localhost", "::1"]
    if extra_no_proxy:
        no_proxy_parts.extend(str(p).strip() for p in extra_no_proxy if str(p).strip())

    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    merged: list[str] = []
    seen: set[str] = set()
    for part in [*no_proxy_parts, *[p.strip() for p in existing.split(",") if p.strip()]]:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(part)
    no_proxy_value = ",".join(merged)
    os.environ["NO_PROXY"] = no_proxy_value
    os.environ["no_proxy"] = no_proxy_value
    applied["NO_PROXY"] = no_proxy_value

    # Mark FigureSmith strict flag so vendor code and child processes see it.
    if overwrite or STRICT_OFFLINE_ENV not in os.environ:
        os.environ[STRICT_OFFLINE_ENV] = "1"
        applied[STRICT_OFFLINE_ENV] = "1"
    if overwrite or FORCE_LOCAL_SAM_ENV not in os.environ:
        os.environ[FORCE_LOCAL_SAM_ENV] = "1"
        applied[FORCE_LOCAL_SAM_ENV] = "1"

    return applied


def _normalize_hostname(host: str) -> str:
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    # Strip trailing dot used by FQDN forms of localhost.
    if h.endswith(".") and h.count(".") == 1:
        h = h[:-1]
    return h


def _is_ip_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_loopback_host(host: str, *, resolve_dns: bool = False) -> bool:
    """Return True only for true loopback hostnames/IPs.

    Rejects prefix/suffix tricks such as ``localhost.example.com`` or
    ``127.0.0.1.example.com`` by requiring an exact hostname match or a
    parseable loopback IP literal. Optional DNS resolution is disabled by
    default so unit tests and offline runs do not depend on the network.
    """
    if not host or not str(host).strip():
        return False

    normalized = _normalize_hostname(str(host))
    if not normalized:
        return False

    if _is_ip_loopback(normalized):
        return True

    if normalized in _LOOPBACK_HOSTNAMES:
        return True

    # Bare "localhost" variants only — never startswith/endswith tricks.
    if normalized == "localhost":
        return True

    if not resolve_dns:
        return False

    # Optional: resolve and require *all* addresses to be loopback.
    try:
        infos = socket.getaddrinfo(normalized, None)
    except (socket.gaierror, OSError):
        return False
    if not infos:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            return False
        addr = sockaddr[0]
        if not _is_ip_loopback(addr):
            return False
    return True


def validate_offline_endpoint(base_url: str, *, resolve_dns: bool = False) -> None:
    """Validate a configured HTTP(S) endpoint.

    Endpoint validation no longer imposes a loopback-only policy. Strict offline
    controls local model downloads, while an explicitly configured API may be
    remote. Credentials in URLs and malformed endpoints remain forbidden.
    """
    # Lazy import avoids circular dependency with figuresmith.models package init.
    from figuresmith.models.errors import OfflineEndpointForbidden

    if base_url is None or not str(base_url).strip():
        raise OfflineEndpointForbidden(detail="empty base_url")

    raw = str(base_url).strip()
    if raw.count("://") > 1:
        raise OfflineEndpointForbidden(detail="endpoint contains a duplicated URL scheme")
    # Allow bare host:port by giving urlparse a scheme when missing.
    to_parse = raw if "://" in raw else f"http://{raw}"
    parsed = urlparse(to_parse)
    if parsed.scheme not in {"http", "https"}:
        raise OfflineEndpointForbidden(
            detail=f"scheme={parsed.scheme!r} is not an HTTP(S) endpoint"
        )
    if parsed.username or parsed.password:
        raise OfflineEndpointForbidden(detail="endpoint credentials are not allowed")
    host = parsed.hostname
    if not host:
        raise OfflineEndpointForbidden(
            detail=f"could not parse hostname from base_url={base_url!r}"
        )

    # Remote endpoints are allowed when explicitly configured. The strict
    # offline flag must not turn a valid API binding into a loopback-only URL.
    return


def validate_effective_offline_policy(
    *,
    provider: str,
    base_url: str,
    image_provider: str,
    image_base_url: str,
) -> None:
    """Validate effective configured API endpoints before a client is built.

    Provider names are no longer restricted to the former preset list; a
    binding may target any valid HTTP(S) endpoint.
    """
    from figuresmith.models.errors import OfflineEndpointForbidden

    validate_offline_endpoint(base_url)
    validate_offline_endpoint(image_base_url)


def validate_offline_asset_url(url: str) -> None:
    """Allow local data images or loopback HTTP assets, rejecting remote URLs."""
    from figuresmith.models.errors import OfflineEndpointForbidden

    raw = str(url or "").strip()
    if raw.lower().startswith("data:image/"):
        return
    validate_offline_endpoint(raw)
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    if not parsed.hostname or not is_loopback_host(parsed.hostname):
        raise OfflineEndpointForbidden(
            detail=f"remote asset URL is not allowed in strict offline mode: {url!r}"
        )
