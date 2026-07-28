# Implement: Phase 6 Windows Packaging

## Pre-flight

- [x] Phase 5 `a5a4454`
- [ ] Confirm tauri.conf productName FigureSmith
- [ ] Ensure dist-* in .gitignore

## Checklist

### 1. Version single source

- [ ] `VERSION` or read from tauri.conf + pyproject consistently
- [ ] Document bump process

### 2. build-desktop.ps1

- [ ] Output to `dist-desktop/`
- [ ] Named Setup + Portable zip
- [ ] `-SkipBuild` to only repackage existing target
- [ ] Copy LICENSE + notices into portable root
- [ ] No weight files in zip (assert)

### 3. build-runtime.ps1

- [ ] Create runtime tree under `dist-runtime/`
- [ ] Copy backend/vendor code (exclude large img/case if any)
- [ ] `requirements-runtime.txt` from backend requirements (+ notes for torch CUDA index)
- [ ] `install-deps.ps1`, `README-RUNTIME.md`, `MANIFEST.json` with `contains_weights: false`
- [ ] Exclude weight globs hard

### 4. checksums

- [ ] `scripts/write-checksums.ps1` for a directory
- [ ] Called at end of build scripts

### 5. Docs + CI

- [ ] `docs/release.md`, `docs/phase6-delivery.md`
- [ ] `.github/workflows/release-windows.yml` (draft/manual)
- [ ] CHANGELOG 0.6.0
- [ ] README release section

### 6. Tests

- [ ] `tests/test_packaging_excludes.py` — helper that filters paths never includes weights
- [ ] Existing suite green

## Validation

```powershell
python -m pytest tests -q
./scripts/build-runtime.ps1   # at least skeleton
./scripts/build-desktop.ps1 -SkipBuild  # if no time for full tauri
```

## Review Gates

1. No weights in any dist script copy list
2. Product name FigureSmith
3. checksums produced or documented
4. delivery doc complete

## Defaults

- Full `tauri build` attempted if toolchain present; else scripts + skeleton runtime still ship
- CUDA tag string configurable `cu128` default in script param
