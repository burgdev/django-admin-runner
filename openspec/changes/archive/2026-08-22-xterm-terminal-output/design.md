# Design: xterm-terminal-output

## Context

- `execute_command` captures stdout/stderr into `_LiveTtyStringIO` (a TTY-claiming
  `StringIO`) and periodically persists the full buffer to `CommandExecution`.
- The execution page converts the stored ANSI text to static HTML
  (`_linkify(_convert_ansi(...))` in a `<pre>`), and `live-output.js` re-fetches
  the **entire** field every 2 s and replaces the `<pre>` contents. Verbose
  commands (rich progress bars emit a full redraw per tick) produce multi-MB
  fields: server-side regex conversion, multi-MB DOM, frozen browsers.
- Output is currently truncated to the last ~200k characters
  (`ADMIN_RUNNER_MAX_OUTPUT`) as a stopgap — history is lost and bars still
  render as hundreds of stale lines.
- Commands run in-process via `call_command`, so captured output is Python
  `str`; ANSI escape codes are ASCII and round-trip through storage losslessly.
  No byte-level capture is required.

## Goals / Non-Goals

**Goals:**

- Terminal-accurate rendering of command output in the admin (progress bars
  behave like in a real terminal).
- Cheap live updates: poll only the delta; ~500 ms cadence.
- Commands lay out output at the viewer's terminal width at launch time.
- Retain a generous raw stream (default ~2 MB tail) replayable on page load.

**Non-Goals:**

- No-JS/email fallback rendering (not needed).
- Mid-run terminal resize (a recording cannot reflow already-written lines).
- Real pty / subprocess execution, websockets, or server push (polling suffices).
- Changes to `result_html` or the rest of the result page.

## Decisions

### D1: xterm.js client-side, fed by an offset-delta endpoint

`term.write()` is incremental: it applies only new bytes to its internal screen,
so the server is a dumb append-only character log. Server-side emulators (pyte)
were considered and rejected for the live view — they cap data beautifully but
cannot provide interactive terminal feel; pyte may return later as a flatten
pass only if a text export is ever needed.

Endpoint (staff-only, per execution):

```
GET admin/django_admin_runner/commandexecution/<pk>/output/?field=stdout&offset=N
→ {"status": "RUNNING", "offset": M, "chunk": "<chars N..M>", "finished": false}
```

- `offset` is a character offset into the stored field. Empty delta when
  nothing new (`chunk: ""`).
- Response includes `finished` (and final `status`) so the client knows when to
  stop polling.
- Initial load: `offset=0` replays the whole stored stream once. For very large
  fields the client may first write the stored tail (server returns
  `truncated_head: true` plus the pre-truncated stream) — one replay, xterm.js
  handles multi-MB writes in reasonable time.
- No JSON escaping pitfalls: `chunk` is a JSON string; ANSI bytes are ASCII.

### D2: Raw stream storage with a generous tail cap

- `ADMIN_RUNNER_MAX_OUTPUT` is reinterpreted as the **raw** cap, default raised
  to 2,000,000 characters per field.
- The stored field contains **only** raw command output — no truncation marker
  embedded. The marker confuses terminal replay; instead the endpoint exposes
  `truncated_head` and the widget shows a notice line above the terminal.
- If a capped stream starts mid-escape-sequence, xterm.js discards the dangling
  sequence — acceptable; a leading `ESC c` (reset) is prepended server-side when
  `truncated_head` is true to guarantee a clean screen state.
- DB write pattern: flush every 0.5 s / 4 kB (interval reduced to match the
  poll cadence — see D4).

### D3: Fixed terminal size (configuration, not caller-dependent)

- Terminal dimensions are a **global setting**, not per-launch input:
  `ADMIN_RUNNER_TERM_COLS` (default 120) and `ADMIN_RUNNER_TERM_ROWS`
  (default 40), validated at settings load to sane bounds.
- `execute_command` exports them as `COLUMNS`/`LINES` for the duration of
  `call_command` (restored afterwards); `os.get_terminal_size()` and rich
  honor these env vars.
- The xterm widget always initializes at the configured size — deterministic
  replay, identical layout for every execution, no form fields, no per-run
  data on `CommandExecution`. Changing the size is an operator decision
  (settings), applying to future runs.

### D4: Widget replaces the `<pre>`; flush cadence matches poll cadence

- New static module `terminal-output.js` (+ vendored xterm.js assets under
  `static/django_admin_runner/vendor/xterm/`) — no CDN dependency, works
  offline/air-gapped; vendored files pinned to a fixed version.
- On load: create terminal at the configured size, replay stored stream,
  start delta polling at 500 ms; auto-scroll to bottom unless the user scrolled
  up (existing behavior); timer/status-bar logic moves into the new module.
- **Flush interval reduced from 2.0 s to 0.5 s** (`_LiveTtyStringIO`) so new
  output is persisted at the same cadence it is polled — otherwise 3 of 4
  polls would return empty deltas. The byte trigger (`flush_bytes`) stays as a
  second condition. A single-row `UPDATE ... SET stdout=...` twice per second
  per running command is negligible DB load for an admin tool.
- Polling stops when `finished: true`; a final full refresh ensures the last
  flush (saved after `finished_at`) is captured — the endpoint serves the
  authoritative final field content.
- ANSI-to-HTML conversion and URL auto-linking for stdout/stderr are removed
  from the change-form rendering (widget replaces it); `result_html` is untouched.

### D5: Permissions & safety

- Endpoint reuses the `CommandExecution` view/change permission checks
  (staff + model permission), returns 403/404 accordingly.
- `offset` clamped to `[0, len(field)]`; non-numeric → 400.
- Polling requests are cheap (one indexed PK lookup + string slice), so 0.5 s
  cadence for a handful of admins is negligible; no rate limiting added.

## Risks / Trade-offs

- [Multi-MB initial replay is slower than a snapshot] → Acceptable one-time cost;
  default cap bounds it; increase cap only consciously.
- [Truncated head means older history is gone] → Same as the status quo stopgap,
  but 10× more retained; documented.
- [Browser find-in-page cannot see virtualized scrollback] → xterm's own search
  addon can be enabled later; out of scope.
- [Vendored xterm.js adds ~300 KB static assets] → Pinned version, served with
  far-future cache headers; admin-only.
- [Clients scraping the old `<pre>` markup break] → Documented in the proposal;
  stored data unchanged.

## Migration Plan

1. Add endpoint + widget behind the existing page (no data changes). Deploy-safe.
2. Switch the execution page template to the widget; remove old JS.
3. Raise `ADMIN_RUNNER_MAX_OUTPUT` default; existing executions replay as-is
   (their stored text is already raw).
- Rollback: revert template/JS; endpoint is inert.

## Open Questions

- Store `term_cols`/`term_rows` on `CommandExecution` (new small fields +
  migration) or only pass them to the env? Preferred: store — the widget needs
  the recorded width for faithful replay.
- Poll cadence setting (`ADMIN_RUNNER_POLL_INTERVAL_MS`, default 500) — expose
  or hardcode? Lean: hardcode 500 ms for now.
