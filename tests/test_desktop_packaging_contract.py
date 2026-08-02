"""Static checks for fail-closed desktop packaging behavior."""

from __future__ import annotations

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_builder_refuses_placeholder_portable_artifacts() -> None:
    script = (ROOT / "scripts" / "build-desktop.ps1").read_text(encoding="utf-8")

    assert "BUILD_INSTRUCTIONS.txt" not in script
    assert "refusing to create a placeholder Portable artifact" in script
    assert 'throw "No FigureSmith release executable found' in script
    assert "Copy-Item $releaseExe" in script


def test_release_workflow_does_not_upload_placeholder_instructions() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-windows.yml").read_text(
        encoding="utf-8"
    )

    assert "BUILD_INSTRUCTIONS.txt" not in workflow
    assert "FigureSmith-Portable-*.zip" in workflow


def test_tauri_maps_application_runtime_as_a_bundle_resource() -> None:
    config = json.loads(
        (ROOT / "apps" / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )
    assert "runtime" in config["bundle"]["resources"]


def test_desktop_builder_requires_and_carries_application_runtime() -> None:
    script = (ROOT / "scripts" / "build-desktop.ps1").read_text(encoding="utf-8")

    assert "Assert-ApplicationRuntime" in script
    assert "runtime-manifest.json" in script
    assert "application_only -ne $true" in script
    assert 'python_required -ne "external"' in script
    assert "app\\backend\\main.py" in script
    assert "requirements-runtime.txt" in script
    assert "requirements-bootstrap.txt" in script
    assert "requirements-models.txt" in script
    assert "Copy-Item $TauriResources" in script
    assert "embedded runtime" not in script.lower()


def test_runtime_builder_consumes_locked_inputs_without_network_resolution() -> None:
    script = (ROOT / "scripts" / "build-runtime.ps1").read_text(encoding="utf-8")

    assert "assemble_runtime.py" in script
    assert "--wheelhouse" in script
    assert "--lock-root" in script
    assert "--variant" in script
    assert ".stage-$Variant" in script
    assert '"$zipPath.partial"' in script
    assert "Move-Item -LiteralPath $zipStagePath" in script
    assert "$published = $true" in script
    assert "runtime_complete=true" in script
    assert "Invoke-WebRequest" not in script
    assert "Download-Verified" not in script
    assert "Expand-Archive" not in script
    assert "git clone" not in script
    assert "pip install" not in script
    assert "requirements-models.txt" not in script


def test_desktop_uses_a_separate_managed_python_environment() -> None:
    sidecar = (ROOT / "apps" / "desktop" / "src-tauri" / "src" / "sidecar.rs").read_text(
        encoding="utf-8"
    )
    commands = (ROOT / "apps" / "desktop" / "src-tauri" / "src" / "commands.rs").read_text(
        encoding="utf-8"
    )
    splash = (ROOT / "apps" / "desktop" / "src" / "main.ts").read_text(encoding="utf-8")

    assert "FIGURESMITH_MANAGED_PYTHON_DIR" in sidecar
    assert '"-m", "venv", "--clear"' in sidecar
    assert '"-m",\n            "pip",\n            "install"' in sidecar
    assert "cannot modify" in sidecar.lower()
    assert "prepare_managed_python_environment" in commands
    assert "request_restart" in commands
    assert "Create isolated environment" in splash


def test_model_import_ui_exposes_visual_progress() -> None:
    welcome = (ROOT / "apps" / "backend" / "figuresmith" / "static" / "ui" / "welcome.js").read_text(
        encoding="utf-8"
    )
    models = (ROOT / "apps" / "backend" / "figuresmith" / "static" / "ui" / "models.js").read_text(
        encoding="utf-8"
    )

    assert "fs-import-progress" in welcome
    assert "importing_model" in welcome
    assert "data-transfer" in models
    assert "import_complete" in models
