# Release checklist — FigureSmith (Windows)

## Before tagging

- [ ] Bump root `VERSION`, `apps/backend/figuresmith/__init__.py`, `apps/backend/pyproject.toml`, `apps/desktop/src-tauri/tauri.conf.json`
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

- [ ] `dist-runtime/**/MANIFEST.json` has `"contains_weights": false`
- [ ] No `*.pt` / `*.safetensors` under `dist-runtime` or `dist-desktop`
- [ ] `checksums.txt` present and hashes match
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
