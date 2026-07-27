# Licenses and third-party notices — FigureSmith

This document summarizes license boundaries for the FigureSmith repository.

## FigureSmith source code

- License: **MIT** (see root `LICENSE`)
- Applies to FigureSmith-authored files under `apps/`, `scripts/`, `docs/`, `tests/`, and root project docs, unless a file says otherwise.

## AutoFigure-Edit (vendored)

- Path: `vendor/autofigure_edit/`
- License: **MIT** — Copyright 2026 Autofigure2 contributors
- See: `vendor/autofigure_edit/LICENSE`, `CITATION.cff`, `CITATION_AND_ATTRIBUTION.md`, `TRADEMARK.md`
- Import metadata: `vendor/autofigure_edit/UPSTREAM.md`

FigureSmith is based on AutoFigure-Edit but is an **independent** project.

## svg-edit (static editor assets)

- Paths:
  - Runtime (used by vendor server): `vendor/autofigure_edit/web/vendor/svg-edit/`
  - Boundary copy: `vendor/svg_edit/`
- Bundled as part of the AutoFigure-Edit web UI vendor tree.
- Extension notes include MIT-licensed Raphael shape library text under editor extensions.
- Treat as third-party static assets; do not rebrand as FigureSmith logo/IP.

## Runtime ML dependencies (not shipped as weights in this repo)

| Component | Role | Notes |
|-----------|------|-------|
| SAM3 | Local segmentation (optional) | Installed separately; weights **not** in git |
| RMBG-2.0 (Bria) | Background removal | Often gated; **weight license ≠ MIT source license** |
| PyTorch / torchvision / transformers / timm / kornia | ML stack | Per their respective upstream licenses |

**Important:** The MIT license on FigureSmith / AutoFigure-Edit **source code** does **not** automatically grant rights to third-party **model weights**. Review each weight provider’s terms before distribution or commercial use.

## Cloud APIs (optional, not offline desktop path)

Vendor code may still reference optional cloud SAM providers (e.g. Roboflow, fal.ai) and OpenAI-compatible APIs. Those are network services with their own terms. Phase 2 aims to prefer local models for desktop offline use.

## Files to keep in sync

| File | Purpose |
|------|---------|
| `LICENSE` | FigureSmith MIT |
| `NOTICE.md` | Attribution summary |
| `THIRD_PARTY_NOTICES.md` | Third-party inventory |
| `resources/licenses/` | Extra license texts (Phase 2+) |
| `resources/notices/` | Extra notices (Phase 2+) |
| `docs/licenses.md` | This guide |

## Trademark

Upstream trademarks and logos remain with their owners. FigureSmith does **not** use AutoFigure-Edit / ResearAI branding as its product identity. See upstream `TRADEMARK.md` inside the vendor tree.
