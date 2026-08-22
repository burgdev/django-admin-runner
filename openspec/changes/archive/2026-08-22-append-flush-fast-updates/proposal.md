# Proposal: append-flush-fast-updates

## Why

Live output flushing currently rewrites the **entire** captured buffer to
`CommandExecution.stdout/stderr` on every flush. To keep DB cost bearable, the
flush interval adapts to the buffer size (`_FLUSH_TIERS`: 0.5 s → 10 s for
large buffers), so long-running verbose commands update the terminal view only
every few seconds — and each update is a multi-megabyte row rewrite. We want
~250 ms live updates at any output size, with per-flush DB cost proportional to
new output only, and without destroying output history.

## What Changes

- New model `CommandOutputPart`: output is stored as an ordered sequence of
  immutable **parts** (`execution` FK, `field` stdout/stderr, `seq`, `text`),
  each up to **512 KB**. All flushes append at DB level (`F() + Value()`) to
  the single *active* (last) part; when a part would exceed 512 KB it is
  sealed and a new empty part becomes active.
- Data migration: existing `CommandExecution.stdout`/`stderr` contents are
  written into parts (split at 512 KB), preserving history; the legacy fields
  are then **removed** — parts are the single source of truth for output.
- Fixed **250 ms** flush cadence (adaptive `_FLUSH_TIERS` removed; byte
  trigger stays). Appends only ever rewrite a ≤512 KB row — trivial for SQLite
  WAL and Postgres alike.
- Retention = total cap per field (`ADMIN_RUNNER_MAX_OUTPUT`, default 500 MB):
  pruning **deletes the oldest sealed parts** only — never touches the active
  part, no destructive trims, history kept up to the cap.
- Delta endpoint moves to a `(seq, offset-in-part)` cursor (opaque `cursor`
  token to clients); response contract otherwise unchanged (`chunk`,
  `finished`), plus `reset` when the client cursor predates pruned parts (the
  response then contains the full current output so the widget can
  `term.reset()` and replay).
- Widget: poll 250 ms; sequential replay from the beginning in chunked
  slices with a progress bar for large content; handle `reset`.
- The legacy `stdout`/`stderr` TextFields are dropped after migration; the
  completion path appends the remaining buffer to parts (no separate
  snapshot storage).

## Capabilities

### New Capabilities

- `append-flush`: sealed-part output storage, DB-level append flushes, fixed
  250 ms cadence, retention by part pruning, cursor delta endpoint with
  `reset`, chunked terminal replay, data migration from the legacy fields.

## Impact

- **Data model**: new `django_admin_runner_commandoutputpart` table; the
  `stdout`/`stderr` fields on `CommandExecution` are removed (schema + data
  migration in one release).
- **Code**: `tasks.py` (`_LiveTtyStringIO` rework, seal/prune logic), models,
  output endpoint (cursor), `terminal-output.js` (250 ms poll, chunked replay,
  reset).
- **Task managers**: none — persistence stays inside django-admin-runner
  (q2/Celery/Django Tasks/sync unaffected); async-context deferral carries
  over to appends.
- **Settings**: `ADMIN_RUNNER_MAX_OUTPUT` becomes the per-field total
  retention cap (default 500 MB); part size fixed at 512 KB. Deleting a
  `CommandExecution` deletes its output parts (FK cascade).
