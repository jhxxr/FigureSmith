# Decision — CPU pack ships; CUDA is not a release artifact

## Decision

GitHub Releases carry the **CPU runtime only** (0.23 GiB compressed, single
asset). The cu128 variant is **not** published as a release artifact and is not
automatically downloaded by this release. The cu128 locks and manual assembly
path remain available for a future, explicitly designed GPU delivery flow.

Asset splitting is therefore **not needed** and
`scripts/ci/split-large-assets.ps1` stays unwired.

## What forced the question

Measured, not estimated:

| Variant | Compressed | Over GitHub's 2 GiB per-asset limit? |
|---|---:|---|
| cpu | 0.23 GiB (242,788,746 B) | no |
| cu128 | 2.68 GiB (2,879,590,012 B) | **yes** |

The packaging burden was never general — it existed only for cu128. Splitting
2.68 GiB into two parts, publishing a part manifest and joiner, and verifying
reassembly in CI is real ongoing complexity for one variant.

## Why this preserves the Runtime V1 contract

The original 0.6.2 defect was that `requirements-models.txt` pinned only ranges
(`torch>=2.1`), so the same FigureSmith version resolved different Torch and
Transformers builds depending on install date. Runtime V1 continues to solve
that problem for the published CPU pack.

The unpublished CUDA path also has a deterministic build contract:

- the committed cu128 lock names exact versions, HTTPS URLs, and SHA-256
  digests;
- `fetch_wheelhouse.py` verifies every downloaded wheel;
- `assemble_runtime.py` installs with `--no-index --require-hashes --no-deps`;
- `_assert_variant_is_real()` refuses a closure whose Torch packages are not
  genuine `+cu128` builds.

The release itself uses the CPU lock and the application never resolves
dependencies on the target machine. A future CUDA delivery must preserve the
same lock-and-digest guarantees before it is exposed to users.

## What genuinely changes

- GPU acceleration is not available from the published Runtime V1 asset.
- A future CUDA delivery will need to account for upstream availability,
  corporate networks, and the measured TLS interruption during the 2.7 GiB
  wheelhouse fetch.
- Maintainers can still build the cu128 wheelhouse from committed locks for
  offline/manual validation.

## Consequences for Stage 7

- Release publishes the CPU pack plus checksums; no split assets, joiner, or
  reassembly step runs in release CI.
- Runner disk pressure drops sharply: only the CPU path (188 MiB wheelhouse +
  828 MiB tree + 0.23 GiB zip) runs for publication.
- CI validates **both** committed lock bundles, so the cu128 lock cannot rot
  unnoticed even though it is not published.
- A user-initiated CUDA acquisition flow with progress and verification is
  explicitly deferred until after Stage 7.
- `split-large-assets.ps1` remains in-tree and unwired. Its real-file bug fix is
  retained for a future artifact that may need splitting.
