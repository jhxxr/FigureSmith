"""Static checks for runtime manifest evidence in the Windows workflow."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_carries_structured_runtime_manifest() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-windows.yml").read_text(
        encoding="utf-8"
    )

    assert "dist-runtime/**/runtime-manifest.json" in workflow
    assert "-name 'runtime-manifest.json'" in workflow
