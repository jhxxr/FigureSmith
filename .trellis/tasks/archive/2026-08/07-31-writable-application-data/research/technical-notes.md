# Writable Data Technical Notes

## Existing contract and defect

`get_app_data_dir()` documents first-writable resolution, but its explicit
override branch ignores `_ensure_writable_dir()`'s false result. The desktop
turns executable-adjacent data into that explicit override, preventing the
documented LocalAppData fallback in Program Files.

Source anchors:

- `apps/backend/figuresmith/models/paths.py:33`: current write probe.
- `apps/backend/figuresmith/models/paths.py:60`: documented resolution order.
- `apps/backend/figuresmith/models/paths.py:74`: ignored override probe result.
- `apps/desktop/src-tauri/src/sidecar.rs:89`: forced adjacent override.
- `apps/desktop/src-tauri/src/commands.rs:179`: separately guessed model path.
- `vendor/autofigure_edit/server.py:25`: source-relative upload/output roots.

## Selected layout

```text
<data-root>/
  settings.json
  models/
  jobs/
  uploads/
  outputs/
  temp/
  logs/
  cache/svg-sanitized/
```

The application records the canonical resolved root in app state. APIs and
native operations consume it instead of calling independent environment/path
helpers per request.

## Write probe

The probe creates a unique private subdirectory/file, writes and flushes bytes,
atomically replaces a sibling file, and removes both. It does not leave a test
file behind. Permission, path length, antivirus/locking, and invalid-path errors
are categorized without exposing secrets.

## Release versus development

Release startup passes `FIGURESMITH_INSTALL_ROOT` but does not convert its data
candidate into `FIGURESMITH_DATA_DIR`. Python may therefore fall through after
a failed probe. An actual user override remains authoritative and fails early if
invalid. Repository data is considered only under an explicit development flag.
