# FigureSmith Release Hardening Design

## Problem statement

FigureSmith's components pass their isolated checks, but the production
composition and release payload do not preserve those contracts. The program
must make the shipped Windows application, rather than the repository layout,
the unit of correctness.

## Program architecture

This parent task coordinates independently verifiable children and does not
directly own product-code edits.

```text
Safe Beta runtime integration
          |
          +----> Safe Beta security boundary
          |
          +----> Writable application data
          |               |
          +---------------+----> Safe Beta Windows runtime distribution
                                         |
                                         +----> Safe Windows Beta gate

Job and model lifecycle hardening -----------+
Safe Beta Windows runtime distribution ------+--> Release quality/consistency
                                                    --> production-ready gate
```

Dependencies are contracts, not scheduling suggestions:

| Child | Owns | Explicit dependencies |
|---|---|---|
| Safe Beta runtime integration | Production ASGI composition, Tauri command reachability, authentication readiness, sidecar startup/process ownership | None |
| Safe Beta security boundary | SVG trust boundary, exact-origin credential transport, and effective strict-offline enforcement | Runtime integration's API origin and session contracts |
| Writable application data | One writable root for settings, models, jobs, uploads, outputs, and temporary files | Runtime integration's launch environment contract |
| Safe Beta Windows runtime distribution | Locked Runtime Directory, sidecar release resolver, Setup/Portable payloads, fail-closed build, clean-artifact smoke | All three Safe Beta children above |
| Job and model lifecycle hardening | Queue/cancel/progress, secret/input transport, bounded file operations, graceful shutdown, transactional imports/settings, model executable-code integrity | Runtime integration and writable-data contracts |
| Release quality and consistency | Full PR/release gates, version authority, reproducible metadata, bilingual docs | Windows runtime distribution and lifecycle contracts |

## Safe Beta architecture

### Composed backend

`apps/backend/main.py` creates a FigureSmith-owned outer FastAPI application.
Authentication middleware and FigureSmith model/system/desktop routes live on
that outer app. The vendor application is mounted at `/` last and acts only as
the fallback UI and vendor API surface.

This avoids modifying vendor route-list internals and makes route precedence
structural. `/healthz` must report composition readiness, not merely that the
vendor sub-application is alive.

### Desktop session and native-command boundary

The sidecar chooses an ephemeral `127.0.0.1` port and a random session token
before bind. After health and authenticated readiness succeed, Rust registers a
runtime Tauri capability for that exact origin and creates the remote webview
with a document-start initialization script. The script installs the API
authentication wrapper and keeps the token in a private closure before any page
application script can run. Injection failure produces a blocking startup error
and no anonymous request. Reload and navigation rerun the initialization script.

The bridge derives an immutable allowed origin from the injected API base. It
adds credentials only when protocol, hostname, port, origin, and API path all
match. It preserves `Request`, body, abort, and header semantics. No public
native command returns the token to page code.

The Tauri build manifest declares only named FigureSmith commands. At runtime,
the pinned Tauri dynamic ACL registers those commands only for the main webview
label and the exact `http://127.0.0.1:<chosen-port>/*` URL. A static wildcard
port grant is not used. Browser-only development mode remains usable without
native commands.

### Untrusted SVG and network boundary

A single backend SVG safety service is called after generation and before PNG
rendering. It uses bounded XML parsing plus element, attribute, namespace, URI,
and CSS allowlists. Script-capable elements, event attributes, external URLs,
active CSS, DTD/entities, and unsupported data URIs fail closed.

Artifact delivery applies the same policy again so pre-upgrade history cannot
bypass it. SVG responses carry a sandboxed CSP and `nosniff`; downloads use
attachment disposition. Preview uses a non-script execution context.

Strict-offline enforcement validates the effective provider configuration
after defaults are resolved and rejects cloud providers, remote redirects, and
provider-returned remote assets before network access.

### Process ownership

Rust owns the backend and its descendants as one Windows process tree from the
moment Python is spawned. Startup failure, webview close, Rust panic cleanup,
and graceful shutdown all converge on the same idempotent cleanup path. The
health loop checks early child exit instead of waiting the full timeout.

The Beta contract guarantees a concurrency ceiling and no orphan process.
Rich queueing, cancellation UX, recovery, and transaction semantics remain in
the lifecycle child.

### Writable data root

The desktop resolves one writable application-data root before backend start,
normally under LocalAppData. It passes that root explicitly. The backend
validates the directory with a create/write/replace/delete probe and fails
early if neither the requested location nor the supported fallback works.

All mutable paths derive from this root:

```text
data/
  settings.json
  models/
  jobs/
  uploads/
  outputs/
  temp/
  logs/
```

The install directory and Runtime Directory are immutable. Development may use
an explicit override, but production never silently falls back to source paths.

### Runtime Directory

The canonical Windows runtime is a versioned, immutable directory:

```text
runtime/
  runtime-manifest.json
  python/
    python.exe
    python312.dll
    python312.zip
    python312._pth
    Lib/site-packages/
  app/
    backend/main.py
    backend/figuresmith/
    vendor/autofigure_edit/
    resources/
  legal/
  locks/
```

The implementation pins the exact CPython 3.12 Windows x64 embeddable archive,
SAM3 application source/wheel, cu128 runtime wheels, and every other dependency
by version and SHA-256. Acquisition may use the network; assembly runs with
`--no-index`, `--find-links`, and `--require-hashes` against verified inputs.
Target machines never run pip.

`runtime-manifest.json` records schema, product/runtime versions, platform,
Python and CUDA flavor, entry point, source revision, lock digests, component
hashes/sizes, and `contains_weights: false`. It is verified before packaging and
again before launch.

Setup and Portable consume the same verified payload. Each contains the
desktop executable and complete runtime. Release mode resolves Python and the
backend only through the packaged resource contract; it cannot fall back to
PATH Python, `CARGO_MANIFEST_DIR`, current directory, or a repository checkout.

### Packaging and smoke gate

Build order is deterministic:

1. Acquire and hash-verify locked sources and wheels.
2. Assemble and validate the canonical Runtime Directory offline.
3. Build the desktop executable against the approved capability/configuration.
4. Stage and validate one immutable desktop payload.
5. Produce Portable and Setup from that payload.
6. Validate hashes, required files, weight exclusion, version agreement, and
   archive readability before moving artifacts into the publish directory.

Missing executables, runtime files, manifests, dependency hashes, or import
checks cause a non-zero exit and no publishable archive. Placeholder artifacts
are removed as a supported build outcome.

A clean Windows job downloads the built artifact without the source checkout,
clears Python/FigureSmith environment overrides, launches from a path with
spaces and non-ASCII characters, reaches authenticated health/model/system
routes, exercises shutdown, and verifies no child survives. Negative smoke
cases remove or corrupt required files and must fail before partial startup.

## Full hardening architecture

The lifecycle child replaces immediate heavyweight subprocess launch with a
bounded job manager. Generation and import become observable jobs with stable
IDs, progress, cancellation, timeouts, cleanup, and a single source of truth
for status. Provider secrets and method content move from argv into a bounded,
ephemeral job-input channel; uploads and artifact paths gain streaming/resource
bounds and resolved containment. Model promotion and settings updates use a
process-wide lock, staging journal, atomic replacement, and crash recovery.

Executable model packages use a release manifest that covers every executed
Python/config file and every weight shard. UI status separates configured,
structurally valid, integrity verified, and currently loaded states.

The final quality child promotes all relevant checks into PR CI and release
gates, establishes one version source, validates dependency/source locks and
legal metadata, and aligns English/Chinese documentation with shipped behavior.

## Compatibility and migration

- Existing model weights remain external and are discovered or migrated under
  the writable-data contract; packaging never copies them.
- Existing history SVG is not trusted. It is sanitized at read time or denied.
- Development launch remains available through an explicit dev-mode resolver;
  production detection is based on build configuration, not path guessing.
- Existing API response shapes remain stable where possible. New failure codes
  are additive and deterministic.
- The first Beta may require a supported NVIDIA driver and may report CPU-only
  CI as an import/startup smoke rather than a full GPU inference proof.

## Rollback and operational behavior

- Each child lands behind its own tests and can be reverted independently
  before the Windows payload task consumes its contract.
- Runtime staging is immutable and promoted only after verification. A failed
  build leaves diagnostic logs outside the publish directory.
- Mutable-data migrations use versioned markers and preserve the previous file
  until atomic replacement succeeds.
- Release publishing depends on clean-artifact smoke; manual dispatch cannot
  bypass the same version and payload checks.

## Deferred decisions and measured risks

No user-owned decision blocks planning. Implementation must measure, without
changing the accepted behavior:

- native-wheel compatibility in CPython's embeddable distribution;
- full cu128 runtime size and release-channel limits;
- VC/UCRT and WebView2 availability on a clean Windows image;
- GPU inference on representative NVIDIA hardware;
- code-signing and long-term updater strategy, which remain outside the Safe
  Beta unless separately authorized.
