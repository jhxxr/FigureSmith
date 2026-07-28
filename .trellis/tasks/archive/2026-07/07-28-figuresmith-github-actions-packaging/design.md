# Design: GitHub Actions auto packaging

## Overview

```text
tag v0.6.1 / workflow_dispatch
        │
        ▼
   ┌─────────┐
   │  test   │  pytest + version sanity
   └────┬────┘
        │
   ┌────┴─────────────────────┐
   ▼                          ▼
package-runtime          package-desktop
(build-runtime.ps1)      (build-desktop.ps1)
assert-no-weights        assert-no-weights
upload-artifact          upload-artifact
   │                          │
   └──────────┬───────────────┘
              ▼
         release (tag only)
         download artifacts
         gh release create
         attach zips/exe + checksums
```

## Triggers

| Event | Behavior |
|-------|----------|
| `push` tags `v*` | full pipeline + GitHub Release |
| `workflow_dispatch` | selectable skip_desktop / create_release |
| `pull_request` / `push` to default branch | `ci.yml` only: test (+ optional runtime) |

## Jobs

### test
- `windows-latest`（与打包同 OS，减少路径差异）或 `ubuntu-latest` 更快测纯 Python  
  **Decision:** test 用 `windows-latest` 与 packaging 一致，避免 bash/pwsh 差异；若过慢可改为 ubuntu 仅测。
- Setup Python 3.12
- Install backend requirements（允许无 CUDA；现有 tests 不依赖 GPU）
- `PYTHONPATH=apps/backend;vendor/autofigure_edit python -m pytest tests -q`
- Optional: run `sync-version -CheckOnly` if tag

### package-runtime
- needs: test
- `./scripts/build-runtime.ps1`
- `./scripts/ci/assert-no-weights.ps1 -Path dist-runtime`
- Upload:
  - `dist-runtime/FigureSmith-Runtime-*.zip`
  - `dist-runtime/checksums.txt`
  - `dist-runtime/**/MANIFEST.json`（可选）

### package-desktop
- needs: test
- if: not skip_desktop
- setup-node 20, rust-toolchain stable, rust-cache, WebView2 implicit
- `./scripts/ci/sync-version.ps1`（从 VERSION 写 tauri.conf / pyproject）
- `./scripts/build-desktop.ps1`
- `./scripts/ci/assert-no-weights.ps1 -Path dist-desktop`
- Upload Setup/Portable/checksums
- timeout-minutes: 180

### release
- needs: [package-runtime, package-desktop]  
  （若 skip_desktop，needs 仅 runtime — 用条件 job 或 always 下载存在的 artifacts）
- if: tag `v*` OR (dispatch && create_release)
- permissions: contents: write
- checkout + download-artifact
- `extract-changelog.ps1` → `release-notes.md`
- softprops/action-gh-release 或 gh cli
- fail if no files

## Helper scripts

### assert-no-weights.ps1
- Recurse files under Path
- Fail on extensions: `.pt .pth .onnx .safetensors .gguf .ckpt .h5 .pb`
- Also peek zip entries (System.IO.Compression) for same suffixes
- Exit 1 with file list

### sync-version.ps1
- Read root `VERSION`
- Update:
  - `apps/backend/pyproject.toml` version
  - `apps/backend/figuresmith/__init__.py` `__version__`
  - `apps/desktop/src-tauri/tauri.conf.json` version
- `-CheckOnly`: verify equality, used on tag

### extract-changelog.ps1
- Parse `CHANGELOG.md` for `## [X.Y.Z]` section matching VERSION
- Write markdown file for release body
- Fallback: generic blurb + link to CHANGELOG

### assert-version-tag.ps1 (optional inline step)
- `GITHUB_REF_NAME` = `v0.6.1` → strip v → must equal VERSION

## Caching

| Cache | Key inputs |
|-------|------------|
| cargo | `Cargo.lock` hash + os |
| npm | `package-lock.json` |
| pip | `requirements.txt` hash |

Do **not** cache `data/`, `models/`, user outputs.

## Security

- Default `permissions: contents: read`
- Release job only: `contents: write`
- No secrets required for basic release (GITHUB_TOKEN)
- Future signing: `FIGSMITH_CODE_SIGN_*` secrets, optional step

## Failure modes

| Failure | Handling |
|---------|----------|
| pytest fail | stop all |
| weight found | fail job, no release |
| tauri timeout | desktop job red; optional dispatch skip_desktop still can release runtime-only if explicitly allowed — **default: tag requires both** |
| version mismatch on tag | fail early in test/release |

## Compatibility with local scripts

CI calls the same `build-runtime.ps1` / `build-desktop.ps1` / `write-checksums.ps1` so local and CI stay one path.

## Docs

Update `docs/release.md`:
- How to cut a release (bump VERSION, changelog, tag, push)
- What Actions produces
- Manual dispatch knobs
- No-weights policy
