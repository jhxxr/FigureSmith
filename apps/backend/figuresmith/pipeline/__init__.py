"""Pipeline orchestration boundary for FigureSmith.

Phase 1 provides only a vendor bridge. Do not rewrite SAM3/RMBG here yet.
"""

from figuresmith.pipeline.vendor_bridge import (
    VENDOR_ROOT,
    ensure_vendor_on_sys_path,
    get_vendor_root,
    get_vendor_server_module_hint,
)

__all__ = [
    "VENDOR_ROOT",
    "ensure_vendor_on_sys_path",
    "get_vendor_root",
    "get_vendor_server_module_hint",
]
