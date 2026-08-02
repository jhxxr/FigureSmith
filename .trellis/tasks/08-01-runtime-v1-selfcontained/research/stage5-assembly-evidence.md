# Stage 5 — Runtime V1 assembly evidence

## Final input bundles

| Variant | Packages / wheels | Source archives | Wheelhouse |
|---|---:|---:|---:|
| CPU | 69 | 18 | 188 MiB |
| cu128 | 69 | 18 | 2.7 GiB |

Both pass `validate_lock_bundle(..., wheelhouse_root=..., variant=...)` including
physical wheel inventory, byte sizes, and SHA-256.

## Assembled runtimes

| Variant | Manifest files | Assembled size | Torch result |
|---|---:|---:|---|
| CPU | 23,476 | 828 MiB | `2.13.0+cpu`; CUDA false |
| cu128 | 23,250 | 4.5 GiB | `2.11.0+cu128`; CUDA 12.8; CUDA true |

The current host has a supported GPU, so cu128 import was exercised rather than
only checking wheel metadata.

## Reproducibility

Two fresh CPU assemblies from the same committed locks/source cache/wheelhouse
produced:

```
manifest-bytes-identical: True
manifest-objects-identical: True
file_count: 23476
lock digests: requirements, sources, wheelhouse
python source: 3.12.10 / 4acbed6dd1c744b0...
```

pip-generated Windows console launchers are nondeterministic (their executable
stub bytes differ), and each `dist-info/RECORD` repeats those differing hashes.
They are unused by FigureSmith, which invokes modules through its own embedded
interpreter. Removing 24 launchers and 69 RECORD files made the assemblies
byte-identical without deleting importable package metadata.

## Isolation and native import evidence

With system Python absent from PATH and `PYTHONPATH`, `PYTHONHOME`, and
`VIRTUAL_ENV` cleared:

```
executable = <pack>/python/python.exe
isolated = 1
no_user_site = 1
torch = 2.13.0+cpu
cairosvg = 2.9.0
fastapi = 0.141.1
```

The high-fidelity SVG renderer passed an SVG→PNG smoke containing a gradient and
transparency. The final native chain is 19 DLLs, not the initial 14-DLL estimate:
real LoadLibrary probes exposed transitive `libglib`, `libintl`,
`libwinpthread`, `libiconv`, and `libpcre2` requirements.

The cu128 runtime on this machine reports:

```
torch = 2.11.0+cu128
cuda_available = True
cuda_build = 12.8
```

## Offline boundary

The assembler performs no network I/O. Source acquisition is a separate
`--fetch-sources` command. A clean empty cache failed before publication with:

```
assembly failed: pinned source archive is missing from the offline cache
exit = 2
```

The wheel install uses:

```
--no-index --find-links <wheelhouse> --require-hashes --no-deps
--no-compile --only-binary :all: --python-version 3.12
--platform win_amd64 --abi cp312 --target <site-packages>
```

## Bugs found by real assembly

1. **CPU/CUDA wheelhouse manifest collision.** A shared filename let one variant
   overwrite the other. All three lock files are now variant-specific.
2. **Percent-escaped CUDA wheel filename.** The resolver stored `%2B` literally,
   so pip could not match `torch==2.11.0+cu128`. Resolver now URL-decodes the
   basename; a regression covers it.
3. **Incomplete cairo closure.** Static inspection found 14 DLLs, but real
   LoadLibrary exposed five more transitive dependencies. All are pinned.
4. **`uploads` false positive.** openai legitimately ships Python namespaces
   named `resources/uploads` and `types/uploads`; mutable-data names are now
   forbidden outside site-packages while real caches stay forbidden everywhere.
5. **MAX_PATH at four boundaries.** Direct long-path pip install, post-rename
   manifest traversal, post-rename checksumming, and deletion of an old display
   tree each failed independently. All recursive operations now happen under a
   short staging path; old packs are renamed short before recursive deletion.
6. **Partial publication.** ZIPs previously wrote directly to their final name
   and checksum failures happened after a publishable tree existed. Publication
   is now transactional with `.partial`, staging, cleanup, and a `$published`
   guard.
7. **Import mutates immutable pack.** `-I` ignores
   `PYTHONDONTWRITEBYTECODE`; `sitecustomize.py` executes too late to prevent its
   own and `_distutils_hack` bytecode. Stage 6 sidecar must add `-B` to the
   embedded Python invocation. Direct probes used `-B`; manifest remained valid.

## Validation

- Focused Runtime V1 tests: 30 passed after final URL-decoding fix.
- Full Python suite: **313 passed**, one existing Starlette/httpx deprecation.
- Python compile: pass.
- `git diff --check`: pass.
- CPU and cu128 lock-bundle validation: pass.
- CPU deterministic double assembly: pass.
- CPU and GPU embedded-interpreter import probes: pass.
