"""Local model loading, path management, and Phase 3 import/lifecycle APIs."""

from figuresmith.models.errors import (
    FigureSmithError,
    ModelDeleteError,
    ModelImportError,
    ModelImportInvalidSource,
    ModelImportPinMismatch,
    ModelImportSizeError,
    ModelImportZipSlip,
    ModelNotInstalled,
    OfflineEndpointForbidden,
    PathTraversalRejected,
    RemoteSamDisabled,
    RmbgModelInvalid,
    RmbgModelMissing,
    Sam3ModelInvalid,
    Sam3ModelMissing,
)
from figuresmith.models.manager import ModelManager, default_manager
from figuresmith.models.registry import ModelPaths, resolve_model_paths

# Loader helpers remain importable from their modules directly to avoid circular
# imports with figuresmith.security.offline (offline -> errors -> models package).

__all__ = [
    "FigureSmithError",
    "ModelDeleteError",
    "ModelImportError",
    "ModelImportInvalidSource",
    "ModelImportPinMismatch",
    "ModelImportSizeError",
    "ModelImportZipSlip",
    "ModelManager",
    "ModelNotInstalled",
    "ModelPaths",
    "OfflineEndpointForbidden",
    "PathTraversalRejected",
    "RemoteSamDisabled",
    "RmbgModelInvalid",
    "RmbgModelMissing",
    "Sam3ModelInvalid",
    "Sam3ModelMissing",
    "default_manager",
    "resolve_model_paths",
]
