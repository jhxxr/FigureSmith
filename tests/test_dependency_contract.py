"""User-managed Python dependency contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from figuresmith.api.system_routes import (
    _DEFAULT_DEPENDENCIES,
    _load_dependency_contract,
    probe_dependency_status,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "apps" / "backend" / "figuresmith" / "runtime" / "dependencies.json"


def test_dependency_contract_separates_bootstrap_and_model_scopes() -> None:
    path = ROOT / "apps" / "backend" / "figuresmith" / "runtime" / "dependencies.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    packages = data["packages"]
    scopes = {item["scope"] for item in packages}
    assert {"bootstrap", "models"}.issubset(scopes)
    assert all(item["distribution"] and item["import"] for item in packages)
    assert all(item["requirement"] for item in packages)


def test_loader_reads_the_shipped_contract_and_does_not_fall_back() -> None:
    # The loader resolves dependencies.json from figuresmith/runtime/, not from
    # its own directory. A wrong path made this degrade silently to the small
    # built-in subset while the desktop resolver used the full contract.
    shipped = json.loads(CONTRACT.read_text(encoding="utf-8"))["packages"]
    loaded = _load_dependency_contract()
    assert len(loaded) == len(shipped)
    assert len(loaded) > len(_DEFAULT_DEPENDENCIES)
    assert {item["distribution"] for item in loaded} == {
        item["distribution"] for item in shipped
    }


def test_probe_covers_every_scope_in_the_shipped_contract() -> None:
    result = probe_dependency_status()
    reported = {item["distribution"] for item in result["packages"]}
    shipped = json.loads(CONTRACT.read_text(encoding="utf-8"))["packages"]
    assert reported == {item["distribution"] for item in shipped}


def test_dependency_probe_reports_install_guidance_without_importing_model_code() -> None:
    result = probe_dependency_status()
    assert isinstance(result["packages"], list)
    assert isinstance(result["missing_bootstrap"], list)
    assert isinstance(result["missing_models"], list)
    assert result["requirements_file"] == "requirements-runtime.txt"
    assert "pip install" in result["install_command"]
