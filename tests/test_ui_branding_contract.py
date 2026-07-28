"""UI contract tests for Phase 5 branding and local-only SAM."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "vendor" / "autofigure_edit" / "web"
UI = ROOT / "apps" / "backend" / "figuresmith" / "static" / "ui"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_create_and_import_pages_brand_figuresmith() -> None:
    index = _read(WEB / "index.html")
    import_html = _read(WEB / "import.html")
    assert "FigureSmith" in index
    assert "FigureSmith" in import_html
    assert 'value="local"' in index
    assert 'value="local"' in import_html
    # No selectable remote SAM options in formal HTML
    assert not re.search(r'<option[^>]+value="fal"', index)
    assert not re.search(r'<option[^>]+value="roboflow"', index)
    assert not re.search(r'<option[^>]+value="fal"', import_html)
    assert not re.search(r'<option[^>]+value="roboflow"', import_html)


def test_app_js_forces_local_sam() -> None:
    js = _read(WEB / "app.js")
    assert "FIGURESMITH_SAM_BACKEND" in js
    assert "forceLocalSamBackend" in js
    # Must not default payload/state to roboflow anymore
    assert '?? "roboflow"' not in js
    assert '?? "fal"' not in js
    assert "samBackend.value === \"fal\"" not in js
    assert "samBackend.value === \"roboflow\"" not in js


def test_welcome_and_models_ui_exist() -> None:
    assert (UI / "welcome.html").is_file()
    assert (UI / "models.html").is_file()
    assert (UI / "common.js").is_file()
    welcome = _read(UI / "welcome.html")
    models = _read(UI / "models.html")
    assert "FigureSmith" in welcome or "图匠" in welcome
    assert "FigureSmith" in models or "模型" in models


def test_no_hf_token_field_in_create_pages() -> None:
    for name in ("index.html", "import.html"):
        html = _read(WEB / name)
        assert "HF_TOKEN" not in html
        assert "HUGGINGFACE" not in html.upper() or "HUGGINGFACE" not in html
