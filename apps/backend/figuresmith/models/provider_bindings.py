"""Persistent named API bindings with secrets kept in the OS credential store."""
from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urlparse

from figuresmith.models.settings_io import atomic_write_json, read_settings

_SECRET_SERVICE = "FigureSmith"
_NAME_RE = re.compile(r"^[^\\x00-\\x1f\\x7f]{1,120}$")


def normalize_binding_base_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("base_url is required")
    if raw.count("://") > 1:
        raise ValueError("base_url contains a duplicated URL")
    candidate = raw if "://" in raw else f"https://{raw}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base_url must be a valid HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not contain credentials")
    if "://" in parsed.path:
        raise ValueError("base_url contains a duplicated URL")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def _keyring():
    try:
        import keyring  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OS credential storage is unavailable; install keyring") from exc
    return keyring


def _secret_ref(binding_id: str) -> str:
    return f"provider:{binding_id}"


def _bindings(settings_path) -> list[dict[str, Any]]:
    data = read_settings(settings_path)
    values = data.get("provider_bindings")
    return [dict(v) for v in values if isinstance(v, dict) and v.get("id")] if isinstance(values, list) else []


def list_bindings(settings_path) -> list[dict[str, Any]]:
    return [{k: v for k, v in item.items() if k != "secret_ref"} for item in _bindings(settings_path)]


def save_binding(settings_path, *, binding_id: str | None, name: str, base_url: str,
                 text_model: str, image_model: str, api_key: str | None) -> dict[str, Any]:
    if not _NAME_RE.match(name.strip()):
        raise ValueError("binding name is required")
    canonical = normalize_binding_base_url(base_url)
    values = _bindings(settings_path)
    current = next((v for v in values if v["id"] == binding_id), None) if binding_id else None
    item_id = binding_id or uuid.uuid4().hex
    ref = _secret_ref(item_id)
    item = {"id": item_id, "name": name.strip(), "base_url": canonical,
            "text_model": text_model.strip(), "image_model": image_model.strip(), "secret_ref": ref}
    if current:
        values[values.index(current)] = item
    else:
        values.append(item)
    data = read_settings(settings_path)
    data["provider_bindings"] = values
    atomic_write_json(settings_path, data)
    if api_key is not None and api_key.strip():
        _keyring().set_password(_SECRET_SERVICE, ref, api_key)
    result = dict(item)
    result.pop("secret_ref", None)
    return result


def delete_binding(settings_path, binding_id: str) -> None:
    values = _bindings(settings_path)
    kept = [v for v in values if v["id"] != binding_id]
    data = read_settings(settings_path)
    data["provider_bindings"] = kept
    atomic_write_json(settings_path, data)
    try:
        _keyring().delete_password(_SECRET_SERVICE, _secret_ref(binding_id))
    except Exception:
        pass


def resolve_binding(settings_path, binding_id: str, *, require_secret: bool = True) -> dict[str, Any]:
    item = next((v for v in _bindings(settings_path) if v["id"] == binding_id), None)
    if not item:
        raise KeyError(f"unknown provider binding: {binding_id}")
    result = dict(item)
    ref = result.pop("secret_ref", _secret_ref(binding_id))
    try:
        result["api_key"] = _keyring().get_password(_SECRET_SERVICE, ref)
    except RuntimeError:
        result["api_key"] = None
    if require_secret and not result.get("api_key"):
        raise ValueError(f"API key is unavailable for binding {item.get('name', binding_id)!r}")
    return result
