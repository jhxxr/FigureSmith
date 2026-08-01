"""Static checks for the Windows packaging and release workflow."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> str:
    return (ROOT / ".github" / "workflows" / "release-windows.yml").read_text(
        encoding="utf-8"
    )


def test_windows_release_triggers_tags_and_manual_runs() -> None:
    workflow = _workflow()

    assert 'tags:\n      - "v*"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "skip_desktop:" in workflow
    assert "manual packaging trial (never publishes)" in workflow


def test_release_is_gated_to_successful_packaging_and_has_write_permission() -> None:
    workflow = _workflow()

    assert "needs: [package-runtime, package-desktop]" in workflow
    assert "needs.package-runtime.result == 'success'" in workflow
    assert "needs.package-desktop.result == 'success'" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "inputs.create_release" not in workflow
    assert "./scripts/ci/sync-version.ps1 -CheckOnly" in workflow
    assert "permissions:\n      contents: write" in workflow
    assert "softprops/action-gh-release@v2" in workflow


def test_release_uploads_only_expected_packaged_artifacts() -> None:
    workflow = _workflow()

    for pattern in (
        "dist-runtime/*.zip",
        "dist-runtime/checksums.txt",
        "dist-runtime/**/MANIFEST.json",
        "dist-runtime/**/runtime-manifest.json",
        "dist-desktop/FigureSmith-*.exe",
        "dist-desktop/FigureSmith-*.msi",
        "dist-desktop/FigureSmith-Portable-*.zip",
    ):
        assert pattern in workflow
    assert workflow.count("if-no-files-found: error") >= 2
    assert "fail_on_unmatched_files: true" in workflow


def test_release_reasserts_no_weight_files_before_upload() -> None:
    workflow = _workflow()

    for pattern in (
        "-iname '*.pt'",
        "-iname '*.safetensors'",
        "-iname '*.h5'",
        "-iname '*.pb'",
        "-iname '*.bin'",
    ):
        assert pattern in workflow


def test_windows_release_carries_structured_runtime_manifest() -> None:
    workflow = _workflow()

    assert "dist-runtime/**/runtime-manifest.json" in workflow
    assert "-name 'runtime-manifest.json'" in workflow
    assert "Require complete runtime manifest" in workflow
    assert 'if ($manifest.runtime_complete -ne $true)' in workflow
    assert "refusing to publish a dependency-install pack" in workflow


def test_release_notes_use_version_from_the_same_shell_step() -> None:
    workflow = _workflow()

    assert "export VER" in workflow
    assert "VER: ${{ steps.meta.outputs.version }}" not in workflow
