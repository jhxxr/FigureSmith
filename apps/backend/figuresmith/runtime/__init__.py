"""Runtime pack discovery and offline environment helpers.

The manifest and lock validators are intentionally importable by packaging
tools that do not install the backend's ML/web dependencies.  Environment
helpers therefore stay lazy: importing ``figuresmith.runtime.manifest`` must
not pull in FastAPI, Starlette, or model registries.
"""
from figuresmith.runtime.locks import (
    RuntimeLockError,
    validate_lock_bundle,
    validate_requirements_lock,
    validate_sources_lock,
    validate_wheelhouse_manifest,
    verify_wheelhouse_files,
)
from figuresmith.runtime.manifest import (
    RuntimeManifestError,
    build_runtime_manifest,
    verify_runtime_manifest,
    write_runtime_manifest,
)

__all__ = [
    "child_process_env",
    "prepare_figuresmith_runtime",
    "RuntimeLockError",
    "validate_lock_bundle",
    "validate_requirements_lock",
    "validate_sources_lock",
    "validate_wheelhouse_manifest",
    "verify_wheelhouse_files",
    "RuntimeManifestError",
    "build_runtime_manifest",
    "verify_runtime_manifest",
    "write_runtime_manifest",
]


def __getattr__(name: str):
    """Load process-environment helpers only when a caller requests them."""
    if name in {"child_process_env", "prepare_figuresmith_runtime"}:
        from figuresmith.runtime import env

        value = getattr(env, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
