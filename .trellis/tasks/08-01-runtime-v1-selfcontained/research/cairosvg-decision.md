# cairosvg / libcairo — measured findings

**Decision: bundle libcairo, keep cairosvg.** The optimizer's LLM vision
feedback is the product's core value; a parser that silently drops embedded
base64 figures would degrade it invisibly. The 8.3 MB / 14-DLL supply chain is
accepted as the cost of that fidelity.

Consequences accepted:
- `sources.lock.json` gains the MSYS2 cairo package chain, each pinned by
  SHA-256 with a license record, refreshed deliberately when MSYS2 rebuilds.
- `pycairo`/`rlPyCairo`/`svglib` are NOT the shipping path. The svglib branch
  stays only as a degraded fallback and must still be made reachable.

These are the measured numbers behind that choice.

All results below were executed on this Windows machine, not inferred.

## What actually fails

```
>>> import cairosvg
OSError: no library called "cairo-2" was found
cannot load library 'libcairo-2.dll': error 0x7e
```

`cairosvg` → `cairocffi` → `cffi.dlopen("libcairo-2")`. It needs a real
`dlopen`-able DLL on the search path. No Windows wheel supplies one.

## Measured: the DLL chain if cairosvg is kept

Parsed the PE import tables of the MSYS2 `mingw-w64-x86_64-cairo-1.18.4-4`
package and walked the closure:

| DLL | Size |
|---|---|
| libstdc++-6.dll | 2605 KB |
| libharfbuzz-0.dll | 1506 KB |
| libcairo-2.dll | 1218 KB |
| libfreetype-6.dll | 772 KB |
| libpixman-1-0.dll | 723 KB |
| libfontconfig-1.dll | 491 KB |
| libpng16-16.dll | 258 KB |
| libexpat-1.dll | 232 KB |
| libgraphite2.dll | 163 KB |
| libgcc_s_seh-1.dll | 148 KB |
| libbrotlicommon.dll | 140 KB |
| zlib1.dll | 125 KB |
| libbz2-1.dll | 99 KB |
| libbrotlidec.dll | 61 KB |

**14 DLLs, 8.3 MB**, drawn from ~10 MSYS2 packages. Five more references were
left unresolved by the packages fetched (`libglib-2.0-0.dll`, `libintl-8.dll`,
`libwinpthread-1.dll`, plus the system `DWrite.dll`/`USP10.dll`), so the real
closure is slightly larger.

Cost of this path: each DLL needs an entry in `sources.lock.json` with a
SHA-256, a license record, and a refresh procedure whenever MSYS2 rebuilds. It
is a second supply chain running parallel to the wheel lock, sourced from a
distro repo rather than PyPI, with no per-file signing.

## Measured: a wheels-only path that works

`pycairo`'s Windows wheel links cairo **statically** into its extension module:

```
pycairo-1.29.0-cp312-cp312-win_amd64.whl
    cairo/_cairo.cp312-win_amd64.pyd   1740800 bytes
    (no DLLs)
```

End-to-end render, verified:

```
pycairo ok, cairo version: 1.18.4
svglib+rlPyCairo RENDER OK -> 2331 bytes
  image: (150, 90) RGB
```

So `svglib` + `reportlab` + `rlPyCairo` + `pycairo` rasterizes SVG→PNG on
Windows with **zero external DLLs**, entirely from PyPI wheels, fully
hash-lockable by the existing `locks.py`.

Important: installing `pycairo` does **not** rescue `cairosvg`. Re-tested with
pycairo present — still `OSError: no library called "cairo-2"`. `cairocffi`
cannot dlopen a statically-linked `.pyd`. The two paths are mutually exclusive.

## Correction to an earlier claim

An earlier audit asserted reportlab ships its own bundled C rasterizer
(`_renderPM`) needing no external library. Tested and false on Windows for both
lines:

- reportlab 5.0.0 → `RenderPMError: cannot import desired renderPM backend rlPyCairo`
- reportlab 4.5.1 → same; neither `reportlab.graphics._renderPM` nor `_rl_renderPM` exists

reportlab delegates to `rlPyCairo` → `pycairo`. The pure-Python fallback the
code assumes does not exist. Whichever option is chosen, `reportlab>=4.0` must
be pinned deliberately, and if the svglib path is used, `rlPyCairo` + `pycairo`
must be explicit dependencies — today they are not in any requirements file, so
the existing fallback branch cannot work even when reached.

## The real fidelity tradeoff

The gap is **not** the rasterizer — both end in cairo 1.18.4. It is the SVG
parser:

- `cairosvg` parses SVG itself: broader coverage of filters, gradients, masks,
  clip paths, CSS.
- `svglib` converts SVG into ReportLab drawing primitives first, and is weaker
  on exactly those features, notably embedded base64 raster images — which this
  pipeline deliberately produces (`autofigure2.py:3142` `count_base64_images`,
  `:3149` `validate_base64_images`).

Consumer is an LLM vision comparison inside the optimizer loop, not a shipped
artifact. Degraded rendering means weaker optimizer feedback, silently — if
embedded figure images fail to render, the model compares against a near-blank
frame.

That is the case for keeping cairosvg and paying the 8.3 MB / 14-DLL cost.

## Independent of which option is chosen

1. **The fallback never fires.** `autofigure2.py:3184` catches only
   `ImportError`, but the Windows failure is `OSError`, which falls through to
   `:3198` and returns `None`. The optimizer then prints "无法将 SVG 转换为
   PNG，跳过优化" and breaks the loop. Widen to `except (ImportError, OSError)`
   or restructure.
2. **Scope disagreement.** `dependencies.json:108` puts cairosvg in the optional
   `svg` scope; `requirements-bootstrap.txt:11` puts it in mandatory
   first-launch bootstrap. That mismatch is why the DLL failure surfaces during
   automatic install.
3. **`missing_svg` drives nothing.** `system_routes.py:194-201` branches install
   guidance only on `missing_bootstrap`/`missing_models`, so a broken SVG scope
   yields no remediation command.
4. **`scale` is silently dropped** in the svglib branch (`:3189-3190`). Harmless
   today since every caller uses `scale=1.0`, but it is a real parameter drop.

## Usage context

One call site: `svg_to_png` at `autofigure2.py:3167`, `svg2png` only, both
callers at default `scale=1.0`. The arbitrary-DPI capability is never exercised.
No test covers cairosvg, svglib, reportlab, `svg_to_png`, or the `svg` scope, so
either option can be implemented without breaking a test — and neither is
currently guarded by one.
