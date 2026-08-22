## ADDED Requirements

### Requirement: Sealed-part output storage
Command output SHALL be stored as an ordered sequence of `CommandOutputPart` rows (per execution and field), each holding at most 512 KB of text. Flushes SHALL append at the database level to the single active part; when a part would exceed 512 KB it SHALL be sealed and a new part started. Existing `stdout`/`stderr` contents SHALL be migrated into parts, preserving history.

#### Scenario: Flush appends only new characters
- **WHEN** output is written past the flush watermark
- **THEN** an update appends exactly the new characters to the active part and no other part is rewritten

#### Scenario: Part sealing
- **WHEN** an append would grow the active part beyond 512 KB
- **THEN** the part is sealed and the characters go into a newly created part

#### Scenario: Migration preserves history and drops legacy fields
- **WHEN** the data migration runs for an execution with a populated legacy field
- **THEN** its content is split into ≤512 KB parts in order, byte-identical when concatenated, and the legacy `stdout`/`stderr` fields are removed afterwards

#### Scenario: Flush from async context
- **WHEN** output is written from inside a running asyncio event loop
- **THEN** the append is deferred to a thread and no `SynchronousOnlyOperation` is raised

### Requirement: Fixed 250 ms flush cadence
Flushes SHALL occur on a fixed ~250 ms interval (plus the byte trigger), independent of total output size. The adaptive buffer-size flush tiers SHALL be removed.

#### Scenario: Large output still flushes at 250 ms
- **WHEN** several megabytes have been written and new output arrives
- **THEN** the next flush happens within ~250 ms and appends only the new characters

### Requirement: Retention by pruning sealed parts
When the total retained output for a field exceeds `ADMIN_RUNNER_MAX_OUTPUT` (default 500 MB), the oldest **sealed** parts SHALL be deleted. The active part SHALL never be pruned and no stored text SHALL be rewritten for retention.

#### Scenario: Pruning drops oldest history only
- **WHEN** total retained output exceeds the cap
- **THEN** sealed parts are deleted from the front until within the cap, and the active part and newer sealed parts are untouched

### Requirement: Cursor delta endpoint with reset
The output endpoint SHALL accept an opaque cursor (`seq:offset`), returning only output written after it (`chunk`, new `cursor`, `finished`). When the client cursor refers to pruned parts, the endpoint SHALL respond with `reset: true` and the full retained output so the client can reset and replay.

#### Scenario: Delta request
- **WHEN** the client polls with a valid cursor and new output exists
- **THEN** the response contains only the new characters and the advanced cursor

#### Scenario: Reset after pruning
- **WHEN** the client cursor points at a pruned part
- **THEN** the response contains `reset: true` with the full retained output and its cursor

### Requirement: Sequential terminal replay with progress
The terminal widget SHALL replay the retained output from the beginning, part by part in order, in slices (~64 KB per write, yielding between slices) without blocking the page. While replaying content large enough to take noticeable time, the widget SHALL show a progress bar reflecting loaded parts versus total. Live delta polling starts once the replay catches up with the active part. On `reset` (pruning) the widget clears the terminal and replays the retained output the same way. Live deltas append incrementally with dirty-line rendering (no full redraws).

#### Scenario: Multi-megabyte replay does not block
- **WHEN** the execution page is opened for a large retained output
- **THEN** the widget replays slices with yields and the page stays responsive

#### Scenario: Progress bar during large replay
- **WHEN** retained output exceeds a small threshold (e.g. a few parts)
- **THEN** a progress bar shows how much of the output has been loaded and disappears when replay completes

#### Scenario: Live deltas do not redraw history
- **WHEN** new output arrives while polling
- **THEN** only the new characters are written and only affected rows are repainted

### Requirement: Immutable caching of sealed parts
Part fetches SHALL be served with strong validator headers (`ETag` of execution/field/seq) and, for **sealed** parts, `Cache-Control` marking them immutable, so repeat opens are served from the browser cache. The active (last) part SHALL NOT be marked immutable and is read via the cursor delta path.

#### Scenario: Repeat open served from cache
- **WHEN** an execution page is opened a second time
- **THEN** sealed parts come from the browser cache and only the active part and new output are fetched from the server

#### Scenario: Active part never cached as immutable
- **WHEN** the active part is fetched
- **THEN** the response does not claim immutability

### Requirement: Output parts cascade on execution deletion
Output parts SHALL be deleted together with their `CommandExecution` (foreign-key cascade), so deleting an execution removes its logs entirely.

#### Scenario: Deleting an execution removes its output
- **WHEN** a `CommandExecution` with output parts is deleted
- **THEN** all of its `CommandOutputPart` rows are deleted as well
