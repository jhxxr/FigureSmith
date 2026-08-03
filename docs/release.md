# Release checklist — FigureSmith (Windows)

## Before tagging

- [ ] Run `./scripts/ci/sync-version.ps1 -Version X.Y.Z` to align `VERSION`,
      Python, npm, Cargo, and Tauri metadata.
- [ ] Update `CHANGELOG.md`.
- [ ] Run `PYTHONPATH=apps/backend;vendor/autofigure_edit python -m pytest tests -q`.
- [ ] Confirm no model weights are staged.

## Runtime build

The release workflow validates both lock bundles but publishes only the CPU
Runtime V1 pack:

The build machine must use x64 CPython 3.12 and install the archive helper:

```powershell
python -m pip install zstandard
```

```powershell
python scripts/runtime/fetch_wheelhouse.py --variant cpu --lock-root locks --out build/wheelhouse-cpu
python scripts/runtime/assemble_runtime.py --variant cpu --lock-root locks --cache build/source-cache --fetch-sources
./scripts/validate-runtime-locks.ps1 -LockRoot locks -Variant cpu -Wheelhouse build/wheelhouse-cpu
./scripts/build-runtime.ps1 -Variant cpu -Wheelhouse build/wheelhouse-cpu
```

Verify that `runtime-manifest.json` has schema `2`, `variant: "cpu"`,
`runtime_complete: true`, `contains_weights: false`, and
`contains_cache: false`. Run the independent manifest verifier and
`./scripts/ci/assert-no-weights.ps1 -Path dist-runtime`.

The pack must contain embedded `python/python.exe`, the CPU lock files, and no
loose `.whl`, model weight, cache, or user-data files. `checksums.txt` must be
present and match the published ZIP.

## Desktop artifacts

- [ ] Portable contains a real `FigureSmith.exe` and the verified CPU runtime.
- [ ] Setup/MSI does not embed the companion runtime; installation is fail-closed
      until the verified `runtime` directory is placed beside the executable.
- [ ] Model weights are imported by the user and are never uploaded.
- [ ] WebView2 and the Visual C++ runtime remain documented OS prerequisites.

## GitHub Release contents

- `FigureSmith-Setup-x64-*.exe` / `.msi`
- `FigureSmith-Portable-x64-*.zip`
- `FigureSmith-Runtime-Windows-CPU-*.zip`
- `checksums.txt`
- Release notes from `CHANGELOG.md`

The `cu128` lock and assembly path are retained for manual/maintainer builds,
but no CUDA runtime archive is uploaded by this workflow. Model weights,
caches, user outputs, API keys, and session tokens must never be uploaded.
