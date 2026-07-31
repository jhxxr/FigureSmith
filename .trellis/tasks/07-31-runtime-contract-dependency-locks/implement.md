# Runtime Contract and Dependency Locks Implementation Plan

- [ ] Inventory imported runtime modules, native libraries, SAM3 assets, and
      direct versus build/test dependencies.
- [x] Add runtime/source/wheelhouse schemas and failing validation fixtures.
- [ ] Select exact compatible versions on Windows Python 3.12/cu128.
- [ ] Pin and hash CPython, SAM3, all wheels, and offline prerequisites.
- [ ] Generate legal/source provenance and verify licenses are present.
- [ ] Build the isolated disposable probe runtime from the locked cache.
- [ ] Run import, native DLL, app-factory, isolation, no-network, and no-weight
      checks on a clean Windows runner.
- [ ] Record size/time/disk/prerequisite/channel measurements.
- [ ] Validate locks twice from clean acquisition and review all diffs.
- [ ] Hand the frozen schema/locks/report to the assembly child.

## Validation

The implementation defines dedicated lock validation and probe commands, then
runs the repository Python suite. Network is allowed only during acquisition;
the probe/import phase must fail if it attempts network access.

## Risky areas

- PyTorch/torchvision cu128 compatibility and large asset size.
- CPython embeddable DLL/site initialization behavior.
- SAM3's pinned build metadata, code assets, and license.
- Legitimate `.pth`/`.bin` package files versus model-weight exclusions.

Do not start downstream assembly until all acceptance checks are green or a
measured blocker has received a revised approved plan.
