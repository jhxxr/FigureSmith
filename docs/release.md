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
- [ ] Runtime Pack is the dependency-install code pack: the target machine
  installs compatible Python/CUDA/PyTorch/SAM3 dependencies before use
- [ ] SAM3/RMBG model weights remain external; users download and import them
  on the target machine after installing the Runtime Pack
- [ ] Portable archive contains a real `FigureSmith.exe`; missing binaries fail
  the build and never produce a placeholder archive
- [ ] Portable/README states models must be imported by the user
- [ ] Product name is **FigureSmith** (not AutoFigure-Edit)

## GitHub Release contents (allowed)

- `FigureSmith-Setup-x64-*.exe` / `.msi`
- `FigureSmith-Portable-x64-*.zip`
- `FigureSmith-Runtime-Windows-NVIDIA-*.zip`
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
