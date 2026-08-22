## 1. Model + migration

- [x] 1.1 Add `CommandOutputPart` model (execution FK CASCADE, field, seq, text; unique constraint `(execution, field, seq)`, index for tail queries) + schema migration
- [x] 1.2 Migration chain: (a) create `CommandOutputPart`, (b) data migration splitting existing non-empty `stdout`/`stderr` into ≤512 KB parts (seq from 0), (c) remove the legacy fields from `CommandExecution`; reverse migration concatenates parts back; update all readers (admin templates, endpoint) to parts
- [x] 1.3 Tests: migration splits/joins byte-identically, reverse works, empty fields skipped, fields removed

## 2. Append flush core

- [x] 2.1 Rework `_LiveTtyStringIO`: watermark of appended chars; `_flush` appends `buffer[watermark:]` to the active part via `F("text") + Value(chunk)` (async-context `run_in_executor` deferral kept); seal-and-start-new-part at 512 KB; fixed 0.25 s interval, byte trigger stays; delete `_FLUSH_TIERS`/`_flush_interval_for`
- [x] 2.2 Retention: during flush, when total per field exceeds `ADMIN_RUNNER_MAX_OUTPUT` (default 500 MB), delete oldest sealed parts (never the active part); test that deleting an execution cascades to its parts
- [x] 2.3 Final save in `execute_command`'s `finally` appends the remaining un-flushed tail to parts (no legacy fields)
- [x] 2.4 Tests: append-only (other parts untouched), sealing at 512 KB, pruning drops oldest sealed only, async-context append deferred, 250 ms cadence regardless of size

## 3. Delta endpoint

- [x] 3.1 Replace numeric `offset` with opaque cursor (`seq:offset`); response `{chunk, cursor, finished, reset?}`; `reset: true` + full retained output when the cursor predates pruned parts; keep permission checks
- [x] 3.2 Tests: delta, empty delta, reset after pruning, invalid cursor, permissions, finished flag

## 4. Frontend

- [x] 4.1 `terminal-output.js`: cursor-based polling at 250 ms; handle `reset` (`term.reset()` + replay served output); truncation notice on reset
- [x] 4.2 Chunked initial replay (~64 KB slices, yield between writes), then start polling
- [x] 4.3 Manual verification: long verbose command (e.g. cartoload `generate_maps`) — ≤~0.5 s perceived live updates, large-log open responsive, backfill + cache hit on re-open, prune/reset path exercised

## 5. Wrap-up

- [x] 5.1 Docs: README section (parts model, 512 KB parts, 2 MB retention, cursor endpoint, 250 ms updates)
- [x] 5.2 Full test suite, lint, type checks
