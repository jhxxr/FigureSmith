# Runtime V1 Implementation Plan

Ordered. Each stage ends green before the next starts. Stages 1-3 are
prerequisites that unblock everything else and carry the highest uncertainty.

## Stage 1 — Unblock the packaging gates

- [x] Fix `api/system_routes.py:53` to resolve `dependencies.json` from
      `figuresmith/runtime/`, and stop swallowing the read error silently — a
      missing contract must log, not degrade to a 7-entry default.
- [x] Align the two dependency-contract loaders: Rust (`sidecar.rs:701`)
      requires `distribution`/`import`/`scope`, Python additionally requires
      `requirement`. Pick one shape and assert it in both.
- [x] Rewrite `is_weight_file` with a `site_packages_root` context parameter;
      drop the `python312._pth` special case. Add tests for: `sam3.pt` refused,
      `distutils-precedence.pth` allowed under site-packages, `nvidia` `.bin`
      allowed under site-packages, `.bin` outside site-packages refused.

Validation: `python -m pytest tests/test_packaging_excludes.py
tests/test_dependency_contract.py -q`, plus a new test asserting the doctor
reports all 19 contract entries.

Done in 86b9d30. The two new dependency-contract tests were confirmed to fail
against the old path before the fix. Loader drift is reported as a warning
rather than unified, because the Rust side legitimately needs only three
fields; forcing one shape would have been a wider change than the bug required.

## Stage 2 — Widen the lock validator

- [x] `locks.py:78` — accept `cuda` in `{"cpu", "cu128"}` instead of requiring
      `cu128`. Keep every other constraint unchanged.
- [x] Add a lock→pip requirements emitter producing `==` pins with
      `--hash=sha256:` lines.
- [x] Extend `tests/test_runtime_locks.py` for the CPU variant and the emitter,
      including a negative test that a range or sdist is still rejected.

Validation: `python -m pytest tests/test_runtime_locks.py -q`.

Done in 86b9d30. `_header` now returns the variant and `validate_lock_bundle`
rejects a bundle whose three locks disagree, plus an ambiguous lock root that
holds both variants. CLI gained `--variant` and `--emit-requirements`, verified
end-to-end against a generated CPU bundle.

## Stage 3 — Acquire and commit real locks

- [x] Pin the CPython 3.12 Windows x64 embeddable version + SHA-256.
- [x] Resolve the full dependency closure on Windows x64 for both variants;
      capture exact versions, wheel URLs, digests, tags, licenses.
- [x] Pin the native cairo DLL chain (12 MSYS2 packages) by SHA-256.
- [ ] Commit `locks/requirements-win-py312-{cpu,cu128}.lock.json` and
      `sources-{cpu,cu128}.lock.json`.
- [ ] `wheelhouse-manifest.json` — CI produces it, since only CI downloads.
- [x] Run the validator against generated locks until clean.

Done in 93e7c10 (resolver + guards). Locks generate and validate but are not
yet committed: the cu128 pins move whenever the index advances, so committing
them should coincide with CI being able to verify a full download against them.

Two defects surfaced and were fixed rather than worked around:

- The first cu128 closure was byte-identical to CPU. Unbounded `torch>=2.1` plus
  pip's cross-index version preference resolved PyPI's newer CPU build while the
  lock still claimed cu128. `VARIANT_CONSTRAINTS` + `_assert_variant_is_real()`
  make that fail the resolve instead of shipping.
- pip 24.0 could not resolve the cu128 index at all (5 min, no report, 1.8 GB
  cached); pip 26.2 does it in 3.45 s. `_assert_pip_is_new_enough()` enforces the
  floor. The same pip bug explained 28 spurious UNKNOWN licenses.

MSYS2 filenames drift — 8 of 12 hand-written pins were already stale. Use
`--refresh-msys2` rather than editing them by hand.

## Stage 4 — Manifest schema 2

- [x] Bump `MANIFEST_SCHEMA` to 2; add `variant`, `python`, `locks`; delete the
      `application_only`/`python_required` assertions and their schema-1
      branches.
- [x] Allow the `python/` tree in `_iter_runtime_files`; keep `.whl` forbidden
      in the shipped pack.
- [x] Update `tests/test_runtime_manifest.py` for schema 2.

Validation: `python -m pytest tests/test_runtime_manifest.py -q`.

Done. `require_complete` is gone — a schema 2 manifest is self-contained by
definition, so the flag had one legal value. `runtime_complete=True`,
`variant`, and `python.version` are now asserted, and a schema 1 manifest is
refused outright.

Weight detection is scoped to `python/Lib/site-packages` via the
`site_packages_root` parameter added in Stage 1, so an installed package's
`.pth` hooks and non-model `.bin` payload ship while a checkpoint is still
refused anywhere in the pack. `__pycache__` remains forbidden: `.pyc` files
embed absolute source paths and mtimes, so shipping them would break
reproducibility and contradict `contains_cache=false`. Assembly must strip them.

### Known breakage carried into Stage 5

`build-runtime.ps1:122,171` still calls `write_runtime_manifest(...,
runtime_complete=False)`, which now raises `TypeError`. The script is broken
until Stage 5 rewrites it. Verified directly rather than assumed.

**No test caught this.** `test_runtime_release_workflow_contract.py` and
`test_desktop_packaging_contract.py` assert on the *text* of the `.ps1`/`.yml`
files, not on whether the calls they contain still work, so 305 tests pass over
a build script that cannot run. The root cause is that manifest generation is
embedded as Python source inside PowerShell `-c` strings, which no type checker
or test can see.

Stage 5 should move manifest generation into a real Python entry point invoked
with plain arguments, which removes this entire class of invisible breakage
rather than re-creating it in a new script.

## Stage 5 — Offline assembly

- [ ] Add the acquire script (network on) and the assemble script (network off):
      expand pinned CPython, `pip install --no-index --find-links wheelhouse
      --require-hashes --no-deps --target python/Lib/site-packages`.
- [ ] Write `python312._pth` with `import site` and no user-site.
- [ ] Rewrite `build-runtime.ps1`: drop the `python.exe`/`*.dll`/`*.whl`
      rejection (`:185`), keep the weight rejection, emit per-variant packs.
- [ ] Assemble twice and diff digests to prove reproducibility.

Validation: two assemblies produce identical digests for all non-timestamp
files; `verify_runtime_manifest` passes on both.

## Stage 6 — Sidecar and desktop

- [ ] Point release-mode resolution at the packed `python/python.exe`; delete
      the managed-venv creation and `pip install` path (`sidecar.rs:885-947`)
      from release mode. Keep an explicit dev-mode resolver.
- [ ] Verify manifest digests before spawn; fail closed on mismatch.
- [ ] Resolve the installer payload: shell installs without the cu128 tree and
      locates a runtime pack beside it; Portable carries a full variant.
- [ ] Update the splash/welcome UI — the "install model dependencies" prompt and
      copyable pip command are obsolete for a pre-installed pack.

Validation: launch from a path with spaces and non-ASCII characters; confirm no
`pip` process spawns and no network egress occurs.

## Stage 7 — CI, release, measurement

- [ ] Wire `validate-runtime-locks.ps1` into `ci.yml`.
- [ ] Wire `split-large-assets.ps1` into `release-windows.yml`; publish the part
      manifest and joiner; verify a reassembly in CI.
- [ ] Rewrite the workflow's manifest assertions and
      `tests/test_runtime_release_workflow_contract.py` /
      `tests/test_desktop_packaging_contract.py` for schema 2.
- [ ] Clean-runner smoke: no Python installed, `PATH` Python removed, network
      off; boot to authenticated ready, probe health/model/system APIs, shut
      down with no surviving process.
- [ ] Negative smoke: corrupt a runtime file, confirm fail-closed.
- [ ] Record size/time/disk/part-count per variant into task research.

Validation: full `python -m pytest tests -q`, then the clean-runner job.

## Stage 8 — Docs

- [ ] Rewrite `docs/runtime-locks.md`, `docs/release.md`, `README*.md`, and the
      release-notes block in `release-windows.yml`, which currently instruct the
      user to supply Python 3.10-3.12.
- [ ] CHANGELOG entry stating the reversal of the 0.6.2 decision and the reason.

## Review gates

- After Stage 3: locks reviewed before any assembly work depends on them.
- After Stage 5: reproducibility proven before the sidecar is rewired.
- After Stage 7: measurement reviewed before publishing.

## Rollback points

Each stage is an independent commit. Stages 1-2 are safe improvements that hold
value even if Runtime V1 is abandoned. Stage 4 onward changes the shipped
contract; revert to the 0.6.2 application-only path if the measurement gate goes
red and no reviewed delivery decision follows.
