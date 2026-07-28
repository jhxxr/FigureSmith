"""System lifecycle + status routes for desktop sidecar (Phase 4/5)."""

from __future__ import annotations

import logging
import os
import platform
import threading
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("figuresmith.system")

router = APIRouter(prefix="/api", tags=["system"])

_SHUTDOWN_STARTED = False
_SHUTDOWN_LOCK = threading.Lock()

GPU_MISSING_ZH = (
    "未检测到可用的 NVIDIA CUDA 环境。"
    "本地 SAM3 / RMBG 在仅 CPU 模式下可能不可用或极慢；"
    "请安装 NVIDIA 驱动与 CUDA 兼容的 PyTorch，或在「模型」页确认权重已导入。"
)
GPU_MISSING_EN = (
    "No usable NVIDIA CUDA environment detected. "
    "Local SAM3 / RMBG may be unavailable or very slow on CPU-only hosts. "
    "Install an NVIDIA driver and a CUDA-enabled PyTorch build, "
    "or confirm model weights are imported on the Models page."
)


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


def _manager_from_request(request: Request):
    """Prefer app.state override (tests), else FIGURESMITH_DATA_DIR / default."""
    from figuresmith.models.manager import ModelManager

    override = getattr(request.app.state, "figuresmith_app_data_dir", None)
    if override:
        return ModelManager(app_data_dir=Path(override))
    env_dir = os.environ.get("FIGURESMITH_DATA_DIR")
    if env_dir and str(env_dir).strip():
        return ModelManager(app_data_dir=Path(env_dir))
    return ModelManager()


def _settings_path_for_manager(mgr) -> Path:
    return Path(mgr.app_data_dir) / "settings.json"


def _read_onboarding_completed(settings_path: Path) -> bool:
    from figuresmith.models.settings_io import read_settings

    data = read_settings(settings_path)
    raw = data.get("onboarding_completed")
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    onboarding = data.get("onboarding")
    if isinstance(onboarding, dict):
        val = onboarding.get("completed")
        if isinstance(val, bool):
            return val
    return False


def _write_onboarding_completed(settings_path: Path, completed: bool) -> None:
    from figuresmith.models.settings_io import atomic_write_json, read_settings

    data = read_settings(settings_path)
    data["onboarding_completed"] = bool(completed)
    onboarding = data.get("onboarding") if isinstance(data.get("onboarding"), dict) else {}
    onboarding = dict(onboarding)
    onboarding["completed"] = bool(completed)
    onboarding["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data["onboarding"] = onboarding
    atomic_write_json(settings_path, data)


def probe_gpu_status() -> dict[str, Any]:
    """Probe torch/CUDA safely — never raises."""
    result: dict[str, Any] = {
        "gpu_available": False,
        "gpu_name": None,
        "cuda_version": None,
        "vram_total_mb": None,
        "vram_free_mb": None,
        "pytorch_cuda": False,
        "torch_version": None,
        "probe_error": None,
    }
    try:
        import torch  # type: ignore
    except Exception as exc:  # ImportError or environment issues
        result["probe_error"] = f"torch_unavailable:{type(exc).__name__}"
        return result

    try:
        result["torch_version"] = getattr(torch, "__version__", None)
        cuda_is_available = False
        try:
            cuda_is_available = bool(torch.cuda.is_available())
        except Exception as exc:
            result["probe_error"] = f"cuda_is_available_failed:{type(exc).__name__}"
            return result

        result["pytorch_cuda"] = cuda_is_available
        result["gpu_available"] = cuda_is_available

        try:
            result["cuda_version"] = getattr(torch.version, "cuda", None)
        except Exception:
            result["cuda_version"] = None

        if not cuda_is_available:
            return result

        try:
            if torch.cuda.device_count() > 0:
                result["gpu_name"] = torch.cuda.get_device_name(0)
        except Exception as exc:
            result["probe_error"] = f"device_name_failed:{type(exc).__name__}"

        try:
            free_b, total_b = torch.cuda.mem_get_info(0)
            result["vram_total_mb"] = int(total_b // (1024 * 1024))
            result["vram_free_mb"] = int(free_b // (1024 * 1024))
        except Exception:
            # mem_get_info may be missing on older builds; try properties.
            try:
                props = torch.cuda.get_device_properties(0)
                total = int(getattr(props, "total_memory", 0) or 0)
                if total > 0:
                    result["vram_total_mb"] = int(total // (1024 * 1024))
            except Exception as exc:
                if not result.get("probe_error"):
                    result["probe_error"] = f"vram_probe_failed:{type(exc).__name__}"
    except Exception as exc:  # pragma: no cover - defensive
        result["probe_error"] = f"gpu_probe_failed:{type(exc).__name__}"
        result["gpu_available"] = False
        result["pytorch_cuda"] = False
    return result


def build_system_status(
    *,
    app_data_dir: Optional[Path] = None,
    request: Optional[Request] = None,
) -> dict[str, Any]:
    """Assemble GET /api/system/status payload (never raises on GPU/model probe)."""
    from figuresmith import __version__
    from figuresmith.models.manager import ModelManager
    from figuresmith.security.offline import is_strict_offline_enabled

    if request is not None:
        mgr = _manager_from_request(request)
    elif app_data_dir is not None:
        mgr = ModelManager(app_data_dir=app_data_dir)
    else:
        mgr = ModelManager()

    models_payload: dict[str, Any]
    try:
        models_payload = mgr.list_models()
    except Exception as exc:  # pragma: no cover
        models_payload = {"error": str(exc), "models": []}

    sam3_loaded = False
    rmbg_loaded = False
    try:
        for item in models_payload.get("models") or []:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or "")
            installed = bool(item.get("installed"))
            if mid in {"sam3", "SAM3"} or "sam3" in mid.lower():
                sam3_loaded = installed
            if mid in {"rmbg-2.0", "rmbg", "RMBG"} or "rmbg" in mid.lower():
                rmbg_loaded = installed
    except Exception:
        pass

    gpu = probe_gpu_status()
    settings_path = _settings_path_for_manager(mgr)
    try:
        onboarding_completed = _read_onboarding_completed(settings_path)
    except Exception:
        onboarding_completed = False

    plat = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "platform": platform.platform(),
    }

    status: dict[str, Any] = {
        "product": "FigureSmith",
        "version": __version__,
        "platform": plat,
        "python": platform.python_version(),
        "gpu_available": bool(gpu.get("gpu_available")),
        "gpu_name": gpu.get("gpu_name"),
        "cuda_version": gpu.get("cuda_version"),
        "vram_total_mb": gpu.get("vram_total_mb"),
        "vram_free_mb": gpu.get("vram_free_mb"),
        "pytorch_cuda": bool(gpu.get("pytorch_cuda")),
        "torch_version": gpu.get("torch_version"),
        "sam3_loaded": sam3_loaded,
        "rmbg_loaded": rmbg_loaded,
        "models": models_payload,
        "strict_offline": bool(is_strict_offline_enabled(default=True)),
        "onboarding_completed": onboarding_completed,
        "app_data_dir": str(mgr.app_data_dir),
        "messages": {
            "gpu_missing_zh": GPU_MISSING_ZH,
            "gpu_missing_en": GPU_MISSING_EN,
        },
    }
    if gpu.get("probe_error"):
        status["gpu_probe_error"] = gpu["probe_error"]
    return status


class OnboardingRequest(BaseModel):
    completed: bool = Field(..., description="Whether first-run onboarding is complete")


@router.get("/system/status")
def system_status(request: Request) -> dict[str, Any]:
    """Hardware / model / onboarding status for welcome wizard and models page."""
    try:
        return build_system_status(request=request)
    except Exception as exc:  # pragma: no cover - must never 500 on probe
        logger.exception("system status failed unexpectedly")
        from figuresmith import __version__

        return {
            "product": "FigureSmith",
            "version": __version__,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "python": platform.python_version(),
            "gpu_available": False,
            "gpu_name": None,
            "cuda_version": None,
            "vram_total_mb": None,
            "vram_free_mb": None,
            "pytorch_cuda": False,
            "sam3_loaded": False,
            "rmbg_loaded": False,
            "models": {"models": []},
            "strict_offline": True,
            "onboarding_completed": False,
            "messages": {
                "gpu_missing_zh": GPU_MISSING_ZH,
                "gpu_missing_en": GPU_MISSING_EN,
            },
            "error": f"{type(exc).__name__}: {exc}",
        }


@router.post("/system/onboarding")
def set_onboarding(body: OnboardingRequest, request: Request) -> dict[str, Any]:
    """Persist first-run onboarding completion flag into settings.json."""
    mgr = _manager_from_request(request)
    settings_path = _settings_path_for_manager(mgr)
    try:
        _write_onboarding_completed(settings_path, body.completed)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "ONBOARDING_WRITE_FAILED",
                "message": str(exc),
                "message_zh": "无法写入引导状态",
            },
        ) from exc
    return {
        "ok": True,
        "onboarding_completed": bool(body.completed),
        "settings_path": str(settings_path),
    }


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
    # If any system route already present, skip full re-include.
    if "/api/shutdown" in existing and "/api/system/status" in existing:
        return
    # If only shutdown was mounted in an older process, still include router —
    # FastAPI will register remaining paths; duplicate path names are rare in tests
    # because create_models_app builds a fresh app.
    if "/api/shutdown" in existing and "/api/system/status" not in existing:
        # Partial upgrade path: add status/onboarding only.
        status_router = APIRouter(prefix="/api", tags=["system"])
        status_router.add_api_route(
            "/system/status", system_status, methods=["GET"]
        )
        status_router.add_api_route(
            "/system/onboarding", set_onboarding, methods=["POST"]
        )
        app.include_router(status_router)
        return
    app.include_router(router)
