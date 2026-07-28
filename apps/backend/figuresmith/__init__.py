"""FigureSmith backend package (图匠).

Phase 3 adds safe local model import/verify/delete (staging + pin policy) on top
of Phase 2 local load contracts and strict offline controls.

Phase 4 adds optional Bearer session-token auth for ``/api/*`` and
``POST /api/shutdown`` for the Tauri desktop sidecar lifecycle.

Phase 5 adds desktop UX: system status API, onboarding flag, welcome/models
static pages, vendor brand/SAM convergence, and log redaction helpers.
"""

__version__ = "0.5.0"

__all__ = ["__version__"]