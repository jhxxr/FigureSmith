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

Phase 5: ``GET /api/system/status`` + onboarding; welcome/models static UI
served with priority over the vendor catch-all StaticFiles mount; brand/SAM
convergence patches live in vendor web.

Health check: GET /healthz
Models API:   GET /api/models
System API:   GET /api/system/status
Default URL:  http://127.0.0.1:8765/
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from fastapi import Request

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


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "figuresmith" / "static"


def _ui_dir() -> Path:
    return _static_dir() / "ui"


def _mount_desktop_bridge(app) -> None:
    """Expose the desktop bridge on the FigureSmith outer app."""
    paths = {
        str(getattr(route, "path", "") or "")
        for route in getattr(app, "routes", [])
    }
    if "/figuresmith-bridge.js" in paths:
        return

    try:
        from starlette.responses import FileResponse
    except ImportError:  # pragma: no cover
        return

    bridge_path = _static_dir() / "desktop-bridge.js"
    if not bridge_path.is_file():
        print(
            f"[FigureSmith] WARNING: desktop bridge missing at {bridge_path}",
            file=sys.stderr,
        )
        return

    async def figuresmith_bridge_js(request):  # noqa: ARG001
        return FileResponse(
            bridge_path,
            media_type="application/javascript; charset=utf-8",
            filename="figuresmith-bridge.js",
        )

    app.add_route("/figuresmith-bridge.js", figuresmith_bridge_js, methods=["GET"])
    print("[FigureSmith] mounted /figuresmith-bridge.js (Phase 4 desktop bridge)")


def _mount_figuresmith_ui(app) -> None:
    """Serve FigureSmith UI assets before the vendor fallback mount."""
    try:
        from starlette.responses import FileResponse, Response
    except ImportError:  # pragma: no cover
        return

    ui = _ui_dir()
    static = _static_dir()
    if not ui.is_dir():
        print(f"[FigureSmith] WARNING: UI dir missing at {ui}", file=sys.stderr)
        return

    def _file_endpoint(path: Path, media_type: str):
        async def endpoint(request):  # noqa: ARG001
            if not path.is_file():
                return Response("Not found", status_code=404)
            return FileResponse(path, media_type=media_type)

        return endpoint

    # Page map: URL path → file under static/ui or static/
    page_files = {
        "/welcome.html": (ui / "welcome.html", "text/html; charset=utf-8"),
        "/models.html": (ui / "models.html", "text/html; charset=utf-8"),
        "/fs/welcome.css": (ui / "welcome.css", "text/css; charset=utf-8"),
        "/fs/models.css": (ui / "models.css", "text/css; charset=utf-8"),
        "/fs/welcome.js": (ui / "welcome.js", "application/javascript; charset=utf-8"),
        "/fs/models.js": (ui / "models.js", "application/javascript; charset=utf-8"),
        "/fs/common.css": (ui / "common.css", "text/css; charset=utf-8"),
        "/fs/common.js": (ui / "common.js", "application/javascript; charset=utf-8"),
        "/fs/brand-mark.svg": (ui / "brand-mark.svg", "image/svg+xml"),
    }

    existing = {
        str(getattr(route, "path", "") or "")
        for route in getattr(app, "routes", [])
    }
    mounted = 0
    for url, (path, media) in page_files.items():
        if url in existing:
            continue
        if not path.is_file():
            # Allow partial UI during development; warn once per missing file.
            print(
                f"[FigureSmith] WARNING: UI asset missing: {path}",
                file=sys.stderr,
            )
            continue
        app.add_route(url, _file_endpoint(path, media), methods=["GET"])
        mounted += 1

    # Optional: also expose brand-override helpers if present
    for name, media in (
        ("brand-override.js", "application/javascript; charset=utf-8"),
        ("brand-override.css", "text/css; charset=utf-8"),
    ):
        path = static / name
        url = f"/fs/{name}"
        if path.is_file() and url not in existing:
            app.add_route(url, _file_endpoint(path, media), methods=["GET"])
            mounted += 1

    if mounted:
        print(f"[FigureSmith] mounted {mounted} Phase 5 UI asset route(s)")


def _configure_vendor_data_root(vendor_app, app_paths) -> None:
    """Point the vendored server's mutable directories at the canonical root."""
    vendor_server = sys.modules.get("server")
    if vendor_server is None or getattr(vendor_server, "app", None) is not vendor_app:
        return

    from figuresmith.models.errors import DataDirNotWritable
    from figuresmith.models.paths import ensure_under_root

    def mutable_override(name: str, default: Path) -> Path:
        raw = os.environ.get(name)
        candidate = Path(raw).expanduser() if raw and raw.strip() else default
        try:
            return ensure_under_root(app_paths.root, candidate)
        except Exception as exc:
            raise DataDirNotWritable(
                detail=f"{name} must remain under the application data root"
            ) from exc

    outputs = mutable_override("FIGURESMITH_OUTPUTS_DIR", app_paths.outputs)
    uploads = mutable_override("FIGURESMITH_UPLOADS_DIR", app_paths.uploads)
    outputs.mkdir(parents=True, exist_ok=True)
    uploads.mkdir(parents=True, exist_ok=True)
    vendor_server.APP_DATA_DIR = app_paths.root
    vendor_server.JOBS_DIR = app_paths.jobs
    vendor_server.TEMP_DIR = app_paths.temp
    vendor_server.LOGS_DIR = app_paths.logs
    vendor_server.SVG_CACHE_DIR = app_paths.svg_cache
    vendor_server.OUTPUTS_DIR = outputs
    vendor_server.UPLOADS_DIR = uploads


def create_production_app(
    vendor_app=None,
    *,
    app_data_dir: Path | None = None,
    app_paths=None,
    install_auth: bool = True,
):
    """Create the production composition used by Uvicorn and desktop smoke.

    FigureSmith owns the outer app so its routes and middleware are registered
    before the vendor application is mounted as the final ``/`` fallback.
    ``vendor_app`` is injectable for composition tests without changing route
    ordering or production behavior.
    """
    from fastapi import FastAPI
    from figuresmith.api.models_routes import mount_models_routes
    from figuresmith.api.system_routes import mount_system_routes
    from figuresmith.models.paths import resolve_app_paths

    if app_paths is not None:
        resolved_paths = app_paths
    else:
        resolved_paths = resolve_app_paths(app_data_dir=app_data_dir)

    # Validate and construct the canonical layout before importing vendor
    # server.py. Its module-level initialization creates mutable directories.
    if vendor_app is None:
        vendor_app = _load_vendor_app()

    app = FastAPI(title="FigureSmith", version="0.6.0")
    resolved_data_dir = resolved_paths.root
    app.state.figuresmith_app_paths = resolved_paths
    app.state.figuresmith_app_data_dir = str(resolved_data_dir)
    _configure_vendor_data_root(vendor_app, resolved_paths)

    mount_models_routes(app, app_data_dir=resolved_data_dir)
    mount_system_routes(app)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "application": "figuresmith"}

    @app.get("/api/desktop/ready")
    def desktop_ready(request: Request) -> dict[str, object]:
        """Authenticated readiness probe for the desktop bootstrap."""
        return {
            "ok": True,
            "ready": True,
            "application": "figuresmith",
            "api_base_path": "/api",
            "app_data_dir": str(
                getattr(request.app.state, "figuresmith_app_data_dir", str(resolved_data_dir))
            ),
            "models_dir": str(resolved_paths.models),
        }

    _mount_desktop_bridge(app)
    _mount_figuresmith_ui(app)

    if install_auth:
        _install_security(app)

    # This must remain the final route: vendor UI/API is an opaque fallback.
    app.mount("/", vendor_app)
    return app


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

    try:
        from figuresmith.models.paths import resolve_app_paths

        app_paths = resolve_app_paths()
        applied = prepare_figuresmith_runtime(
            strict_offline=strict,
            default_strict=True,
            app_data_dir=app_paths.root,
        )
    except Exception as exc:
        from figuresmith.models.errors import DataDirNotWritable

        if isinstance(exc, DataDirNotWritable):
            raise SystemExit(str(exc)) from exc
        raise
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
    try:
        app = create_production_app(app_paths=app_paths)
    except Exception as exc:
        from figuresmith.models.errors import DataDirNotWritable

        if isinstance(exc, DataDirNotWritable):
            raise SystemExit(str(exc)) from exc
        raise

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

    print("--- FigureSmith backend (Phase 5) ---")
    print(f"Vendor root : {vendor_root}")
    print(f"Uvicorn app : {get_vendor_server_module_hint()} (composed)")
    print(f"Local URL   : http://{args.host}:{args.port}/")
    print(f"Welcome     : http://{args.host}:{args.port}/welcome.html")
    print(f"Models UI   : http://{args.host}:{args.port}/models.html")
    print(f"Health      : http://{args.host}:{args.port}/healthz")
    print(f"Models API  : http://{args.host}:{args.port}/api/models")
    print(f"System API  : http://{args.host}:{args.port}/api/system/status")
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
