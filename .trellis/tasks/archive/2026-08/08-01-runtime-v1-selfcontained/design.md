# Runtime V1 Design

## Shipped layout

```
FigureSmith-Runtime-Windows-CPU-<version>/  # published artifact
  python/
    python.exe, python312.dll, python312.zip
    python312._pth              # isolation policy
    Lib/site-packages/          # resolved packages, installed at build time
  app/backend/                  # figuresmith package + main.py
  app/vendor/autofigure_edit/, app/vendor/svg_edit/
  app/resources/                # no models/ subtree
  locks/                        # the exact locks this pack was built from
  LICENSE, NOTICE.md, THIRD_PARTY_NOTICES.md, VERSION
  runtime-manifest.json         # schema 2, full SHA-256 inventory
```

No `python -m pip`, no wheels, no venv, no `requirements-models.txt` install step
on the target machine. The release sidecar invokes embedded Python with `-B` so
imports cannot create bytecode caches inside the immutable manifested tree.

## Interpreter isolation

`python312._pth` is the whole isolation mechanism for an embeddable tree. It
replaces normal `site` discovery:

```
python312.zip
.
Lib\site-packages
import site
```

`import site` is required — without it `site-packages` is not processed and
native extensions that rely on `.pth` hooks (torch, numpy) fail to import. The
presence of `python312._pth` itself suppresses user-site and registry lookups,
which is what R2 needs. The sidecar additionally scrubs `PYTHONPATH`/`PYTHONHOME`
from the child env; `sidecar.rs:340 scrub_python_path` already does this.

Consequence for `packaging.py`: `python312._pth` must ship, so the current
`is_weight_file` special case that classifies it as a weight is removed.

## Lock model

Three committed artifacts per variant, all validated by the existing `locks.py`:

- `requirements-win-py312-<variant>.lock.json` — exact version, wheel filename,
  HTTPS URL, SHA-256, wheel tags, license per distribution.
- `sources-<variant>.lock.json` — CPython embeddable archive, the MSYS2 cairo
  DLL chain, and any non-wheel input, each with SHA-256; git sources need a full
  40-hex commit.
- `wheelhouse-<variant>.manifest.json` — inventory of the acquired `.whl` files.

### Native libraries

`cairosvg` reaches outside the wheel for `libcairo-2.dll` through `cairocffi`,
which `dlopen`s a real DLL. No PyPI wheel supplies one. Measured closure of the
MSYS2 `mingw-w64-x86_64-cairo` package: **14 DLLs, 8.3 MB**, from ~10 packages
(see `research/cairosvg-decision.md`).

These ship in the pack under `python/Lib/site-packages/cairocffi/` or a
dedicated `native/` directory on the DLL search path, and each is pinned in
`sources.lock.json` with a SHA-256 and license record. This is a second supply
chain — distro packages, not PyPI, no per-file signing — and is accepted
deliberately: `svglib` renders the same cairo but through a weaker SVG parser
that silently drops embedded base64 figures, which is what the optimizer's LLM
vision comparison consumes.

`sources.lock.json` entries for these use `kind: "archive"` with the MSYS2
package URL and its `.pkg.tar.zst` digest; assembly extracts the specific DLLs
named in the lock rather than the whole package.

`locks.py` currently hard-requires `runtime.cuda == "cu128"` (`locks.py:78`).
That check widens to an allowlist of `{"cpu", "cu128"}` so the CPU variant can
use the same validator. This is the only semantic change to the validator; every
other guarantee (exact versions, HTTPS, no sdists, no weight-suffix wheels)
stays as written.

A derived `*.requirements.txt` with `==` pins and `--hash=sha256:` lines is
generated from each lock. Assembly feeds that to pip so pip enforces digests
too, rather than trusting our own pre-check alone.

## Acquisition vs assembly

Split into two phases with a hard boundary:

- **Acquire** (network allowed, CI or maintainer): resolve, download wheels into
  `wheelhouse/`, write the three locks, verify digests.
- **Assemble** (network denied): expand the pinned CPython embeddable, then
  `pip install --no-index --find-links wheelhouse --require-hashes --no-deps
  --target python/Lib/site-packages -r <derived requirements>`.

`--no-deps` is deliberate: the lock is already fully resolved, so pip must not
re-solve. `--no-index` plus a denied network makes any unlocked fetch fail
loudly instead of silently pulling a fresh build.

Assembly runs the manifest writer last, then verifies it immediately.

## Manifest schema 2

Schema 1 encodes the 0.6.2 stance (`application_only`, `python_required:
external`) and is asserted in three places: `manifest.py`, `build-runtime.ps1`,
and `release-windows.yml`. Schema 2 replaces those fields:

```json
{
  "schema": 2,
  "variant": "cu128",
  "runtime_complete": true,
  "python": { "version": "3.12.x", "source_sha256": "..." },
  "locks": { "requirements": "<sha256>", "sources": "<sha256>",
             "wheelhouse": "<sha256>" },
  "contains_weights": false,
  "contains_cache": false,
  "files": [ { "path": "...", "size_bytes": 0, "sha256": "..." } ]
}
```

Keeping schema 1 readable is not required — no released pack is consumed by a
newer client. `MANIFEST_SCHEMA` bumps and the schema-1 branches are deleted
rather than kept as dead compatibility code.

## Weight exclusion, manifest-aware

Suffix-only detection is wrong in both directions here. CUDA/NVIDIA wheels ship
non-weight `.bin` payloads and site-packages ships `.pth` hooks, while a real
`sam3.pt` must still be refused.

Rule: inside `python/Lib/site-packages/`, a `.pth`/`.bin` file is allowed and
recorded in the manifest. Outside it, the existing weight suffixes stay fatal.
Anything matching a weight suffix under `app/resources/models/` or the model
staging paths stays fatal regardless. `is_weight_file` gains an explicit
`site_packages_root` context parameter instead of guessing from the name.

## Release channel

`cu128` uncompressed is expected in the 4-6 GB range, dominated by torch plus
the `nvidia-*` CUDA runtime wheels; GitHub's per-asset ceiling is 2 GB.
The measured compressed size is 2.68 GiB, so it is intentionally excluded from
the selected release channel. GitHub Releases publish the CPU pack only; its
0.23 GiB compressed archive fits as one asset. `split-large-assets.ps1` remains
available but unwired.

Desktop installer: `bundle.resources = ["runtime"]` does not carry the runtime
tree. The installer ships the application shell and resolves a verified CPU
runtime pack installed beside it; the Portable zip carries the same CPU
variant. The cu128 assembly path remains a maintainer/manual path until a
separate GPU delivery design is approved.

## Measurement gate

Record per variant: wheelhouse size, assembled tree size, compressed size, stage
disk peak, wall time, and part count. A red measurement blocks publishing and
triggers plan review — it does not silently drop a dependency.

## Rollback

The 0.6.2 application-only path is one revert away in git history. Locks change
only by explicit regeneration, and the previous lock set stays in version
control so a bad regeneration can be reverted without re-resolving.
