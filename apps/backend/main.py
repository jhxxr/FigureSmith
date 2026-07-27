"""FigureSmith development entrypoint.

Imports the vendor AutoFigure-Edit FastAPI app and runs it bound to
loopback only (127.0.0.1). This is intentional for local/desktop use.

Phase 2+: applies strict offline env by default and injects model path env
from the local registry before importing heavy vendor stacks.

Phase 3: mounts ``/api/models/*`` model manager routes (local path import,
verify, delete) onto the vendor app without rewriting vendor server.py.

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


def _mount_figuresmith_routes(app) -> None:
    """Attach FigureSmith-owned API routers (Phase 3 model manager) to vendor app."""
    try:
        from figuresmith.api.models_routes import mount_models_routes
    except ImportError as exc:  # pragma: no cover
        print(f"[FigureSmith] WARNING: model routes unavailable: {exc}", file=sys.stderr)
        return
    # Avoid double-mount when reload/import runs twice.
    existing = {getattr(r, "path", None) for r in getattr(app, "routes", [])}
    if "/api/models" in existing or any(
        str(getattr(r, "path", "")).startswith("/api/models") for r in getattr(app, "routes", [])
    ):
        return
    mount_models_routes(app)
    print("[FigureSmith] mounted /api/models/* (Phase 3 model manager)")


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

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "uvicorn is required. Run scripts/setup-dev.ps1 or "
            "`pip install -r apps/backend/requirements.txt`."
        ) from exc

    print("--- FigureSmith backend (Phase 3) ---")
    print(f"Vendor root : {vendor_root}")
    print(f"Uvicorn app : {get_vendor_server_module_hint()}")
    print(f"Local URL   : http://{args.host}:{args.port}/")
    print(f"Health      : http://{args.host}:{args.port}/healthz")
    print(f"Models API  : http://{args.host}:{args.port}/api/models")
    print("Bind policy : 127.0.0.1 only (recommended)")
    print(f"Strict off. : {strict}")
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
