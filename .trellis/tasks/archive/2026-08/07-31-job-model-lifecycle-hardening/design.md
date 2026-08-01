# Job and Model Lifecycle Hardening Design

## Job state and ownership

`JobManager` is a backend application service with a bounded queue and one
active GPU job by default. It owns a `JobRecord` containing ID, kind, state,
progress, timestamps, cancellation, timeout, redacted error, and temp root.
Generation and long imports use the same controller interface so cancellation,
tree termination, and cleanup do not diverge.

Requests that exceed the configured queue return a stable capacity error or are
queued according to the documented policy. An idempotency key prevents double
clicks from launching duplicate work. Status polling/SSE stays compatible with
existing UI data while adding fields.

## Process and shutdown flow

```text
accepted -> queued -> running -> success
                    |   |  \
                    |   |   -> timeout/cancel -> tree kill -> cleaned
                    |   -> child failure -> failed -> cleaned
shutdown -> stop intake -> cancel/settle -> reap -> recover journals -> exit
```

The controller owns the backend child input pipe and process tree. Graceful
shutdown waits a bounded period, then forcefully terminates remaining trees.
Startup recovery handles journals left by a crash or forced termination.

## Secure child input

The parent passes only nonsecret flags and writes a size-limited versioned JSON
envelope to stdin. Provider keys, method text, and session credentials never
enter argv or inherited environment. The child validates the envelope before
work; malformed/oversized input fails without partial output.

## Model/import transactions

All model managers share a process-wide lock. Import creates a destination-
volume staging directory, streams through resource/overlap checks, verifies the
full inventory, writes a journal marker, atomically promotes, then updates
settings with compare-and-replace. A failure retains the prior destination and
marks/cleans the journal deterministically.

Archive extraction enforces compressed/uncompressed/member/depth limits and
rejects symlink/reparse/UNC or overlapping source/destination paths. Directory
copy uses the same counters and containment helper.

## Integrity and status

The trusted model manifest covers executable Python/config files, all sharded
weights, metadata, source revision, and license. The manager computes the full
inventory at import and before execution. Status fields are:

```text
configured -> structurally_valid -> integrity_verified -> runtime_loaded
```

Only the final state is runtime-loaded; a child process loading a model does not
mutate global loaded state. Production mode refuses an unverified code pack.

## Compatibility and rollback

Existing `/api/run` and import endpoints can return a job ID while retaining
accepted request fields. Existing completed outputs remain readable. No model
weights are deleted or redistributed. A failed migration/transaction rolls back
the promoted destination and settings marker rather than guessing.

## Deferred risk

Hardware-specific scheduling and long-term queue persistence can follow this
task; the bounded single-slot and crash recovery contract is the baseline.
