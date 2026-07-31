"""Static checks for fail-closed desktop packaging behavior."""

from __future__ import annotations

from pathlib import Path


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
