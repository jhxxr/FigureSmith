# Third-Party Notices — FigureSmith

This file lists third-party software and components included or referenced by
FigureSmith. It is not legal advice.

---

## 1. AutoFigure-Edit

| Field | Value |
|-------|-------|
| Component | AutoFigure-Edit |
| Location | `vendor/autofigure_edit/` |
| License | MIT |
| Copyright | Copyright (c) 2026 Autofigure2 contributors |
| Paper | arXiv:2603.06674 |
| Import | File-level snapshot on 2026-07-27 from local path `G:\0JHX-code\Project\AutoFigure-Edit-main` |

See also:

- `vendor/autofigure_edit/LICENSE`
- `vendor/autofigure_edit/CITATION.cff`
- `vendor/autofigure_edit/CITATION_AND_ATTRIBUTION.md`
- `vendor/autofigure_edit/TRADEMARK.md`
- `vendor/autofigure_edit/UPSTREAM.md`

FigureSmith branding and packaging do **not** claim AutoFigure-Edit as the
product name. FigureSmith is independent and not affiliated with or endorsed by
ResearAI.

---

## 2. svg-edit (static assets via AutoFigure-Edit)

| Field | Value |
|-------|-------|
| Component | svg-edit editor bundle (as vendored by AutoFigure-Edit) |
| Locations | `vendor/autofigure_edit/web/vendor/svg-edit/`, `vendor/svg_edit/` |
| Notes | Used as web canvas/editor static files; not FigureSmith product logo/IP |

Additional bundled notice example found under editor extensions:

- `editor/extensions/ext-shapes/shapelib/license-MIT-raphael.txt` (MIT)

---

## 3. Python / ML stack (dependencies, not vendored as source trees)

Installed via `apps/backend/requirements.txt` (and upstream requirements).
Examples include but are not limited to:

- FastAPI, Uvicorn, Pydantic
- NumPy, Pillow
- PyTorch, torchvision
- transformers, timm, kornia
- lxml, cairosvg, svglib, reportlab
- openai, google-genai, requests

Each dependency remains under its own upstream license. Consult the environment
or package metadata for the installed versions.

---

## 4. SAM3 (optional, separate install)

| Field | Value |
|-------|-------|
| Component | Segment Anything Model 3 (SAM3) related tooling |
| Distribution | **Not** shipped in this repository |
| Install | Separate clone/install per upstream docs |
| Weights | **Not** included in git; user-supplied / Phase 2 model pack |

---

## 5. RMBG / Bria background-removal models (optional runtime)

| Field | Value |
|-------|-------|
| Component | RMBG-style background removal models (e.g. Bria RMBG-2.0) |
| Distribution | **Not** shipped in this repository |
| License caution | Model weight terms may differ from MIT source code terms |
| Phase 1 | No local-only loader rewrite yet |

---

## 6. Optional cloud services referenced by vendor code

Vendor baseline may still mention optional network services such as:

- OpenAI-compatible HTTP APIs
- Roboflow / fal.ai style SAM API paths

These are external services with separate terms of use. They are **not** the
preferred offline desktop path for FigureSmith Phase 2+.

---

## Source license vs model weight license

**MIT (or other OSS licenses) on source code do not equal permission to
redistribute or commercially use third-party model weights.**

Always review weight-provider terms before packaging installers or runtime packs.

---

## Updates

When adding new third-party code or bundling additional static assets, update:

1. This file
2. `NOTICE.md`
3. `docs/licenses.md`
4. Optionally `resources/licenses/` and `resources/notices/`
