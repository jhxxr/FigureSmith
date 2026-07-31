# Windows Runtime Distribution Technical Notes

## Canonical layout

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
    LICENSE
    NOTICE.md
    THIRD_PARTY_NOTICES.md
    dependency-licenses/
  locks/
    requirements-win-py312-cu128.lock
    sources.lock.json
    wheelhouse-manifest.json
```

Tauri maps this directory into its Resource base. Release Rust resolves
`runtime/runtime-manifest.json`, `runtime/python/python.exe`, and
`runtime/app/backend/main.py` through the packaged resource API.

## Manifest minimum fields

- schema and product/runtime version;
- OS, architecture, exact CPython version, CUDA flavor;
- backend entry point and source revision;
- dependency/source lock digests and pinned SAM3 revision;
- full relative file path, size, and SHA-256 list;
- legal metadata digest;
- `contains_weights: false` and an empty mutable-path list.

## Build phases

1. Networked acquisition downloads exact archives/wheels/sources and verifies
   committed hashes.
2. Offline assembly installs only from the verified cache using
   `--require-hashes --no-index --find-links` and rejects sdists/local builds.
3. Import smoke runs isolated Python with user-site and Python environment
   influence disabled.
4. Manifest generation scans the complete immutable tree.
5. Independent verification repeats hashes, imports, license/source checks, and
   manifest-aware weight exclusion.

## Clean smoke

The artifact-only Windows job clears `FIGURESMITH_*` and `PYTHON*`, runs from a
path with spaces/non-ASCII text, and has no repository checkout. A desktop
`--self-test <result.json>` mode is recommended to exercise real resource
resolution, sidecar startup, authenticated API calls, and shutdown without
guessing the ephemeral port. The result is redacted and exit-code authoritative.

Negative cases remove the manifest, Python DLL, and backend entry; corrupt a
hash; add an unlisted checkpoint-like file; and damage the archive. Each must
fail closed before a publishable artifact exists.

## Technical references

- Tauri resources: https://v2.tauri.app/develop/resources/
- CPython embeddable package:
  https://docs.python.org/3.12/using/windows.html#the-embeddable-package
- pip secure/hash installs:
  https://pip.pypa.io/en/stable/topics/secure-installs/
- Tauri Windows installers:
  https://v2.tauri.app/distribute/windows-installer/

## Measured-risk gate

The first nested child must validate native-wheel/DLL compatibility, SAM3
license/assets, VC/UCRT and WebView2 behavior, total size, compression ratio,
build time, disk peak, and release-channel limits. A failed measurement blocks
assembly; it does not weaken the self-contained runtime requirement.
