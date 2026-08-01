"""User-managed Python dependency contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from figuresmith.api.system_routes import probe_dependency_status


ROOT = Path(__file__).resolve().parents[1]


def test_dependency_contract_separates_bootstrap_and_model_scopes() -> None:
    path = ROOT / "apps" / "backend" / "figuresmith" / "runtime" / "dependencies.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    packages = data["packages"]
    scopes = {item["scope"] for item in packages}
    assert {"bootstrap", "models"}.issubset(scopes)
    assert all(item["distribution"] and item["import"] for item in packages)
    assert all(item["requirement"] for item in packages)


def test_dependency_probe_reports_install_guidance_without_importing_model_code() -> None:
    result = probe_dependency_status()
    assert isinstance(result["packages"], list)
    assert isinstance(result["missing_bootstrap"], list)
    assert isinstance(result["missing_models"], list)
    assert result["requirements_file"] == "requirements-runtime.txt"
    assert "pip install" in result["install_command"]
