"""Read/write app-data settings.json for imported model paths."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Union

from figuresmith.models.paths import get_app_data_dir, get_settings_path

PathLike = Union[str, Path]


def read_settings(path: PathLike) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def atomic_write_json(path: PathLike, data: dict[str, Any]) -> Path:
    """Write JSON via temp file + replace for crash safety."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def update_model_settings(
    *,
    sam3_checkpoint: Optional[PathLike] = None,
    sam3_bpe: Optional[PathLike] = None,
    rmbg_model_path: Optional[PathLike] = None,
    clear_sam3: bool = False,
    clear_rmbg: bool = False,
    app_data_dir: Optional[Path] = None,
    settings_path: Optional[Path] = None,
    also_update_dev: bool = True,
) -> list[Path]:
    """Merge model path fields into settings.json (app data, and dev if present).

    Returns the list of settings files written.
    """
    app_data = app_data_dir if app_data_dir is not None else get_app_data_dir()
    targets: list[Path] = []

    primary = (
        Path(settings_path)
        if settings_path is not None
        else get_settings_path(app_data_dir=app_data, prefer_dev=False)
    )
    targets.append(primary)

    if also_update_dev:
        # Update project-local dev settings only when the file already exists.
        try:
            from figuresmith.models.manifest import find_repo_root

            root = find_repo_root()
        except Exception:
            root = None
        if root is not None:
            dev = root / ".figuresmith" / "settings.json"
            if dev.is_file() and dev.resolve() != primary.resolve():
                targets.append(dev)

    written: list[Path] = []
    for target in targets:
        data = read_settings(target)
        models = data.get("models") if isinstance(data.get("models"), dict) else {}
        models = dict(models)

        if clear_sam3:
            models.pop("sam3_checkpoint", None)
            models.pop("sam3_bpe", None)
        else:
            if sam3_checkpoint is not None:
                models["sam3_checkpoint"] = str(Path(sam3_checkpoint))
            if sam3_bpe is not None:
                models["sam3_bpe"] = str(Path(sam3_bpe))

        if clear_rmbg:
            models.pop("rmbg_model_path", None)
        elif rmbg_model_path is not None:
            models["rmbg_model_path"] = str(Path(rmbg_model_path))

        data["models"] = models
        written.append(atomic_write_json(target, data))

    return written
