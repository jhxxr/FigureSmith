"""Launcher / runtime environment helpers for FigureSmith."""

from __future__ import annotations

import os
from typing import Optional

from figuresmith.models.registry import ModelPaths, export_path_env, resolve_model_paths
from figuresmith.security.offline import (
    STRICT_OFFLINE_ENV,
    apply_strict_offline_env,
    env_flag_true,
    is_strict_offline_enabled,
)


def prepare_figuresmith_runtime(
    *,
    strict_offline: Optional[bool] = None,
    default_strict: bool = True,
    apply_env: bool = True,
) -> dict[str, str]:
    """Prepare process environment for FigureSmith desktop/local launches.

    By default enables strict offline (``FIGURESMITH_STRICT_OFFLINE=1``) and
    applies HF offline flags before heavy ML stacks are imported.

    Explicit ``strict_offline=False`` (``--no-strict-offline``) clears the env
    flag first so developer opt-out is effective against fail-closed env reads.
    """
    applied: dict[str, str] = {}

    # Developer opt-out must clear env before fail-closed env reads.
    if strict_offline is False:
        os.environ[STRICT_OFFLINE_ENV] = "0"
        applied[STRICT_OFFLINE_ENV] = "0"
        enabled = False
    else:
        enabled = is_strict_offline_enabled(strict_offline, default=default_strict)

    if enabled:
        if apply_env:
            applied.update(apply_strict_offline_env(overwrite=True))
        else:
            os.environ.setdefault(STRICT_OFFLINE_ENV, "1")
            applied[STRICT_OFFLINE_ENV] = os.environ[STRICT_OFFLINE_ENV]

    # Inject resolved model paths into env for vendor subprocesses if unset.
    paths = resolve_model_paths(use_defaults=True)
    for key, value in export_path_env(paths).items():
        if key not in os.environ or not os.environ[key].strip():
            os.environ[key] = value
            applied[key] = value

    return applied


def child_process_env(
    base: Optional[dict[str, str]] = None,
    *,
    strict_offline: Optional[bool] = None,
    model_paths: Optional[ModelPaths] = None,
) -> dict[str, str]:
    """Build an env mapping suitable for ``subprocess.Popen``."""
    env = dict(base if base is not None else os.environ)

    # Explicit opt-out wins for the child mapping (does not require mutating os.environ).
    if strict_offline is False:
        enabled = False
        env[STRICT_OFFLINE_ENV] = "0"
    else:
        # Prefer flags already present on the child env mapping, then process env.
        raw = env.get(STRICT_OFFLINE_ENV)
        if raw is not None and str(raw).strip().lower() in {"1", "true", "yes", "on"}:
            enabled = True
        elif raw is not None and str(raw).strip().lower() in {"0", "false", "no", "off"}:
            enabled = bool(strict_offline) if strict_offline is not None else False
        else:
            enabled = is_strict_offline_enabled(
                strict_offline,
                default=env_flag_true(STRICT_OFFLINE_ENV, default=True),
            )

    if enabled:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        env["HF_DATASETS_OFFLINE"] = "1"
        env[STRICT_OFFLINE_ENV] = "1"
        env["FIGURESMITH_FORCE_LOCAL_SAM"] = "1"
        existing = env.get("NO_PROXY") or env.get("no_proxy") or ""
        parts = ["127.0.0.1", "localhost", "::1"]
        parts.extend(p.strip() for p in existing.split(",") if p.strip())
        # de-dupe preserving order
        seen: set[str] = set()
        merged: list[str] = []
        for p in parts:
            k = p.lower()
            if k in seen:
                continue
            seen.add(k)
            merged.append(p)
        env["NO_PROXY"] = ",".join(merged)
        env["no_proxy"] = env["NO_PROXY"]

    paths = model_paths if model_paths is not None else resolve_model_paths(use_defaults=True)
    env.update(export_path_env(paths))
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env
