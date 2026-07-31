# Release Quality Technical Notes

## Source anchors

- CI omissions: `.github/workflows/ci.yml:21`.
- Placeholder/manual publish paths: `.github/workflows/release-windows.yml:160`,
  `:207`, `scripts/build-desktop.ps1:104`.
- Version drift: `VERSION`, `apps/backend/pyproject.toml:`,
  `apps/desktop/package.json:4`, `apps/desktop/src-tauri/Cargo.toml:3`,
  `CHANGELOG.md:5`.
- Docs drift/NUL: `README_ZH.md:13`, `README_ZH.md:23`,
  `docs/development.md`.

## Selected gates

PR gates should be cheap source/unit/composition checks; Windows artifact smoke
may be a required workflow job with cached runtime inputs. Release jobs must
consume a tested artifact digest and reject manual refs that do not pass the
same version relation.

Version synchronization should be one parser/validator used by scripts and CI,
not a list of ad hoc string replacements. Legal/SBOM/checksum output is tied to
the runtime manifest digest.

Unsigned Beta can be shipped only with explicit documentation; production
release policy should require configured signing before public readiness claims.
