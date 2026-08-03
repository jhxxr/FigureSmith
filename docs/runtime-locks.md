# Runtime V1 locks

Runtime V1 is assembled from exact, committed Windows Python 3.12 locks. The
published GitHub Release contains the CPU pack only; the cu128 lock remains
available for maintainer or manual GPU builds and is validated in CI.

The lock bundle for each variant contains:

- `requirements-win-py312-<variant>.lock.json` — exact wheel versions, URLs,
  tags, licenses, and SHA-256 digests;
- `sources-<variant>.lock.json` — the CPython embeddable archive and pinned
  native cairo DLL sources;
- `wheelhouse-<variant>.manifest.json` — the acquired wheel inventory.

The build machine must provide x64 CPython 3.12 with pip and the `zstandard`
package (for unpacking pinned MSYS2 archives):

```powershell
python -m pip install zstandard
```

The assembler rejects another Python minor version before it creates a pack.
This is a maintainer/build-machine requirement only; the published CPU pack
still contains its own interpreter and does not require Python or pip on the
target machine.

Acquisition is network-enabled and always verifies the committed digests:

```powershell
python scripts/runtime/fetch_wheelhouse.py `
  --variant cpu --lock-root locks --out build/wheelhouse-cpu
python scripts/runtime/assemble_runtime.py `
  --variant cpu --lock-root locks --cache build/source-cache --fetch-sources
./scripts/validate-runtime-locks.ps1 `
  -LockRoot locks -Variant cpu -Wheelhouse build/wheelhouse-cpu
```

Assembly is offline. It installs with `--no-index`, `--require-hashes`,
`--no-deps`, and `--only-binary :all:` into the embedded interpreter's
`Lib/site-packages`. Missing or tampered inputs fail before publication.

```powershell
./scripts/build-runtime.ps1 -Variant cpu -Wheelhouse build/wheelhouse-cpu
```

The resulting CPU pack contains embedded CPython, resolved packages, native
DLLs, the consumed locks, and a schema-2 `runtime-manifest.json`. It contains
no model weights, caches, loose wheels, or mutable user data. The manifest
records every file and its SHA-256 digest; the desktop sidecar verifies it
before spawning the backend.

The CPU pack is approximately 0.23 GiB compressed. The cu128 pack is much
larger and is intentionally not uploaded as a release asset.
