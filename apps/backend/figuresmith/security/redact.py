"""Log and message redaction helpers for FigureSmith UI / streaming paths.

Masks common secret patterns (API keys, Bearer tokens, sk- keys) and shortens
home-directory paths so job logs and error surfaces are safer to display.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

# Authorization: Bearer <token>
_BEARER_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s\"']+)",
)
# api_key / api-key / apikey JSON or form-like assignments
_API_KEY_ASSIGN_RE = re.compile(
    r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|secret[_-]?key)["\']?\s*[:=]\s*["\']?)([^\s"\']+)',
)
# OpenAI-style sk- keys and similar long opaque tokens
_SK_KEY_RE = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,})\b")
# fal / roboflow-ish long tokens sometimes appear bare
_LONG_HEX_TOKEN_RE = re.compile(r"\b([a-f0-9]{32,})\b", re.IGNORECASE)

_REDACTED = "[REDACTED]"
_REDACTED_PATH = "[HOME]"


def _home_prefixes() -> list[str]:
    """Return unique home directory string prefixes to shorten in logs."""
    prefixes: list[str] = []
    try:
        home = str(Path.home())
        if home:
            prefixes.append(home)
            # Windows users often see mixed separators in logs.
            prefixes.append(home.replace("\\", "/"))
            prefixes.append(home.replace("/", "\\"))
    except Exception:
        pass
    for key in ("USERPROFILE", "HOME"):
        raw = os.environ.get(key)
        if raw and raw not in prefixes:
            prefixes.append(raw)
            prefixes.append(raw.replace("\\", "/"))
            prefixes.append(raw.replace("/", "\\"))
    # Longest first so nested replacements are stable.
    return sorted(set(p for p in prefixes if p), key=len, reverse=True)


def redact_home_paths(text: str, *, home: Optional[str] = None) -> str:
    """Replace home directory prefixes with a short placeholder."""
    if not text:
        return text
    if home:
        candidates = [home, home.replace("\\", "/"), home.replace("/", "\\")]
    else:
        candidates = _home_prefixes()
    out = text
    for prefix in candidates:
        if prefix and prefix in out:
            out = out.replace(prefix, _REDACTED_PATH)
    return out


def redact_secrets_text(text: str, *, extra_secrets: Optional[list[str]] = None) -> str:
    """Mask API keys, bearer tokens, and sk- style secrets in free-form text."""
    if not text:
        return text

    out = text
    if extra_secrets:
        for secret in extra_secrets:
            if secret and secret in out:
                out = out.replace(secret, _REDACTED)

    out = _BEARER_RE.sub(r"\1" + _REDACTED, out)
    out = _API_KEY_ASSIGN_RE.sub(r"\1" + _REDACTED, out)
    out = _SK_KEY_RE.sub(_REDACTED, out)

    # Also reuse session-token redaction when auth module is available.
    try:
        from figuresmith.security.auth import redact_secrets as redact_session

        out = redact_session(out)
    except Exception:
        pass

    return out


def redact_log_line(
    text: str,
    *,
    extra_secrets: Optional[list[str]] = None,
    home: Optional[str] = None,
) -> str:
    """Full log-line redaction: secrets + home path shortening."""
    if not text:
        return text
    return redact_home_paths(
        redact_secrets_text(text, extra_secrets=extra_secrets),
        home=home,
    )


def redact_mapping(data: dict, *, keys: Optional[set[str]] = None) -> dict:
    """Return a shallow copy with sensitive keys masked.

    Default sensitive keys: api_key, sam_api_key, authorization, token, password.
    """
    sensitive = keys or {
        "api_key",
        "sam_api_key",
        "image_api_key",
        "authorization",
        "token",
        "access_token",
        "password",
        "secret",
        "session_token",
    }
    out: dict = {}
    for key, value in data.items():
        key_l = str(key).lower()
        if key_l in sensitive or any(s in key_l for s in ("api_key", "token", "secret", "password")):
            out[key] = _REDACTED if value not in (None, "") else value
        elif isinstance(value, str):
            out[key] = redact_log_line(value)
        else:
            out[key] = value
    return out


__all__ = [
    "redact_home_paths",
    "redact_log_line",
    "redact_mapping",
    "redact_secrets_text",
]
