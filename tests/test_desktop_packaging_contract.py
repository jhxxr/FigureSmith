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


def test_tauri_installer_does_not_embed_the_companion_runtime() -> None:
    config = json.loads(
        (ROOT / "apps" / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )
    assert "runtime" not in config["bundle"]["resources"]


def test_desktop_builder_requires_runtime_v1_and_portable_carries_it() -> None:
    script = (ROOT / "scripts" / "build-desktop.ps1").read_text(encoding="utf-8")

    assert "Assert-RuntimeV1" in script
    assert "runtime-manifest.json" in script
    assert "verify_runtime_manifest" in script
    assert "python\\python.exe" in script
    assert "python312._pth" not in script
    assert "robocopy.exe" in script
    assert '"$portableZip.partial"' in script
    assert "Move-Item -LiteralPath $portableZipStage" in script
    assert "$portablePublished = $true" in script
    assert "Tauri resource" in script
    assert "pip install" not in script
    assert "user-managed Python" not in script


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


def test_desktop_release_uses_only_packaged_python_without_setup_ui() -> None:
    sidecar = (ROOT / "apps" / "desktop" / "src-tauri" / "src" / "sidecar.rs").read_text(
        encoding="utf-8"
    )
    commands = (ROOT / "apps" / "desktop" / "src-tauri" / "src" / "commands.rs").read_text(
        encoding="utf-8"
    )
    splash = (ROOT / "apps" / "desktop" / "src" / "main.ts").read_text(encoding="utf-8")

    assert 'join("python").join("python.exe")' in sidecar
    assert 'cmd.arg("-B")' in sidecar
    assert 'if release {' in sidecar
    assert "ensure_managed_environment" not in sidecar
    assert '"pip"' not in sidecar
    assert "prepare_managed_python_environment" not in commands
    assert "Create isolated environment" not in splash
    assert "Runtime V1" in splash


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
