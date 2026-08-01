# Application Pack and Isolated Python Sidecar

## Goal

Ship an application-only Windows pack and make desktop startup select a
supported user-installed Python only as a base for a dedicated FigureSmith
virtual environment. Do not package CPython, pip, PyTorch, CUDA wheels, SAM3
source, model weights, caches, or user data.

## Requirements

- Copy application/vendor/resources/legal files through the existing safety
  filters and generate an application-only `runtime-manifest.json` with a full
  file inventory and SHA-256 hashes.
- Include `requirements-runtime.txt` and a structured dependency contract that
  separates bootstrap, model, generation, and SVG packages.
- Resolve explicit `FIGURESMITH_PYTHON`, project environments, Windows `py
  -0p`, PATH Python candidates, and known conda/virtualenv roots. Use one
  supported Python 3.10-3.12 only as the base for
  `%LOCALAPPDATA%\FigureSmith\python-env`.
- Install bootstrap packages only into that isolated environment; never modify
  the base Python and never silently fall back to repository Python in release.
- Probe Torch/CUDA in a disposable Python process so broken native packages
  cannot abort the backend process. Model package gaps must be visible without
  preventing the editor from opening after bootstrap succeeds.
- Release mode must use only Tauri Resource application files; missing,
  tampered, wrong-version, embedded-runtime, weight, cache, or extra files fail
  before sidecar spawn.
- Welcome and splash UI must show selected Python, isolated environment path,
  service readiness, model package readiness, GPU state, model import state,
  one-click environment repair, and visual import progress.

## Acceptance Criteria

- [x] Application pack builds without Python executables, wheels, model files,
      or user data.
- [x] Manifest independently verifies application inventory and hashes.
- [x] Release resolver validates application identity/version and refuses source
      fallback.
- [x] Multiple Python candidates are probed and a supported base can create the
      isolated environment without modifying the base.
- [x] Native Torch/CUDA probing is isolated from the backend process.
- [x] Welcome/splash flows expose one-click environment setup and visual model
      import state in English and Chinese.
- [ ] Windows clean artifact smoke confirms isolated environment creation from
      multiple Python installations without modifying the bases.

## Out of Scope

- Bundling CPython or a complete ML runtime in the application pack.
- Automatic installation of Python itself, PyTorch, CUDA, SAM3, or model weights.
- Mutable data migration and model import transaction changes.
