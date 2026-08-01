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


def test_windows_release_validates_dependency_pack_manifest_without_embedded_runtime() -> None:
    workflow = _workflow()

    assert "dist-runtime/**/runtime-manifest.json" in workflow
    assert "-name 'runtime-manifest.json'" in workflow
    assert "Validate dependency-install runtime manifest and artifacts" in workflow
    assert '$manifest.product -ne "FigureSmith"' in workflow
    assert "$manifest.version -ne $expectedVersion" in workflow
    assert "$manifest.contains_weights -ne $false" in workflow
    assert "$manifest.contains_cache -ne $false" in workflow
    assert "runtime_complete" not in workflow


def test_runtime_release_requires_exact_dependency_pack_artifacts() -> None:
    workflow = _workflow()

    for pattern in (
        '"MANIFEST.json"',
        '"runtime-manifest.json"',
        '"README-RUNTIME.md"',
        '"$packName.zip"',
        '"checksums.txt"',
        "Expected exactly one runtime directory",
        "Expected exactly one runtime zip and checksums.txt",
        "Expected exactly one MANIFEST.json and README-RUNTIME.md",
    ):
        assert pattern in workflow


def test_release_notes_describe_external_models_and_target_install_boundary() -> None:
    workflow = _workflow()

    assert "Models are external" in workflow
    assert "download and import them on the target machine" in workflow
    assert "Target-machine dependency installation boundary" in workflow
    assert "target machine must provide" in workflow


def test_release_notes_use_version_from_the_same_shell_step() -> None:
    workflow = _workflow()

    assert "export VER" in workflow
    assert "VER: ${{ steps.meta.outputs.version }}" not in workflow
