# Job and Model Lifecycle Technical Notes

## Source anchors

- Child process launch: `vendor/autofigure_edit/server.py:371`.
- Unbounded run launch: `vendor/autofigure_edit/server.py:184`.
- Forced shutdown: `apps/backend/figuresmith/api/system_routes.py:308`.
- Desktop timeout: `apps/desktop/src-tauri/src/commands.rs:23`.
- Directory import: `apps/backend/figuresmith/models/import_rmbg.py:283`.
- Partial RMBG integrity path: `apps/backend/figuresmith/models/import_rmbg.py:349`.
- Runtime trust flag: `vendor/autofigure_edit/autofigure2.py:2347`.
- Unpinned model manifest: `resources/model-manifest.json:36`.

## Selected job model

The backend owns a bounded job manager with a single GPU execution slot by
default. API calls return stable IDs; status/progress/cancel are additive. Each
job owns its temp directory and child process controller. A Windows Job Object
or equivalent tree mechanism is preferred so descendants cannot survive a
parent cancel/close.

## Selected secret transport

Use a nonsecret child flag and one bounded versioned JSON envelope over stdin,
then close stdin. Construct child environments from an allowlist. Redaction is
centralized for argv, logs, exceptions, and status.

## Selected model integrity

Import records a full relative-file inventory and hashes all executable/code
files plus all weight shards. A release trusted manifest records source/revision,
allowed files, hashes, and license. Production execution requires a full match;
unverified imports remain non-runnable.

## Recovery shape

`jobs/<id>/journal.json` records staged, verified, promoted, and settings-updated
markers. Startup scans incomplete journals and either removes staging or restores
the prior destination. A process-wide lock protects manager/settings operations.
