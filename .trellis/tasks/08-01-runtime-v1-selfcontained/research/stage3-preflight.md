# Stage 3 pre-flight findings

Recorded during Stage 1-2 implementation. Both affect acquisition and must be
settled before locks are generated.

## 1. cairosvg needs a native DLL that pip does not provide

Building the Stage 1 test environment from `requirements-bootstrap.txt`
installed cleanly, but importing `cairosvg` fails on Windows:

```
OSError: no library called "cairo-2" was found
cannot load library 'libcairo-2.dll': error 0x7e
```

`cairosvg` binds to `libcairo` through `cairocffi`, and no Windows wheel carries
that DLL. Today this is masked: the desktop app installs bootstrap packages and
the SVG scope degrades at runtime on a machine without GTK/cairo. Under Runtime
V1 the pack claims to be self-contained, so a missing native DLL becomes a
shipped defect rather than a user environment problem.

Options, in the order they should be considered:

- Ship the `libcairo-2.dll` dependency chain inside the runtime and pin it in
  `sources.lock.json` with a SHA-256, like any other binary input. Adds licence
  review for cairo and its transitive DLLs.
- Drop `cairosvg` and rely on the already-present `svglib` + `reportlab` path,
  which is pure Python. Requires confirming feature parity for the SVG→PDF/PNG
  conversions actually used.
- Keep `cairosvg` optional and declare the SVG scope explicitly degradable.
  Contradicts the "no target-machine setup" goal if that path is user-visible.

Not decided here. `svglib`/`reportlab`/`lxml` all import fine, so the SVG scope
is not wholly blocked either way.

## 2. .gitignore blocks committing a wheelhouse

`.gitignore:36-40` ignores `**/*.pth` and `**/*.bin` to keep model weights out.
A real wheelhouse and an installed `site-packages` tree both contain those
extensions legitimately — `distutils-precedence.pth`, `nvidia-*` payload.

The wheelhouse itself is a build cache and should stay out of git; only the
`*.lock.json` files are committed. But any future attempt to commit a probe
fixture or vendored tree under those paths will silently drop files. If that
becomes necessary, add a negated rule scoped to the runtime tree rather than
loosening the global weight rules.

The same asymmetry now exists between git and the packaging filter: after Stage
1, `is_weight_file` allows those suffixes inside site-packages while git still
ignores them everywhere. That is intentional — packaging decides what ships,
git decides what is versioned — but the two must not be assumed to agree.

## 3. Size expectation for the measurement gate

Not yet measured. The cu128 closure is dominated by `torch` plus the `nvidia-*`
CUDA runtime wheels; the working assumption in `design.md` is 4-6 GB
uncompressed, which exceeds the 2 GB GitHub per-asset ceiling and is why
`split-large-assets.ps1` is being wired in. Replace this section with real
numbers once Stage 3 completes — the channel decision depends on it.
