# Windows Runtime Locks

The standalone Windows runtime is assembled only from three reviewable lock
files. They are deliberately separate from `apps/backend/requirements.txt`,
which remains a developer declaration with version ranges.

| File | Purpose |
| --- | --- |
| `requirements-win-py312-cu128.lock.json` | Exact runtime wheels, URLs, tags, licenses, and SHA-256 hashes |
| `sources.lock.json` | CPython/SAM3 source archives or immutable Git revisions and hashes |
| `wheelhouse-manifest.json` | Exact files present in the offline wheel cache |

Each lock carries `schema: 1`, `product: "FigureSmith"`, and the target
`runtime` tuple `python: "3.12"`, `platform: "win_amd64"`, `cuda: "cu128"`.
Wheels must be `.whl` files from HTTPS URLs with exact versions and lowercase
SHA-256 hashes. Source Git entries require a full 40-character commit hash.
Sdists, mutable branches, local paths, model weights, caches, and user-data
directories are rejected.

Validate a lock set and its acquired cache with:

```powershell
./scripts/validate-runtime-locks.ps1 `
  -LockRoot .\runtime\locks `
  -Wheelhouse .\runtime\wheelhouse
```

The repository intentionally does not commit a fake lock set or multi-gigabyte
CUDA wheels. Until a real Windows Python 3.12/cu128 acquisition produces these
three files and passes the validator, the desktop runtime assembler must fail
closed instead of resolving newer packages online.
