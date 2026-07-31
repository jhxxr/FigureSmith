# Runtime Assembly and Sidecar Resolver Design

## Assembly pipeline

The acquisition command populates a content-addressed verified cache. The
assembly command accepts only the committed locks plus this cache, creates a new
stage, installs with hash/no-index enforcement, copies application/legal inputs
through a structured packager, and runs smoke before manifest generation.

The packager derives output from explicit roots and structured path rules. Its
generated file inventory is the source for independent weight/cache detection;
unexpected files fail. Runtime timestamps/metadata are normalized where needed
for deterministic manifests.

## Python isolation

`python312._pth` contains only controlled runtime entries. Environment variables
that alter Python home/path/user-site are removed before spawn. The runtime
probe asserts imports resolve beneath the staged runtime and that a canary
package on PATH/current directory is ignored.

## Rust resolver

A resolver trait returns validated Python, backend entry, runtime root, and
manifest identity. Development and release implementations are chosen by build
mode/configuration, not by guessing whether repo files exist.

The release implementation resolves Resource base paths, parses the manifest,
checks schema/product/runtime identity and critical files before spawn, and can
run full hash verification in self-test/build validation. Startup failures are
typed and redacted for the local splash.

## Integration

The completed sidecar state machine consumes the resolved command/working root.
The completed data contract supplies a separate writable root. Runtime itself
is never selected as current mutable data.

## Rollback

The old source resolver remains only inside explicit development mode. Release
cannot use it as a fallback. Assembly staging is disposable until independent
verification passes.
