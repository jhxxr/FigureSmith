"""HTTP API surface for FigureSmith.

Phase 3 exposes local model manager routes under ``figuresmith.api.models_routes``.
The vendor FastAPI app remains the primary server; FigureSmith mounts its router
from ``apps/backend/main.py``.
"""

from figuresmith.api.models_routes import create_models_app, mount_models_routes, router

__all__ = ["create_models_app", "mount_models_routes", "router"]
