"""Load ``resources/model-manifest.json`` and evaluate official pin policy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

from figuresmith.models.checksums import digests_equal
from figuresmith.models.errors import ModelImportPinMismatch
from figuresmith.security.offline import env_flag_true

PathLike = Union[str, Path]

ENV_ALLOW_UNPINNED = "FIGURESMITH_ALLOW_UNPINNED_MODELS"
MANIFEST_REL = Path("resources") / "model-manifest.json"


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Best-effort monorepo root discovery (vendor + apps/backend markers)."""
    here = start if start is not None else Path(__file__).resolve()
    for parent in [here, *here.parents] if here.is_dir() else here.parents:
        if (parent / "vendor" / "autofigure_edit").is_dir() and (
            parent / "apps" / "backend"
        ).is_dir():
            return parent
    return None


def get_manifest_path(*, repo_root: Optional[Path] = None) -> Path:
    root = repo_root if repo_root is not None else find_repo_root()
    if root is None:
        # Fall back next to this package's expected monorepo layout.
        root = Path(__file__).resolve().parents[4]
    return Path(root) / MANIFEST_REL


def load_model_manifest(
    *,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Load and return the model manifest document (empty dict on hard failure)."""
    manifest_path = Path(path) if path is not None else get_manifest_path(repo_root=repo_root)
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def get_model_entry(
    model_id: str,
    *,
    manifest: Optional[dict[str, Any]] = None,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Return the manifest entry for ``model_id`` (e.g. ``sam3``, ``rmbg-2.0``)."""
    doc = manifest if manifest is not None else load_model_manifest(path=path, repo_root=repo_root)
    models = doc.get("models")
    if not isinstance(models, list):
        return None
    for entry in models:
        if isinstance(entry, dict) and str(entry.get("id", "")).strip() == model_id:
            return entry
    return None


def allow_unpinned_models(*, env: Optional[dict[str, str]] = None) -> bool:
    """Developer escape hatch: allow imports that do not match official pins."""
    if env is not None:
        raw = env.get(ENV_ALLOW_UNPINNED)
        if raw is None:
            return False
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return env_flag_true(ENV_ALLOW_UNPINNED, default=False)


def _normalize_pin(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"null", "none", "0"}:
        return None
    return text


def get_official_sha256(
    model_id: str,
    *,
    manifest: Optional[dict[str, Any]] = None,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
) -> Optional[str]:
    """Return the primary official pin for a model, if configured.

    Looks at (in order): ``official_sha256``, ``sha256``, then
    ``files_sha256['model.safetensors']`` / ``files_sha256['sam3.pt']``.
    """
    entry = get_model_entry(model_id, manifest=manifest, path=path, repo_root=repo_root)
    if not entry:
        return None
    for key in ("official_sha256", "sha256"):
        pin = _normalize_pin(entry.get(key))
        if pin:
            return pin
    files = entry.get("files_sha256")
    if isinstance(files, dict):
        for candidate in ("model.safetensors", "sam3.pt", "pytorch_model.bin"):
            pin = _normalize_pin(files.get(candidate))
            if pin:
                return pin
    return None


def get_files_sha256(
    model_id: str,
    *,
    manifest: Optional[dict[str, Any]] = None,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
) -> dict[str, str]:
    """Return per-file official pins (may be empty)."""
    entry = get_model_entry(model_id, manifest=manifest, path=path, repo_root=repo_root)
    if not entry:
        return {}
    files = entry.get("files_sha256")
    if not isinstance(files, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in files.items():
        pin = _normalize_pin(value)
        if pin:
            out[str(key)] = pin
    return out


def get_required_files(
    model_id: str,
    *,
    manifest: Optional[dict[str, Any]] = None,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
) -> list[str]:
    entry = get_model_entry(model_id, manifest=manifest, path=path, repo_root=repo_root)
    if not entry:
        return []
    req = entry.get("required_files")
    if not isinstance(req, list):
        return []
    return [str(x) for x in req if str(x).strip()]


@dataclass(frozen=True)
class PinEvaluation:
    """Result of comparing an imported digest against official pins."""

    model_id: str
    actual_sha256: str
    expected_sha256: Optional[str]
    official_verified: bool
    pin_present: bool
    allowed: bool
    warning: Optional[str] = None


def evaluate_pin(
    model_id: str,
    actual_sha256: str,
    *,
    manifest: Optional[dict[str, Any]] = None,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
    allow_unpinned: Optional[bool] = None,
) -> PinEvaluation:
    """Evaluate pin policy without raising.

    Policy:
    - No pin configured → allowed, ``official_verified=False``, warning set.
    - Pin matches → allowed, ``official_verified=True``.
    - Pin mismatches → rejected unless ``allow_unpinned`` / env escape hatch.
    """
    expected = get_official_sha256(
        model_id, manifest=manifest, path=path, repo_root=repo_root
    )
    pin_present = expected is not None
    allow = (
        allow_unpinned
        if allow_unpinned is not None
        else allow_unpinned_models()
    )
    actual = (actual_sha256 or "").strip().lower()

    if not pin_present:
        return PinEvaluation(
            model_id=model_id,
            actual_sha256=actual,
            expected_sha256=None,
            official_verified=False,
            pin_present=False,
            allowed=True,
            warning=(
                "No official SHA-256 pin in model-manifest.json; "
                "import allowed but official_verified=false. "
                "仅可从可信来源导入；源码许可 ≠ 权重许可。"
            ),
        )

    if digests_equal(actual, expected):
        return PinEvaluation(
            model_id=model_id,
            actual_sha256=actual,
            expected_sha256=expected,
            official_verified=True,
            pin_present=True,
            allowed=True,
            warning=None,
        )

    if allow:
        return PinEvaluation(
            model_id=model_id,
            actual_sha256=actual,
            expected_sha256=expected,
            official_verified=False,
            pin_present=True,
            allowed=True,
            warning=(
                f"Pin mismatch for {model_id} but {ENV_ALLOW_UNPINNED}=1; "
                "import allowed with official_verified=false."
            ),
        )

    return PinEvaluation(
        model_id=model_id,
        actual_sha256=actual,
        expected_sha256=expected,
        official_verified=False,
        pin_present=True,
        allowed=False,
        warning=(
            f"Pin mismatch for {model_id}: expected {expected}, got {actual}. "
            f"Set {ENV_ALLOW_UNPINNED}=1 to allow unpinned imports in development."
        ),
    )


def require_pin_or_raise(
    model_id: str,
    actual_sha256: str,
    *,
    manifest: Optional[dict[str, Any]] = None,
    path: Optional[PathLike] = None,
    repo_root: Optional[Path] = None,
    allow_unpinned: Optional[bool] = None,
) -> PinEvaluation:
    """Like :func:`evaluate_pin` but raises on rejected pin mismatch."""
    result = evaluate_pin(
        model_id,
        actual_sha256,
        manifest=manifest,
        path=path,
        repo_root=repo_root,
        allow_unpinned=allow_unpinned,
    )
    if not result.allowed:
        raise ModelImportPinMismatch(
            detail=result.warning
            or f"hash mismatch for {model_id}: got {actual_sha256}"
        )
    return result
