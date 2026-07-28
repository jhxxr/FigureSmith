# Implement: GitHub Actions auto packaging

## Pre-flight

- [x] Existing scripts: build-runtime, build-desktop, write-checksums
- [x] Draft workflow exists
- [ ] Confirm no remote required to commit workflows
- [ ] Keep pytest green

## Checklist

### 1. CI helper scripts

- [ ] `scripts/ci/assert-no-weights.ps1`
  - scan dir + zip members
  - clear error output
- [ ] `scripts/ci/sync-version.ps1`
  - read VERSION
  - patch pyproject, __init__.py, tauri.conf.json
  - `-CheckOnly` mode
- [ ] `scripts/ci/extract-changelog.ps1`
  - extract section for version → file

### 2. Workflows

- [ ] Rewrite `.github/workflows/release-windows.yml`
  - jobs: test, package-runtime, package-desktop, release
  - tag + workflow_dispatch inputs
  - caches for rust/npm/pip where practical
  - assert-no-weights after packs
  - release with gh-release action
- [ ] Add `.github/workflows/ci.yml`
  - on pull_request + push to master/main
  - pytest on windows or ubuntu
  - optional runtime pack (keep light)

### 3. Docs

- [ ] Expand `docs/release.md` with CI auto-release section
- [ ] Short note in `docs/phase6-delivery.md` or README pointing to CI
- [ ] CHANGELOG entry under Unreleased or 0.6.1 patch note for CI

### 4. Validation (local)

- [ ] `python -m pytest tests -q`
- [ ] Dry-run helpers:
  - `pwsh scripts/ci/sync-version.ps1 -CheckOnly`
  - `pwsh scripts/ci/extract-changelog.ps1 -Version (Get-Content VERSION)`
  - build-runtime + assert-no-weights on dist-runtime
- [ ] YAML sanity (no tabs, basic structure)
- [ ] Do **not** require full tauri build in this task unless user asks

### 5. Safety review

- [ ] No upload paths include `**/*.pt` or user model dirs
- [ ] release permissions scoped
- [ ] token/env secrets not echoed

## Validation commands

```powershell
$env:PYTHONPATH = "apps\backend;vendor\autofigure_edit"
python -m pytest tests -q

./scripts/build-runtime.ps1 -SkipZip
./scripts/ci/assert-no-weights.ps1 -Path dist-runtime

./scripts/ci/sync-version.ps1 -CheckOnly
./scripts/ci/extract-changelog.ps1 -Version (Get-Content VERSION -Raw).Trim() -OutFile release-notes.md
```

## Review gates

1. Tag pipeline shape complete in YAML
2. Weight assert exists and is invoked
3. Release job only on tag (or explicit dispatch flag)
4. Docs tell a human how to cut a release in 5 steps
5. Tests still green

## Rollback

- Revert workflow files to previous draft
- Helper scripts are additive under `scripts/ci/`

## Defaults

- package-desktop required for tag release
- workflow_dispatch can skip desktop
- no code signing in v1 of this workflow
