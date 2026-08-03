# Stage 7 — measured size / channel data

All numbers were measured on this machine from the committed locks, not
estimated.

## Per-variant payload

| Variant | Wheelhouse | Assembled tree | Manifest files | Zip (deflate) | Ratio |
|---|---:|---:|---:|---:|---:|
| cpu | 188 MiB | 828 MiB | 23,476 | **0.23 GiB** (242,788,746 B) | ~3.6× |
| cu128 | 2.7 GiB | 4.5 GiB | 23,250 | **2.68 GiB** (2,879,590,012 B) | ~1.7× |

The cu128 tree compresses poorly because it is dominated by already-compressed
CUDA kernel payload inside the 2.56 GiB torch wheel.

## Release-channel consequence

GitHub's per-asset ceiling is 2 GiB.

- `cpu` at 0.23 GiB ships as a single asset.
- `cu128` at 2.68 GiB exceeds the limit and is **not published** by the
  CPU-only release workflow, so no split/join step runs in release CI.

The design assumption that cu128 needs splitting is confirmed, but the chosen
release channel intentionally publishes CPU only. The cu128 lock remains
validated so dependencies are not silently dropped from the repository; it is
simply outside this release artifact.

## Runner disk budget

The CPU publication job holds the CPU wheelhouse, assembled tree, and ZIP only;
the approximately 12.6 GiB cu128 peak does not occur in release CI. The
workflow validates the cu128 lock metadata without downloading its wheelhouse.

## Build time

Wall-clock on this machine with warm source cache and wheelhouse:

- CPU assembly: ~4 min (69 packages, 23,476 files hashed)
- CPU ZIP: included in the release job after assembly

Cold acquisition adds the network time for the 188 MiB CPU wheelhouse and the
pinned CPython/MSYS2 source archives.

## Local clean-runner evidence

On 2026-08-03, the assembled CPU tree was launched with its embedded
`python/python.exe`, with `PYTHONPATH` and `PYTHONHOME` removed, system Python
removed from `PATH`, `FIGURESMITH_STRICT_OFFLINE=1`, and a temporary writable
data root. `/healthz`, `/api/desktop/ready`, and `/api/system/status` all
returned successfully; system status reported the embedded interpreter. A
`POST /api/shutdown` completed cleanly and the child process was absent after
shutdown. The isolated interpreter reported `sys.flags.isolated == 1` and its
`sys.path` contained only the shipped zip, interpreter directory, and
`Lib/site-packages` (no user-site or current-directory entry).

The negative path is covered by the Python manifest tests and Rust sidecar
tests: changing or removing a required runtime file is rejected before spawn.
