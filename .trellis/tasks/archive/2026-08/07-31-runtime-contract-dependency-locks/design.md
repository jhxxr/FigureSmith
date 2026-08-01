# Runtime Contract and Dependency Locks Design

## Lock model

Maintain three reviewable inputs: direct runtime requirements, a fully resolved
Windows Python 3.12/cu128 wheel lock with hashes, and a source lock for CPython,
SAM3, WebView2/VC inputs, indexes, revisions, licenses, and archive hashes.
Build/test tooling is locked separately and never copied into the payload.

Resolution and download run on Windows x64. A verified wheelhouse inventory maps
each locked distribution to its wheel filename, tags, size, and SHA-256. Release
assembly consumes this inventory with no dependency solving.

## Probe runtime

Create a disposable CPython embeddable tree, configure isolated paths, install
the locked wheelhouse, add pinned SAM3 code/assets, and run a versioned import
probe. The probe covers native DLL import, app factory creation, and expected
no-driver behavior while explicitly avoiding model load/network access.

## Measurement gate

Record raw wheelhouse/runtime size, compressed size, stage disk peak, wall time,
VC/UCRT and WebView2 needs, and current release-channel limits. Results are
machine-readable plus a short research report. A red measurement blocks the
next task and triggers plan review rather than changing product scope.

## Manifest schema

The schema defines runtime identity, platform/Python/CUDA versions, product and
source versions, entry paths, lock digests, complete file hashes/sizes, legal
digest, weight exclusion, and immutable/mutable boundaries. Assembly fills file
entries later; this task validates schema examples and failure cases.

## Rollback

Locks change only through explicit regeneration. A previous known-good lock set
remains available in version control; caches never substitute for committed
hashes.
