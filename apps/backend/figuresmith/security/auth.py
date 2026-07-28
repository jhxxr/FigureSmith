"""Session token Bearer authentication for desktop sidecar mode.

Policy (Phase 4):
- When ``FIGURESMITH_SESSION_TOKEN`` is set and ``FIGURESMITH_DISABLE_AUTH`` is not
  truthy, all ``/api/*`` routes require ``Authorization: Bearer <token>``.
- ``/healthz`` stays public (process-alive probe).
- Static UI and non-API paths stay public so the WebView can load vendor pages.
- ``/api/events/*`` may also accept ``fs_token`` / ``token`` query params because
  browser ``EventSource`` cannot set Authorization headers (desktop bridge only).
- Token lives only in process env / memory — never write it to disk or logs.

Test / browser-dev bypass: ``FIGURESMITH_DISABLE_AUTH=1``.
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from figuresmith.security.offline import env_flag_true

SESSION_TOKEN_ENV = "FIGURESMITH_SESSION_TOKEN"
DISABLE_AUTH_ENV = "FIGURESMITH_DISABLE_AUTH"

# Paths that never require a Bearer token even when auth is enabled.
PUBLIC_EXACT_PATHS = frozenset(
    {
        "/healthz",
    }
)


def get_session_token() -> Optional[str]:
    """Return the configured session token, or None if unset/blank."""
    raw = os.environ.get(SESSION_TOKEN_ENV)
    if raw is None:
        return None
    token = raw.strip()
    return token or None


def is_auth_disabled() -> bool:
    """Return True when tests/legacy browser dev bypass auth."""
    return env_flag_true(DISABLE_AUTH_ENV, default=False)


def is_auth_enabled() -> bool:
    """Auth is active only when a token is present and disable flag is off."""
    if is_auth_disabled():
        return False
    return get_session_token() is not None


def redact_secrets(text: str) -> str:
    """Replace any live session token occurrences in ``text`` before logging."""
    if not text:
        return text
    token = get_session_token()
    if not token:
        return text
    if token in text:
        return text.replace(token, "[REDACTED_SESSION_TOKEN]")
    return text


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Parse ``Authorization: Bearer <token>`` (case-insensitive scheme)."""
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, value = parts[0], parts[1].strip()
    if scheme.lower() != "bearer" or not value:
        return None
    return value


def extract_query_token(query_string: str) -> Optional[str]:
    """Extract session token from query for EventSource-compatible paths only.

    Browser ``EventSource`` cannot set ``Authorization`` headers. The desktop
    bridge may append ``fs_token`` / ``token`` on ``/api/events/*`` only.
    """
    if not query_string:
        return None
    from urllib.parse import parse_qs

    # Handle raw query with or without leading '?'.
    raw = query_string[1:] if query_string.startswith("?") else query_string
    params = parse_qs(raw, keep_blank_values=False)
    for key in ("fs_token", "token"):
        values = params.get(key) or []
        if values and values[0].strip():
            return values[0].strip()
    return None


def allows_query_token(path: str) -> bool:
    """Return True if this path may authenticate via query token (SSE only)."""
    if not path:
        return False
    normalized = path if path == "/" else path.rstrip("/") or "/"
    return normalized == "/api/events" or normalized.startswith("/api/events/")


def path_requires_auth(path: str) -> bool:
    """Return True if the request path must present a Bearer token when auth is on."""
    if not path:
        return False
    # Normalize trailing slash for exact public matches only.
    normalized = path if path == "/" else path.rstrip("/") or "/"
    if normalized in PUBLIC_EXACT_PATHS:
        return False
    # Protect the API surface only (static UI remains public).
    return normalized == "/api" or normalized.startswith("/api/")


def tokens_match(expected: str, provided: Optional[str]) -> bool:
    """Constant-time compare of expected vs provided bearer tokens.

    Unequal lengths are treated as non-matching without raising (some Python
    builds raise ``ValueError`` from ``hmac.compare_digest`` on length mismatch).
    """
    if provided is None:
        return False
    exp = expected.encode("utf-8")
    got = provided.encode("utf-8")
    if len(exp) != len(got):
        # Still perform a dummy compare to keep timing closer across paths.
        hmac.compare_digest(exp, exp)
        return False
    return hmac.compare_digest(exp, got)


def unauthorized_response(detail: str = "Unauthorized") -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "detail": {
                "code": "UNAUTHORIZED",
                "message": detail,
                "message_zh": "未授权：需要有效的会话令牌",
            }
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


class SessionTokenMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated ``/api/*`` calls when a session token is configured."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not is_auth_enabled():
            return await call_next(request)

        path = request.url.path or "/"
        if not path_requires_auth(path):
            return await call_next(request)

        expected = get_session_token()
        # Defensive: is_auth_enabled already requires a token.
        if expected is None:
            return await call_next(request)

        provided = extract_bearer_token(request.headers.get("authorization"))
        if provided is None and allows_query_token(path):
            # EventSource cannot send Authorization; allow scoped query token.
            provided = extract_query_token(request.url.query or "")

        if not tokens_match(expected, provided):
            return unauthorized_response(
                "Missing or invalid Bearer session token"
            )

        return await call_next(request)


def install_auth_middleware(app) -> bool:
    """Attach :class:`SessionTokenMiddleware` to a FastAPI/Starlette app.

    The middleware is always installed; it no-ops when auth is disabled or no
    token is set. Returns whether auth is currently enabled.
    """
    # Avoid double-install when reload/import runs twice.
    existing = getattr(app, "user_middleware", None) or []
    for entry in existing:
        cls = getattr(entry, "cls", None)
        if cls is SessionTokenMiddleware:
            return is_auth_enabled()
    # Also check middleware_stack already built (rare for TestClient).
    app.add_middleware(SessionTokenMiddleware)
    return is_auth_enabled()
