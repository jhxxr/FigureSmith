"""Local model loading and path management (Phase 2)."""

from figuresmith.models.errors import (
    FigureSmithError,
    OfflineEndpointForbidden,
    PathTraversalRejected,
    RemoteSamDisabled,
    RmbgModelInvalid,
    RmbgModelMissing,
    Sam3ModelInvalid,
    Sam3ModelMissing,
)
from figuresmith.models.registry import ModelPaths, resolve_model_paths

# Loader helpers are importable from their modules directly to avoid circular
# imports with figuresmith.security.offline (offline -> errors -> models package).

__all__ = [
    "FigureSmithError",
    "ModelPaths",
    "OfflineEndpointForbidden",
    "PathTraversalRejected",
    "RemoteSamDisabled",
    "RmbgModelInvalid",
    "RmbgModelMissing",
    "Sam3ModelInvalid",
    "Sam3ModelMissing",
    "resolve_model_paths",
]
