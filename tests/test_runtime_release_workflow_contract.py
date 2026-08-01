"""Static checks for the Windows application-pack release workflow."""

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


def test_windows_release_validates_application_only_runtime_manifest() -> None:
    workflow = _workflow()

    assert "Validate application-only runtime manifest and artifacts" in workflow
    assert '$manifest.product -ne "FigureSmith"' in workflow
    assert "$manifest.version -ne $expectedVersion" in workflow
    assert "$manifest.contains_weights -ne $false" in workflow
    assert "$manifest.contains_cache -ne $false" in workflow
    assert "$manifest.application_only -ne $true" in workflow
    assert '$manifest.python_required -ne "external"' in workflow
    assert "$manifest.runtime_complete -ne $false" in workflow
    assert '"requirements-runtime.txt"' in workflow
    assert '"requirements-bootstrap.txt"' in workflow
    assert '"requirements-models.txt"' in workflow
    assert '"app/backend/figuresmith/runtime/dependencies.json"' in workflow
    assert "must not contain Python or dependency artifacts" in workflow


def test_runtime_release_requires_application_pack_artifacts() -> None:
    workflow = _workflow()

    for pattern in (
        '"MANIFEST.json"',
        '"runtime-manifest.json"',
        '"README-RUNTIME.md"',
        '"requirements-runtime.txt"',
        '"$packName.zip"',
        '"checksums.txt"',
        "Expected exactly one application runtime directory",
    ):
        assert pattern in workflow


def test_release_notes_describe_external_models_and_python() -> None:
    workflow = _workflow()

    assert "Models are external" in workflow
    assert "download and import them on the target machine" in workflow
    assert "User-managed Python environment" in workflow
    assert "Python 3.10-3.12" in workflow
    assert "does not install them" in workflow


def test_desktop_job_stages_application_pack_before_tauri_build() -> None:
    workflow = _workflow()

    assert "needs: [test, package-runtime]" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "Stage application pack for Tauri resources" in workflow
    assert "apps/desktop/src-tauri/runtime" in workflow
    assert "$manifest.application_only -ne $true" in workflow
    assert "$manifest.python_required -ne \"external\"" in workflow


def test_release_notes_use_version_from_the_same_shell_step() -> None:
    workflow = _workflow()

    assert "export VER" in workflow
    assert "VER: ${{ steps.meta.outputs.version }}" not in workflow
