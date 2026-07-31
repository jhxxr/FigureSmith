"""Security helpers for FigureSmith."""

from figuresmith.security.auth import (
    SessionTokenMiddleware,
    extract_query_token,
    get_sse_ticket,
    get_session_token,
    install_auth_middleware,
    is_auth_disabled,
    is_auth_enabled,
    redact_secrets,
    sse_ticket_is_valid,
)
from figuresmith.security.offline import (
    apply_strict_offline_env,
    is_loopback_host,
    is_strict_offline_enabled,
    validate_effective_offline_policy,
    validate_offline_asset_url,
    validate_offline_endpoint,
)
from figuresmith.security.redact import (
    redact_home_paths,
    redact_log_line,
    redact_mapping,
    redact_secrets_text,
)
from figuresmith.security.svg import SanitizedSvg, SvgLimits, sanitize_svg

__all__ = [
    "SessionTokenMiddleware",
    "apply_strict_offline_env",
    "extract_query_token",
    "get_sse_ticket",
    "get_session_token",
    "install_auth_middleware",
    "is_auth_disabled",
    "is_auth_enabled",
    "is_loopback_host",
    "is_strict_offline_enabled",
    "redact_home_paths",
    "redact_log_line",
    "redact_mapping",
    "redact_secrets",
    "sse_ticket_is_valid",
    "redact_secrets_text",
    "SanitizedSvg",
    "SvgLimits",
    "sanitize_svg",
    "validate_offline_endpoint",
    "validate_effective_offline_policy",
    "validate_offline_asset_url",
]
