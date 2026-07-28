"""FigureSmith development entrypoint.

Imports the vendor AutoFigure-Edit FastAPI app and runs it bound to
loopback only (127.0.0.1). This is intentional for local/desktop use.

Phase 2+: applies strict offline env by default and injects model path env
from the local registry before importing heavy vendor stacks.

Phase 3: mounts ``/api/models/*`` model manager routes (local path import,
verify, delete) onto the vendor app without rewriting vendor server.py.

Phase 4: optional Bearer session-token auth on ``/api/*`` when
``FIGURESMITH_SESSION_TOKEN`` is set; ``POST /api/shutdown`` for desktop
sidecar lifecycle; desktop-bridge static script for WebView fetch wrapping.

Health check: GET /healthz
Models API:   GET /api/models
Default URL:  http://127.0.0.1:8765/
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure apps/backend is importable when launched as a script.
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from figuresmith.pipeline.vendor_bridge import (  # noqa: E402
    ensure_vendor_on_sys_path,
    get_vendor_root,
    get_vendor_server_module_hint,
)
from figuresmith.runtime.env import prepare_figuresmith_runtime  # noqa: E402
from figuresmith.security.offline import env_flag_true  # noqa: E402


def _load_vendor_app():
    """Import vendor ``server:app`` after placing vendor root on sys.path."""
    vendor_root = ensure_vendor_on_sys_path()
    try:
        import server as vendor_server  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            f"Failed to import vendor server from {vendor_root}: {exc}\n"
            "Install backend requirements and ensure vendor/autofigure_edit exists."
        ) from exc
    if not hasattr(vendor_server, "app"):
        raise SystemExit("vendor server.py does not expose FastAPI `app`")
    return vendor_server.app


def _route_paths(app) -> set[str]:
    return {str(getattr(r, "path", "") or "") for r in getattr(app, "routes", [])}


def _mount_figuresmith_routes(app) -> None:
    """Attach FigureSmith-owned API routers to the vendor app."""
    paths = _route_paths(app)

    # Phase 3 model manager
    try:
        from figuresmith.api.models_routes import mount_models_routes
    except ImportError as exc:  # pragma: no cover
        print(f"[FigureSmith] WARNING: model routes unavailable: {exc}", file=sys.stderr)
    else:
        if "/api/models" not in paths and not any(
            p.startswith("/api/models") for p in paths
        ):
            mount_models_routes(app)
            print("[FigureSmith] mounted /api/models/* (Phase 3 model manager)")

    # Phase 4 system routes (shutdown)
    try:
        from figuresmith.api.system_routes import mount_system_routes
    except ImportError as exc:  # pragma: no cover
        print(f"[FigureSmith] WARNING: system routes unavailable: {exc}", file=sys.stderr)
    else:
        mount_system_routes(app)
        print("[FigureSmith] mounted /api/shutdown (Phase 4 lifecycle)")

    # Desktop bridge script (fetch Authorization wrapper)
    _mount_desktop_bridge(app)


def _mount_desktop_bridge(app) -> None:
    """Expose ``/figuresmith-bridge.js`` without conflicting with vendor ``/`` static."""
    paths = _route_paths(app)
    if "/figuresmith-bridge.js" in paths:
        return

    try:
        from fastapi.responses import FileResponse, Response
    except ImportError:  # pragma: no cover
        return

    bridge_path = (
        Path(__file__).resolve().parent
        / "figuresmith"
        / "static"
        / "desktop-bridge.js"
    )
    if not bridge_path.is_file():
        print(
            f"[FigureSmith] WARNING: desktop bridge missing at {bridge_path}",
            file=sys.stderr,
        )
        return

    @app.get("/figuresmith-bridge.js", include_in_schema=False)
    def figuresmith_bridge_js() -> Response:
        return FileResponse(
            bridge_path,
            media_type="application/javascript; charset=utf-8",
            filename="figuresmith-bridge.js",
        )

    print("[FigureSmith] mounted /figuresmith-bridge.js (Phase 4 desktop bridge)")


def _install_security(app) -> None:
    """Install session-token middleware (no-ops when token unset / auth disabled)."""
    try:
        from figuresmith.security.auth import install_auth_middleware, is_auth_enabled
    except ImportError as exc:  # pragma: no cover
        print(f"[FigureSmith] WARNING: auth middleware unavailable: {exc}", file=sys.stderr)
        return

    enabled = install_auth_middleware(app)
    if enabled:
        print(
            "[FigureSmith] session token auth ENABLED for /api/* "
            "(token not logged; set FIGURESMITH_DISABLE_AUTH=1 to bypass in tests)"
        )
    else:
        print(
            "[FigureSmith] session token auth disabled "
            "(no FIGURESMITH_SESSION_TOKEN or FIGURESMITH_DISABLE_AUTH=1)"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FigureSmith local backend (vendor FastAPI, loopback only)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("FIGURESMITH_HOST", "127.0.0.1"),
        help="Bind host (default: 127.0.0.1 — do not expose publicly)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FIGURESMITH_PORT", "8765")),
        help="Bind port (default: 8765)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload (dev only)",
    )
    parser.add_argument(
        "--strict-offline",
        dest="strict_offline",
        action="store_true",
        default=None,
        help="Force strict offline (default: on via FIGURESMITH_STRICT_OFFLINE=1)",
    )
    parser.add_argument(
        "--no-strict-offline",
        dest="strict_offline",
        action="store_false",
        help="Disable strict offline for developer sessions",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # Phase 2: FigureSmith launcher defaults to strict offline unless explicitly disabled.
    if args.strict_offline is None:
        strict = env_flag_true("FIGURESMITH_STRICT_OFFLINE", default=True)
    else:
        strict = bool(args.strict_offline)

    applied = prepare_figuresmith_runtime(strict_offline=strict, default_strict=True)
    if strict:
        print(f"[FigureSmith] strict offline enabled; env applied: {sorted(applied.keys())}")
    else:
        print("[FigureSmith] strict offline disabled (developer mode)")

    # Hard preference for loopback in Phase 1 documentation + default path.
    # If a non-loopback host is forced, warn loudly.
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            f"[FigureSmith] WARNING: binding to {args.host!r}. "
            "Desktop/local policy is 127.0.0.1 only.",
            file=sys.stderr,
        )

    vendor_root = get_vendor_root()
    ensure_vendor_on_sys_path()
    app = _load_vendor_app()
    _mount_figuresmith_routes(app)
    _install_security(app)

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "uvicorn is required. Run scripts/setup-dev.ps1 or "
            "`pip install -r apps/backend/requirements.txt`."
        ) from exc

    # Never print the session token value.
    token_set = bool(os.environ.get("FIGURESMITH_SESSION_TOKEN", "").strip())
    auth_disabled = env_flag_true("FIGURESMITH_DISABLE_AUTH", default=False)

    print("--- FigureSmith backend (Phase 4) ---")
    print(f"Vendor root : {vendor_root}")
    print(f"Uvicorn app : {get_vendor_server_module_hint()}")
    print(f"Local URL   : http://{args.host}:{args.port}/")
    print(f"Health      : http://{args.host}:{args.port}/healthz")
    print(f"Models API  : http://{args.host}:{args.port}/api/models")
    print(f"Shutdown    : POST http://{args.host}:{args.port}/api/shutdown")
    print("Bind policy : 127.0.0.1 only (recommended)")
    print(f"Strict off. : {strict}")
    print(
        f"Auth mode   : "
        f"{'disabled(bypass)' if auth_disabled else ('token' if token_set else 'off')}"
    )
    print("--------------------------------")

    # Prefer importing the already-loaded app object so path setup is respected.
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=False,
    )


if __name__ == "__main__":
    main()
