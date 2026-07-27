# Upstream: svg-edit (via AutoFigure-Edit)

## Source

| Field | Value |
|-------|-------|
| Copied from | `vendor/autofigure_edit/web/vendor/svg-edit` (originally `AutoFigure-Edit-main/web/vendor/svg-edit`) |
| Local upstream root | `G:\0JHX-code\Project\AutoFigure-Edit-main` |
| Import date | 2026-07-27 |
| Role in FigureSmith | Static SVG editor assets for the web canvas |

## Policy

- This is a **boundary copy** for monorepo layout clarity.
- The **runtime path used by the vendor server** remains:

  `vendor/autofigure_edit/web/vendor/svg-edit`

  so relative static mounts and `SVG_EDIT_CANDIDATES` in `server.py` keep working without Phase 1 rewrites.
- Do not treat this tree as FigureSmith product branding or primary logo assets.
- License notes for bundled editor pieces are tracked in root `THIRD_PARTY_NOTICES.md` and `docs/licenses.md`.

## Notes

- Includes `editor/` (SVG-Edit editor bundle) and extension assets.
- Phase 1 does not patch editor behavior.
