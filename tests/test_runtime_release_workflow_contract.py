"""Static checks for the Windows Runtime V1 release workflow."""

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


def test_release_uploads_only_expected_cpu_packaged_artifacts() -> None:
    workflow = _workflow()

    for pattern in (
        "dist-runtime/FigureSmith-Runtime-Windows-CPU-*.zip",
        "dist-runtime/checksums.txt",
        "dist-runtime/FigureSmith-Runtime-Windows-CPU-*/runtime-manifest.json",
        "dist-desktop/FigureSmith-*.exe",
        "dist-desktop/FigureSmith-*.msi",
        "dist-desktop/checksums.txt",
    ):
        assert pattern in workflow
    assert "FigureSmith-Portable-*.zip" not in workflow
    assert "README-PORTABLE.md" not in workflow
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


def test_windows_release_validates_cpu_runtime_v1_manifest() -> None:
    workflow = _workflow()

    assert "Validate CPU Runtime V1 manifest and artifacts" in workflow
    assert '$manifest.product -ne "FigureSmith"' in workflow
    assert "$manifest.version -ne $expectedVersion" in workflow
    assert "$manifest.schema -ne 2" in workflow
    assert '$manifest.variant -ne "cpu"' in workflow
    assert "$manifest.runtime_complete -ne $true" in workflow
    assert "$manifest.contains_weights -ne $false" in workflow
    assert "$manifest.contains_cache -ne $false" in workflow
    assert '"python/python.exe"' in workflow
    assert '"locks/requirements-win-py312-cpu.lock.json"' in workflow
    assert '"locks/sources-cpu.lock.json"' in workflow
    assert '"locks/wheelhouse-cpu.manifest.json"' in workflow
    assert '"app/backend/figuresmith/runtime/dependencies.json"' in workflow
    assert "must not contain loose dependency wheels" in workflow
    assert "Independent Runtime V1 manifest verification failed" in workflow


def test_runtime_release_acquires_only_cpu_inputs_and_skips_split_assets() -> None:
    workflow = _workflow()

    assert "Validate committed CPU and CUDA lock bundles" in workflow
    assert "fetch_wheelhouse.py --variant cpu" in workflow
    assert "assemble_runtime.py --variant cpu" in workflow
    assert "build-runtime.ps1 -Variant cpu" in workflow
    assert "split-large-assets.ps1" not in workflow
    assert "figuresmith-runtime-cpu" in workflow
    assert "figuresmith-runtime\n" not in workflow


def test_runtime_release_requires_cpu_pack_artifacts() -> None:
    workflow = _workflow()

    for pattern in (
        '"runtime-manifest.json"',
        '"python/python.exe"',
        '"$packName.zip"',
        '"checksums.txt"',
        "Expected exactly one CPU runtime directory",
    ):
        assert pattern in workflow


def test_release_notes_describe_cpu_runtime_and_external_models() -> None:
    workflow = _workflow()

    assert "Models are external" in workflow
    assert "download and import them on the target machine" in workflow
    assert "Self-contained CPU Runtime V1" in workflow
    assert "MSI and Setup installers include" in workflow
    assert "checksum-verified repair asset" in workflow
    assert "publishes the CPU runtime only" in workflow
    assert "not uploaded as a release asset" in workflow


def test_desktop_job_stages_application_pack_before_tauri_build() -> None:
    workflow = _workflow()

    assert "needs: [test, package-runtime]" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "Stage application pack for Tauri resources" in workflow
    assert "apps/desktop/src-tauri/runtime" in workflow
    assert '$manifest.schema -ne 2' in workflow
    assert '$manifest.variant -ne "cpu"' in workflow
    assert "$manifest.runtime_complete -ne $true" in workflow


def test_release_notes_use_version_from_the_same_shell_step() -> None:
    workflow = _workflow()

    assert "export VER" in workflow
    assert "VER: ${{ steps.meta.outputs.version }}" not in workflow
