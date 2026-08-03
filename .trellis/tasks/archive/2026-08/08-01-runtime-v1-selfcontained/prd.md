# Runtime V1 — Self-Contained Windows Distribution

## Goal

Ship a Windows runtime that starts with no system Python, no pip, and no network
access. A given FigureSmith version must install to a byte-identical dependency
set regardless of install date. Model weights stay external.

## Background

0.6.2 replaced the self-contained runtime with "user-supplied Python 3.10-3.12 +
online pip". That makes the shipped dependency set a function of install date:
`requirements-models.txt` pins only ranges (`torch>=2.1`, `transformers>=4.39,<5.0`),
so two installs of the same FigureSmith version can resolve different Torch,
Transformers, and CUDA builds. This task reverses that decision.

Reusable assets already in the repo:

- `figuresmith/runtime/locks.py` — full lock/wheelhouse validator with SHA-256,
  HTTPS-only, exact-version, no-sdist enforcement. Never fed a real lock file.
- `scripts/validate-runtime-locks.ps1` — CLI wrapper, wired to no workflow.
- `scripts/ci/split-large-assets.ps1` — 1.9 GB splitter + self-verifying joiner,
  wired to no workflow.
- `tests/test_runtime_locks.py` — 169 lines of schema contract tests.

Blockers that must be resolved, not worked around:

- `runtime/packaging.py:37` treats `python312._pth` as a weight file and
  `.pth`/`.bin` as weight suffixes. A pre-installed tree legitimately contains
  `python312._pth`, `distutils-precedence.pth`, and non-weight `.bin` payloads
  in NVIDIA/CUDA wheels. Suffix-only detection cannot ship this pack.
- `runtime/manifest.py` hard-asserts `application_only=true` and
  `python_required="external"`; `build-runtime.ps1:185` throws on any
  `python.exe`/`python*.dll`/`*.whl`. These gates invert under Runtime V1.
- `api/system_routes.py:53` resolves `dependencies.json` next to
  `figuresmith/api/`, but the file is in `figuresmith/runtime/`. The read fails,
  the exception is swallowed, and the dependency doctor silently reports the
  7-entry `_DEFAULT_DEPENDENCIES` instead of the real 19-entry contract.
- Tauri `bundle.resources = ["runtime"]` embeds the pack in the installer. A
  cu128 payload cannot ride inside an NSIS/MSI installer at that size.

## Requirements

### R1. Frozen inputs

- Pin CPython 3.12 Windows x64 embeddable by exact version + SHA-256.
- Pin every wheel to an exact version, HTTPS URL, and SHA-256. No ranges, no
  sdists, no target-machine compilation.
- Commit `requirements-win-py312-{cpu,cu128}.lock.json`, `sources.lock.json`,
  and a `wheelhouse-manifest.json` per variant, all passing `locks.py`.
- Emit a pip-consumable `--require-hashes` requirements file derived from each
  lock, so pip itself enforces the digests during assembly.
- Record license + provenance for every locked distribution.

### R2. Pre-installed runtime tree

- Assembly installs the wheelhouse into `python/Lib/site-packages` at build
  time. The shipped pack contains resolved packages, not wheels.
- Configure `python312._pth` for an isolated interpreter: no user-site, no
  `PATH`/registry Python, no repo influence, `site-packages` importable so
  native extensions load.
- First launch spawns `python/python.exe` directly. No pip, no venv creation, no
  dependency install, no network.
- Exclude model weights, HF caches, user data, keys, and generated output.

### R3. CPU / CUDA variants

- Build two variants from one assembly path: `cpu` and `cu128`.
- `runtime-manifest.json` records `variant`, pinned Python version + hash, and
  the digest of each consumed lock.
- Both variants share identical application-file digests.

### R4. Release channel

- Wire `split-large-assets.ps1` into `release-windows.yml`, splitting at
  1.9 GB with the self-verifying joiner and part manifest published alongside.
- Publish per-variant archives + `checksums.txt`. Reassembly must verify each
  part digest and the reconstructed whole before use.
- Desktop installer must not embed the cu128 pack; decide and implement the
  installer's runtime delivery path explicitly.

### R5. Integrity at rest and at launch

- Replace suffix-only weight detection with manifest-aware allowlisting so
  legitimate `.pth`/`.bin` package files ship while weights stay blocked.
- Verify manifest digests before the sidecar spawns; a mismatch fails closed.
- Fix the `dependencies.json` path bug and assert the doctor reports 19 entries.

## Acceptance Criteria

- [ ] Assembling twice from the committed locks yields identical file digests
      for every non-timestamp file.
- [ ] Manifest verification covers every shipped file and reports
      `contains_weights: false`; an independent scan finds no weights or caches.
- [ ] The pack boots the backend to authenticated ready state on a clean Windows
      runner with no Python installed, `PATH` Python removed, and network off.
- [ ] The interpreter ignores user-site, registry, and current-directory
      packages; `torch` and native DLLs import from the shipped tree only.
- [ ] cu128 imports Torch and reports CUDA availability on a GPU runner; CPU
      variant runs Torch on CPU with no CUDA wheels present.
- [ ] Split assets reassemble to the original digest via the published joiner.
- [ ] A corrupted or removed runtime file blocks launch before navigation and
      produces no publishable artifact.
- [ ] Measured compressed/uncompressed size, build time, and disk peak are
      recorded per variant.

## Out of Scope

- SAM3/RMBG weights and model caches; still user-imported.
- NVIDIA driver redistribution.
- macOS/Linux artifacts, code signing, auto-update, delta patches.
- GPU certification across every card; representative smoke only.

## Open Decision

If the measured cu128 payload cannot ride the chosen channel even after
splitting, publishing blocks for a reviewed delivery decision. Dependencies are
never silently dropped to fit a size limit.
