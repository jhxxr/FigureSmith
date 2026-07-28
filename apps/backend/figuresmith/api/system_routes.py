"""System lifecycle routes for desktop sidecar (shutdown, etc.)."""

from __future__ import annotations

import logging
import os
import threading
import time

from fastapi import APIRouter

logger = logging.getLogger("figuresmith.system")

router = APIRouter(prefix="/api", tags=["system"])

_SHUTDOWN_STARTED = False
_SHUTDOWN_LOCK = threading.Lock()


def reset_shutdown_state_for_tests() -> None:
    """Reset module shutdown latch (unit tests only)."""
    global _SHUTDOWN_STARTED
    with _SHUTDOWN_LOCK:
        _SHUTDOWN_STARTED = False


def _delayed_exit(delay_s: float = 0.35) -> None:
    """Exit the process after allowing the HTTP response to flush."""
    try:
        time.sleep(delay_s)
    finally:
        # Hard exit: uvicorn may keep non-daemon threads alive on sys.exit.
        os._exit(0)


@router.post("/shutdown")
def shutdown() -> dict:
    """Request graceful process exit (desktop sidecar lifecycle).

    Requires Bearer session token when auth is enabled (middleware).
    Idempotent: repeated calls after the first still return ok.
    """
    global _SHUTDOWN_STARTED
    with _SHUTDOWN_LOCK:
        first = not _SHUTDOWN_STARTED
        _SHUTDOWN_STARTED = True

    if first:
        # Do not log secrets; only lifecycle status.
        logger.info("Shutdown requested; process will exit shortly")
        thread = threading.Thread(
            target=_delayed_exit,
            name="figuresmith-shutdown",
            daemon=True,
        )
        thread.start()

    return {"ok": True, "status": "shutting_down"}


def mount_system_routes(app) -> None:
    """Attach system routes onto an existing FastAPI app (idempotent)."""
    existing = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    if "/api/shutdown" in existing:
        return
    app.include_router(router)
