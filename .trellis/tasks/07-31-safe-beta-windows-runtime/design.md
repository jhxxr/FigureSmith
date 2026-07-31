# Safe Beta Windows Runtime Distribution Design

## Coordinator structure

This task coordinates three nested deliverables and owns their integration
review. Product-code edits live in the nested child that owns the stage.

```text
Runtime contract and dependency locks
                |
                v
Runtime assembly and sidecar resolver
                |
                v
Setup, Portable, and clean artifact smoke
```

The final stage also requires completed production-integration, security, and
writable-data children from the release-hardening parent.

## Locked input model

Direct runtime requirements are declared separately from build/test tooling.
The lock stage resolves on supported Windows x64 against Python 3.12 and the
selected official cu128 PyTorch index. Every transitive wheel is exact-versioned
and hashed. A source lock separately pins CPython, SAM3, WebView2/VC inputs where
app-local, and any non-PyPI source by URL/revision/hash/license.

Locks are committed review artifacts. Regeneration is explicit and diffable;
release assembly does not resolve newer versions. Cache entries are accelerators,
not trust roots.

The lock child builds a probe runtime first. Its import/DLL matrix covers
FastAPI/Uvicorn, Pillow, lxml, CairoSVG/cffi, NumPy/SciPy/OpenCV, Transformers,
Torch/TorchVision/timm/kornia, SAM3, RMBG dependencies, and vendor imports.
CPU-only CI must report missing NVIDIA driver as a supported runtime state rather
than import failure.

## Runtime assembly

Assembly begins from an empty stage and verified local cache. CPython's
`python312._pth` lists only standard library, controlled `site-packages`,
`app/backend`, and vendor paths, with explicit site initialization only where
required. User site and registry/PATH discovery remain disabled.

Application source/resources are copied through one manifest-aware packager,
not duplicated PowerShell and Python filters. The packager applies an allowlist
for expected dependency files and a deny policy for model/cache/data patterns.
It distinguishes legitimate `.pth` path files from model checkpoint files using
the locked file manifest.

After assembly, import and application-factory smoke run using the staged
`python.exe`. Only then is `runtime-manifest.json` generated and independently
verified.

## Release sidecar resolver

Rust has explicit development and release resolvers:

- development accepts configured/repository Python and paths for contributors;
- release reads the Tauri Resource directory, verifies the runtime manifest and
  product version, and returns the packaged Python and backend entry.

Build configuration selects the resolver. Release failure is terminal; there
is no heuristic fallback to PATH, current directory, or repository markers.
The resolver error is shown on the local splash before a remote webview exists.

The data root remains outside Runtime and is supplied through the completed
writable-data contract.

## Desktop payload

A validated payload stage contains:

```text
FigureSmith.exe
runtime/...
desktop/runtime metadata
legal/checksum metadata
```

Portable zips this stage without structural changes. Setup installs the same
stage, preserving the runtime manifest digest. WebView2 uses an offline-capable
strategy and Portable includes/validates the required fixed runtime where the
clean target cannot assume it. VC/UCRT behavior is proven on the clean runner
and supplied app-local or by a bundled offline prerequisite as measurements
require.

Artifact files are written to a private staging directory. Validation completes
before an atomic move to `dist-desktop/publish`. A missing desktop executable or
runtime never produces `BUILD_INSTRUCTIONS.txt` as a success artifact.

## Self-test and CI flow

The desktop exposes a noninteractive `--self-test <result.json>` intended for
artifact validation. It uses production resource resolution, starts the real
sidecar, waits for authenticated readiness, probes owned/vendor APIs, checks
the runtime/data manifests, then shuts down and verifies process cleanup. It
writes a schema-versioned redacted result and exits nonzero on any failure.

The clean artifact job does not check out source. It downloads Setup/Portable
plus checksums, verifies them, runs self-test from a hostile path, and performs
install/uninstall where applicable. Negative matrix jobs mutate copies of the
payload and require early failure.

## Compatibility and release behavior

- Developers retain explicit source-mode launch.
- Users obtain model weights separately and import them into writable data.
- No runtime component is installed globally and no target-machine pip runs.
- A compatible NVIDIA driver remains a documented system prerequisite.
- Runtime/source lock changes require a new runtime/product version and full
  artifact smoke.

## Failure, rollback, and measured risks

The three nested stages are rollback points. A lock/probe failure blocks before
assembly; assembly failure blocks before desktop packaging; smoke failure blocks
publishing. Published artifacts are never repaired in place.

If measured full payload size exceeds the configured release channel, the gate
stops and records exact size/composition. A new delivery shape requires planning
review; omitting dependencies or reintroducing online setup is not an automatic
fallback.
