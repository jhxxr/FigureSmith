# Upstream: AutoFigure-Edit

## Source

| Field | Value |
|-------|-------|
| Local import path | `G:\0JHX-code\Project\AutoFigure-Edit-main` |
| Import date | 2026-07-27 |
| Upstream product | AutoFigure-Edit |
| Upstream license | MIT (Copyright 2026 Autofigure2 contributors) |
| Paper | arXiv:2603.06674 |
| Version clues | `releases/v1.1.md`, README v1.1 |

## Import policy

This directory is a **file-level snapshot** of AutoFigure-Edit used as a **preserve-as-baseline** vendor tree for FigureSmith.

- Keep business / pipeline code **unchanged** in Phase 1 so it remains diffable against the original source.
- Do **not** rewrite SAM3 / RMBG inference logic here in Phase 1.
- FigureSmith-specific adapters live under `apps/backend/figuresmith/`.
- Any future vendor edits must be recorded (file, reason, date).

## What was copied

- Core: `autofigure2.py`, `server.py`, `requirements.txt`
- Compliance: `LICENSE`, `CITATION.cff`, `CITATION_AND_ATTRIBUTION.md`, `TRADEMARK.md`
- Docs: `README.md`, `README_ZH.md`
- Containers: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Config sample: `.env.example`
- Web UI: `web/` (includes `web/vendor/svg-edit` so relative paths still work)
- Release notes: `releases/`
- Reference images: `img/` **except** `img/case/` (large gallery; not required to run the server)

## Intentionally not fully mirrored

- `img/case/` gallery (~95MB) was skipped to keep the monorepo lean. Re-copy from the local upstream path if demos need it.
- Model weights are never imported.
- Runtime caches (`outputs/`, `uploads/`, `__pycache__/`, `.git`) are excluded.

## Relationship to FigureSmith

FigureSmith is an **independent** open-source project based on AutoFigure-Edit.  
It is **not** affiliated with or endorsed by ResearAI.

A second copy of the SVG editor static tree also exists at `vendor/svg_edit/` for clearer monorepo boundaries; the in-tree copy under `web/vendor/svg-edit` remains the path used by `server.py`.
