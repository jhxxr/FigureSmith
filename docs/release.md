# Release checklist — FigureSmith (Windows)

## Before tagging

- [ ] Run `./scripts/ci/sync-version.ps1 -Version X.Y.Z` to align `VERSION`, Python, npm, Cargo, and Tauri metadata
- [ ] Update `CHANGELOG.md`
- [ ] `PYTHONPATH=apps/backend;vendor/autofigure_edit python -m pytest tests -q`
- [ ] Confirm no weights staged: `git status` clean of `*.pt` / `*.safetensors`
- [ ] README still states independence from ResearAI and weight license disclaimer

## Build locally

```powershell
./scripts/build-runtime.ps1
./scripts/build-desktop.ps1   # or -SkipBuild if binary already built
```

## Verify artifacts

- [ ] `dist-runtime/**/MANIFEST.json` and `runtime-manifest.json` have
  `"contains_weights": false` and `"contains_cache": false` in the structured
  runtime manifest; product/version match `FigureSmith` and `VERSION`
- [ ] No `*.pt` / `*.safetensors` under `dist-runtime` or `dist-desktop`
- [ ] `checksums.txt` present and hashes match
- [ ] Runtime manifest declares `application_only: true`, `python_required: external`, and no weights/cache/dependency artifacts
- [ ] The application pack contains `requirements-runtime.txt`, `requirements-bootstrap.txt`, `requirements-models.txt`, and the dependency contract; it does not contain `python.exe`, Python DLLs, wheels, PyTorch, CUDA, SAM3 source, model weights, or user data
- [ ] Release notes tell users to provide Python 3.10-3.12 as a base; FigureSmith creates `%LOCALAPPDATA%\FigureSmith\python-env` and installs bootstrap packages there without changing the base environment
- [ ] Desktop resolver scans multiple Python installations, creates/repairs the isolated environment, reports missing model packages, and continues to the UI when only model packages are missing
- [ ] The target machine has a supported NVIDIA driver, WebView2, and Visual C++
  runtime; these OS prerequisites are not bundled by FigureSmith
- [ ] Portable archive contains a real `FigureSmith.exe`; missing binaries fail
  the build and never produce a placeholder archive
- [ ] Portable/README states models must be imported by the user
- [ ] Product name is **FigureSmith** (not AutoFigure-Edit)

## GitHub Release contents (allowed)

- `FigureSmith-Setup-x64-*.exe` / `.msi`
- `FigureSmith-Portable-x64-*.zip`
- `FigureSmith-Runtime-Windows-*.zip` (application code + dependency guidance only)
- `checksums.txt`
- Release notes (from CHANGELOG)

## Never upload

- `sam3.pt`, RMBG weights, HF caches, user `outputs/`, API keys, session tokens

## Optional signing

If a certificate is available:

```text
signtool sign /fd SHA256 /a path\to\FigureSmith-Setup-x64-*.exe
```

Skip silently when no cert is configured.
