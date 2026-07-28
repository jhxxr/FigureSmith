"""Repository layout checks for FigureSmith Phase 1 scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    # Vendor
    "vendor/autofigure_edit/autofigure2.py",
    "vendor/autofigure_edit/server.py",
    "vendor/autofigure_edit/requirements.txt",
    "vendor/autofigure_edit/LICENSE",
    "vendor/autofigure_edit/UPSTREAM.md",
    "vendor/autofigure_edit/web/index.html",
    "vendor/autofigure_edit/web/vendor/svg-edit/editor/index.html",
    "vendor/svg_edit/UPSTREAM.md",
    "vendor/svg_edit/editor/index.html",
    # Apps
    "apps/desktop/README.md",
    "apps/backend/main.py",
    "apps/backend/requirements.txt",
    "apps/backend/pyproject.toml",
    "apps/backend/figuresmith/__init__.py",
    "apps/backend/figuresmith/api/__init__.py",
    "apps/backend/figuresmith/pipeline/__init__.py",
    "apps/backend/figuresmith/pipeline/vendor_bridge.py",
    "apps/backend/figuresmith/models/__init__.py",
    "apps/backend/figuresmith/runtime/__init__.py",
    "apps/backend/figuresmith/security/__init__.py",
    # Resources / scripts / docs
    "resources/model-manifest.json",
    "resources/licenses/.gitkeep",
    "resources/notices/.gitkeep",
    "scripts/setup-dev.ps1",
    "scripts/run-backend.ps1",
    "scripts/build-runtime.ps1",
    "scripts/build-desktop.ps1",
    "scripts/verify-offline.ps1",
    "docs/development.md",
    "docs/licenses.md",
    "docs/phase1-delivery.md",
    "docs/phase2-delivery.md",
    "docs/phase3-delivery.md",
    "docs/phase4-delivery.md",
    "docs/phase5-delivery.md",
    "apps/backend/figuresmith/models/manager.py",
    "apps/backend/figuresmith/api/models_routes.py",
    "apps/backend/figuresmith/security/auth.py",
    "apps/backend/figuresmith/security/redact.py",
    "apps/backend/figuresmith/api/system_routes.py",
    "apps/backend/figuresmith/static/desktop-bridge.js",
    "apps/backend/figuresmith/static/ui/welcome.html",
    "apps/backend/figuresmith/static/ui/models.html",
    "apps/desktop/package.json",
    "apps/desktop/src-tauri/Cargo.toml",
    "apps/desktop/src-tauri/tauri.conf.json",
    "apps/desktop/src-tauri/src/lib.rs",
    "apps/desktop/src-tauri/src/sidecar.rs",
    "apps/desktop/src-tauri/src/commands.rs",
    "scripts/import-model.ps1",
    "scripts/run-desktop.ps1",
    # Root compliance / branding
    "LICENSE",
    "NOTICE.md",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "README.md",
    "README_ZH.md",
    ".gitignore",
    ".env.example",
]

WEIGHT_SUFFIXES = (
    ".pt",
    ".pth",
    ".onnx",
    ".safetensors",
    ".gguf",
    ".ckpt",
)


@pytest.mark.parametrize("rel", REQUIRED_PATHS)
def test_required_path_exists(rel: str) -> None:
    path = REPO_ROOT / rel
    assert path.exists(), f"Missing required Phase 1 path: {rel}"


def test_readme_independence_disclaimer() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "FigureSmith is an independent open-source project based on AutoFigure-Edit" in text
    assert "not affiliated with or endorsed by ResearAI" in text
    # Product branding should be FigureSmith, not AutoFigure-Edit as product name
    assert text.strip().startswith("# FigureSmith") or "# FigureSmith" in text.splitlines()[0:5]


def test_readme_zh_branding() -> None:
    text = (REPO_ROOT / "README_ZH.md").read_text(encoding="utf-8")
    assert "图匠" in text or "FigureSmith" in text
    assert "ResearAI" in text


def test_no_accidental_weight_files_in_tracked_trees() -> None:
    """Fail if obvious model weight binaries appear under key trees.

    Skips .venv and typical ignore dirs if present.
    """
    scan_roots = [
        REPO_ROOT / "apps",
        REPO_ROOT / "vendor",
        REPO_ROOT / "resources",
        REPO_ROOT / "scripts",
        REPO_ROOT / "docs",
        REPO_ROOT / "tests",
    ]
    skip_dir_names = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "outputs",
        "uploads",
        ".trellis",
        ".claude",
        ".agents",
        ".codex",
        ".opencode",
    }
    offenders: list[str] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dir_names for part in path.parts):
                continue
            lower = path.name.lower()
            if lower.endswith(WEIGHT_SUFFIXES):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"Unexpected weight files in repo trees: {offenders}"


def test_backend_bind_documented_loopback() -> None:
    main_text = (REPO_ROOT / "apps" / "backend" / "main.py").read_text(encoding="utf-8")
    assert "127.0.0.1" in main_text
    assert 'default=os.environ.get("FIGURESMITH_HOST", "127.0.0.1")' in main_text
    dev_text = (REPO_ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    assert "127.0.0.1" in dev_text


def test_main_default_host_is_loopback() -> None:
    """Parse CLI defaults without starting uvicorn or importing vendor server app body."""
    import importlib.util

    main_path = REPO_ROOT / "apps" / "backend" / "main.py"
    spec = importlib.util.spec_from_file_location("figuresmith_main_under_test", main_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Loading main.py imports vendor_bridge only; it does not call main().
    spec.loader.exec_module(module)
    args = module.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8765
