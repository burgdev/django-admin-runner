# Design: append-flush-fast-updates

## Context

- `_LiveTtyStringIO` saves the whole buffer per flush (`O(total)` row
  rewrites), with adaptive `_FLUSH_TIERS` (0.5–10 s) as damage control.
- SQLite (WAL, busy timeout) and Postgres (TOAST) both rewrite the full stored
  value on any text UPDATE — so "append at DB level into one big field" still
  costs O(row size) per flush. Only small rows make appends cheap.
- Existing executions hold output in `CommandExecution.stdout/stderr` text
  fields; history must be preserved.

## Goals / Non-Goals

**Goals:**

- ~250 ms live updates regardless of output size; per-flush DB cost O(new
  output).
- No destructive trims — history retained up to a total cap.
- One small, straightforward migration that moves legacy output into parts
  and removes the legacy fields.

**Non-Goals:**

- Server push / SSE (polling at 250 ms; contract is forward-compatible).
- Sub-250 ms latency; multi-writer interleaving (one execution = one writer).

## Decisions

### D1: Sealed parts, 512 KB each

```python
class CommandOutputPart(models.Model):
    execution = FK(CommandExecution, CASCADE, related_name="output_parts")
    # CASCADE: deleting an execution deletes its output parts
    field = CharField(max_length=10)   # "stdout" | "stderr"
    seq = IntegerField()               # ordering within (execution, field)
    text = TextField()
    class Meta:
        constraints = [UniqueConstraint(fields=["execution", "field", "seq"])]
```

- Flush appends to the **active** (highest-seq) part via
  `F("text") + Value(chunk)`; if the part would exceed **512 KB**, it is
  sealed as-is and the append goes into a freshly created part.
- Every append therefore rewrites at most a 512 KB row — bounded, WAL-cheap.
- Part size 512 KB: ~4–8 parts per hour-long verbose run; row count trivial.
- `_LiveTtyStringIO` keeps the authoritative in-memory buffer plus a
  watermark of appended chars; at completion, `execute_command`'s final save
  appends the remaining un-flushed tail to parts (single source of truth —
  no legacy fields).

### D2: Retention by pruning sealed parts

- Total cap per field: `ADMIN_RUNNER_MAX_OUTPUT` (default 500 MB ≈ 1000
  parts) — generous history; row count stays trivial and queries only ever
  touch parts after the cursor.
- Pruning runs during flush when total size exceeds the cap and deletes only
  **sealed** parts from the front — the active part is never deleted, no
  rewrite of any stored text.

### D3: Cursor-based delta endpoint

- Client cursor: opaque string `"<seq>:<offset_in_part>"` (also accepts
  missing/`""` = replay from start).
- Response: `{chunk, cursor, finished, reset?}` where `reset: true` +
  `chunk = <all currently retained output>` happens when the client cursor
  points at a pruned part — the widget `term.reset()`s and replays. This
  replaces the old numeric-offset and `truncated_head` semantics (the
  truncation notice banner derives from `reset` + a flag).
- Reading a delta = parts with `seq > cursor.seq` (indexed query), only the
  new rows — O(new output) reads to match the writes.
- Backwards compatibility note: the previous numeric `offset` parameter is
  dropped (widget ships in the same release); the stored data is fully
  compatible via migration.

### D4: Fixed 250 ms cadence

- `_FLUSH_TIERS` / `_flush_interval_for` removed; interval constant 0.25 s;
  byte trigger (4 kB) stays for chatty bursts between ticks.
- Async-context deferral (`run_in_executor`) carries over — the append is
  still an ORM call that must not run on the event loop thread.

### D5: Data migration — parts become the only output storage

- One release, one migration chain:
  1. Create `CommandOutputPart`.
  2. Data migration: for each `CommandExecution` with non-empty
     `stdout`/`stderr`, split the content into 512 KB parts (`seq` from 0).
  3. Remove the `stdout`/`stderr` fields from `CommandExecution`.
- Reverse migration: recreate the fields and concatenate parts back
  (best-effort; retention-capped content returns in full).
- All readers (endpoint, admin templates, exports) switch to parts in the
  same release — no mixed-version reads of removed fields.

### D6: Frontend — progressive replay + immutable caching

- Poll 250 ms with the cursor token; handle `reset`.
- **Sequential replay from the beginning**: parts are fetched and written in
  order (part 0 → active part), chunked (~64 KB slices with `setTimeout(0)`
  yields). A progress bar (loaded parts / total parts) is shown while
  replaying more than a small threshold; it disappears when replay catches
  up with the active part, at which point delta polling starts. On repeat
  opens, sealed parts come from the immutable browser cache, so the progress
  bar is typically brief. Live deltas use dirty-line rendering only.
- **Immutable caching**: sealed parts are fetched whole (one request per part,
  not many small ones) with `ETag: "<execution>:<field>:<seq>"` and
  `Cache-Control: private, max-age=1y, immutable`. Repeat opens hit the
  browser cache for sealed parts; only the active part (never immutable) and
  new output are fetched. First-ever load of a huge log pays the transfer
  once — unavoidable — every later open is cheap.
- `convertEol`, scrollback (5000 lines) unchanged.

## Risks / Trade-offs

- [Migration writes GBs if many huge executions exist] → parts are capped by
  the old 2 MB field cap, so bounded; migration is idempotent and can run
  per-row lazily if ever needed.
- [`F()` concat across backends] → `||` on SQLite/Postgres, `CONCAT` on MySQL
  via Django's `F() + Value()`; tests cover SQLite, note MySQL.
- [Cursor desync after crash mid-run] → the in-memory buffer watermark and
  parts can drift briefly on a hard kill; the retained parts stay consistent
  (each append is atomic) and `reset`/replay tolerates client-side drift.
- [Row count growth] → retention pruning bounds parts per execution; CASCADE
  on execution delete.

## Migration Plan

Ship as a single release (single deployment): schema + data migration +
flush/endpoint/widget switch together. The migration chain (create parts →
copy legacy output → remove legacy fields) is transactional per database, so
there is no window with mixed storage.

## Open Questions

- Expose part size / flush interval as settings? Lean: hardcode 512 KB and
  250 ms; promote on demand.
