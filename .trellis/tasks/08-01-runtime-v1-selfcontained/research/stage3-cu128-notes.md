# Stage 3 — cu128 resolution notes

## The bug this stage exists to catch, caught live

First cu128 resolution produced a closure **byte-identical to the CPU variant**:

```
cpu:  69 packages     cu128: 69 packages
cu128 nvidia-* packages: []
cu128 torch==2.13.0   from files.pythonhosted.org
differing packages: NONE -- identical closures
```

Root cause: `requirements-models.txt` declares `torch>=2.1`, unbounded. pip
merges `--index-url` (cu128) with `--extra-index-url` (PyPI) and picks the
highest version across both. Measured at resolution time:

- PyPI: `torch 2.13.0` (no CUDA wheels)
- cu128 index: tops out at `torch 2.11.0+cu128`, `torchvision 0.26.0+cu128`

So pip preferred PyPI's newer build and the "CUDA" pack silently became
CPU-only. Nothing in the lock file recorded that it had happened — the variant
stamp still said `cu128`.

This is exactly the install-date drift Runtime V1 exists to eliminate, and it
would have shipped as a pack labelled cu128 that cannot use a GPU.

Two fixes, both required:

1. `VARIANT_CONSTRAINTS` pins `torch==2.11.0+cu128` and
   `torchvision==0.26.0+cu128`, appended after the requirements files so they
   override the ranges.
2. `_assert_variant_is_real()` refuses to write a lock where torch/torchvision
   lack a `+cu128` local version or did not come from `download.pytorch.org`.
   The CPU variant gets the mirror-image assertion: no `+cu` builds, no PyTorch
   index URLs. A silent degradation now fails the resolve instead of producing a
   mislabelled lock.

## pip version decides whether cu128 is resolvable at all

Same command, same index, two pip versions:

| pip | result |
|---|---|
| 24.0 | no report after **5 minutes**, 1.8 GB pulled into the http cache |
| 26.2 | complete report in **3.45 seconds** |

An 87× difference. The cu128 index does advertise PEP 658 metadata on every
wheel — `data-core-metadata` and `data-dist-info-metadata` are present, and
`...whl.metadata` returns 200 in ~1 s — but pip 24.0 fetches the wheel body
anyway. Since the Windows torch wheel is 2.56 GB, resolving its dependencies
meant downloading it.

Neither the index nor network latency was at fault: the index page is 89 KB and
loads in 1.05 s; the metadata file is 29,875 bytes and loads in 1.18 s.

`_assert_pip_is_new_enough()` now fails fast with the upgrade command when pip
is below 26.2. 26.2 is the lowest version measured to work; 24.0 is measured
broken; versions between are untested, so the floor sits at the verified value.

Full cu128 resolve with pip 26.2, including hashing all 13 sources: **1m 34s**.
That is well inside an interactive budget, so cu128 no longer has to be deferred
to CI purely on cost.

## The 28 UNKNOWN licenses were a pip artifact

The first CPU resolve recorded 28 distributions as `UNKNOWN`, including torch,
numpy, fastapi, pillow, and cryptography. Re-resolving with pip 26.2 produced
**zero** UNKNOWN licenses. The metadata was always there; pip 24.0's report
simply did not carry it. No manual license backfill is needed.

## Zero nvidia-* wheels is correct on Windows

Both variants resolved with no `nvidia-*` packages, which initially looked like
the same silent-degradation bug. It is not. The Windows cu128 torch wheel
declares no NVIDIA dependencies at all:

```
Requires-Dist: filelock, typing-extensions>=4.10.0, setuptools<82,
               sympy>=1.13.3, networkx>=2.5.1, jinja2, fsspec>=0.8.5
nvidia-* dependencies: 0
wheel size: 2.56 GB
```

CUDA is bundled inside the wheel on Windows rather than split into separate
`nvidia-*` distributions as on Linux. The variant assertion therefore checks the
`+cu128` local version and the PyTorch host, not the presence of nvidia wheels.

## Consequence for the release channel

A single torch wheel is **2.56 GB**, already over GitHub's 2 GB per-asset
ceiling before the interpreter, the other 68 packages, or the application are
added. Wiring `split-large-assets.ps1` into the release workflow is confirmed
mandatory, not precautionary.

Note the host: wheels resolve to `download-r2.pytorch.org`, not
`download.pytorch.org`. The variant assertion matches on `pytorch.org` so the
R2 CDN hostname does not trip it.

## What is verified

- CPU variant: 69 packages, all with SHA-256, zero `nvidia-*`, torch from PyPI,
  passes `validate_requirements_lock`.
- cu128 variant: 69 packages, `torch==2.11.0+cu128` and
  `torchvision==0.26.0+cu128` from the PyTorch host, zero UNKNOWN licenses.
- Sources: 13 pinned inputs (CPython 3.12.10 embeddable + 12 MSYS2 packages),
  passes `validate_sources_lock`.
- Variant agreement: `sources-<variant>.lock.json` is written per variant so
  `validate_lock_bundle` sees one consistent variant across all three locks.
- `render_pip_requirements` emits 69 `==` pins, every line carrying
  `--hash=sha256:`.

## Not yet done

- `wheelhouse-manifest.json` for both variants — belongs to CI, which downloads.
- Committing the generated locks. They are reproducible from the script, and the
  cu128 pins move whenever the index advances, so committing them is a
  deliberate act once CI can verify a full download against them.

## MSYS2 filenames drift

Hand-written MSYS2 pins were already stale when first tried — 8 of 12 filenames
had been rebuilt and 404'd. `--refresh-msys2` reads the live index and pins the
newest build, printing every change. MSYS2 removes superseded packages, so a
committed sources lock will rot; refreshing it is a routine maintenance action,
not an emergency.

Current pins (verified against the live index):

| package | version |
|---|---|
| cairo | 1.18.4-4 |
| fontconfig | 2.18.2-1 |
| freetype | 2.14.3-1 |
| pixman | 0.46.4-3 |
| libpng | 1.6.58-1 |
| zlib | 1.3.2-2 |
| bzip2 | 1.0.8-3 |
| brotli | 1.2.0-1 |
| expat | 2.8.2-1 |
| graphite2 | 1.3.15-1 |
| harfbuzz | 14.2.1-1 |
| gcc-libs | 16.1.0-5 |
