"""Developer CLI for model import / list / verify / delete.

Usage::

    python -m figuresmith.models.cli list
    python -m figuresmith.models.cli import-sam3 --source C:\\path\\sam3.pt
    python -m figuresmith.models.cli import-rmbg --source C:\\path\\rmbg.zip --kind zip
    python -m figuresmith.models.cli verify-sam3
    python -m figuresmith.models.cli delete-rmbg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from figuresmith.models.errors import FigureSmithError
from figuresmith.models.manager import ModelManager, error_payload


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _manager(data_dir: Optional[str]) -> ModelManager:
    return ModelManager(app_data_dir=Path(data_dir) if data_dir else None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m figuresmith.models.cli",
        description="FigureSmith Phase 3 model manager CLI (local paths only)",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override app data dir (same as FIGURESMITH_DATA_DIR)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List model install status")
    sub.add_parser("paths", help="Show resolved model paths")

    p_sam3 = sub.add_parser("import-sam3", help="Import local SAM3 .pt checkpoint")
    p_sam3.add_argument("--source", required=True, help="Absolute path to .pt/.pth")
    p_sam3.add_argument("--min-bytes", type=int, default=None, help="Min size override")
    p_sam3.add_argument("--max-bytes", type=int, default=None, help="Max size override")
    p_sam3.add_argument(
        "--allow-relative",
        action="store_true",
        help="Allow non-absolute source (dev only)",
    )

    p_rmbg = sub.add_parser("import-rmbg", help="Import RMBG ZIP or folder")
    p_rmbg.add_argument("--source", required=True, help="Absolute path to zip or directory")
    p_rmbg.add_argument(
        "--kind",
        choices=["auto", "zip", "dir"],
        default="auto",
        help="Source kind (default auto-detect)",
    )
    p_rmbg.add_argument(
        "--allow-relative",
        action="store_true",
        help="Allow non-absolute source (dev only)",
    )

    sub.add_parser("verify-sam3", help="Re-verify installed SAM3")
    sub.add_parser("verify-rmbg", help="Re-verify installed RMBG")
    sub.add_parser("delete-sam3", help="Delete installed SAM3 pack")
    sub.add_parser("delete-rmbg", help="Delete installed RMBG pack")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    mgr = _manager(args.data_dir)

    try:
        if args.command == "list":
            _print_json(mgr.list_models())
            return 0
        if args.command == "paths":
            _print_json(mgr.get_paths())
            return 0
        if args.command == "import-sam3":
            result = mgr.import_sam3(
                args.source,
                min_bytes=args.min_bytes,
                max_bytes=args.max_bytes,
                require_absolute=not args.allow_relative,
            )
            _print_json({"ok": True, **result})
            return 0
        if args.command == "import-rmbg":
            result = mgr.import_rmbg(
                args.source,
                kind=args.kind,
                require_absolute=not args.allow_relative,
            )
            _print_json({"ok": True, **result})
            for warning in result.get("warnings") or []:
                print(f"[warning] {warning}", file=sys.stderr)
            return 0
        if args.command == "verify-sam3":
            _print_json({"ok": True, **mgr.verify_sam3()})
            return 0
        if args.command == "verify-rmbg":
            _print_json({"ok": True, **mgr.verify_rmbg()})
            return 0
        if args.command == "delete-sam3":
            _print_json({"ok": True, **mgr.delete_sam3()})
            return 0
        if args.command == "delete-rmbg":
            _print_json({"ok": True, **mgr.delete_rmbg()})
            return 0
        parser.error(f"unknown command: {args.command}")
        return 2
    except FigureSmithError as exc:
        _print_json(error_payload(exc))
        return 1
    except Exception as exc:  # pragma: no cover
        _print_json(error_payload(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
