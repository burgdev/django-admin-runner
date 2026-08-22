# Proposal: xterm-terminal-output

## Why

The execution output view renders captured ANSI text as static HTML. Commands using
rich progress bars (cursor movement, line erase, redraw) explode into megabytes of
repeated frames: the page freezes, the live-output poller re-downloads the entire
field every 2 seconds, and the stored output must be truncated (losing history).
Rendering the stream through a real terminal emulator — xterm.js — in the browser
fixes all three: progress bars display as they did in a terminal, only new bytes
are polled, and the full (capped) stream can be replayed interactively.

## What Changes

- Add a delta/offset JSON endpoint per `CommandExecution` that returns only the
  output written since a given character offset (`?field=stdout|stderr&offset=N`),
  enabling cheap polling and no full-field re-downloads.
- Replace the static ANSI-to-HTML `<pre>` output rendering on the execution page
  with an xterm.js terminal widget that replays the stored stream and appends
  incremental chunks while the command runs.
- Reduce the live poll interval to ~500 ms while a command is running (delta
  requests are tiny); stop when finished.
- Fixed terminal size: globally configured dimensions (`ADMIN_RUNNER_TERM_COLS`/`ADMIN_RUNNER_TERM_ROWS`, default 120×40) are exported as `COLUMNS`/`LINES` before `call_command`, so commands (rich et al.) lay out progress bars deterministically — not caller/browser dependent.
- Reduce the DB flush interval from 2 s to 0.5 s so persisted output advances at the same cadence the widget polls.
- Raw stream retention: store the raw stream with a generous cap (new default
  ~2 MB tail per field) — no truncation marker embedded in the stream; the
  endpoint reports `truncated_head` so the widget can show a notice. Text
  storage is kept — in-process commands emit `str`, and ANSI escapes are plain
  ASCII that round-trip losslessly.
- The static ANSI-to-HTML view is removed for stdout/stderr on the execution page
  (no no-JS fallback needed); `result_html` and other page parts are unaffected.

## Capabilities

### New Capabilities

- `terminal-output-view`: xterm.js widget on the execution page — replay of stored
  stream, live append of deltas, auto-scroll, sizing from the run form.
- `output-delta-endpoint`: offset-based JSON endpoint returning only new output
  characters per field, with unchanged short-circuit.
- `launch-terminal-size`: capture of browser cols/rows at run submission and
  export as `COLUMNS`/`LINES` in the worker before command execution.

### Modified Capabilities

- `rich-result-page`: the ANSI-to-HTML `<pre>` rendering of stdout/stderr on the
  execution page is replaced by the terminal widget; URL auto-linking within
  stdout/stderr output is removed (xterm.js does not hyperlink); `result_html`
  behavior is unchanged.

## Impact

- **Dependencies**: `xterm.js` frontend assets (vendored or via CDN with SRI;
  decided in design) — no new Python dependencies.
- **Code**: `tasks.py` (`COLUMNS`/`LINES` export, retention cap), new endpoint in
  `admin.py` or `views.py`, `live-output.js` → replaced by an xterm.js widget
  module, run form (`forms.py`) gains hidden cols/rows, execution change template.
- **Data model**: no schema changes; `stdout`/`stderr` remain TextField.
- **Consumers**: integrations that scrape the `<pre class="ansi-output">` markup
  of the execution page will break (the widget replaces it). The stored field
  contents remain unchanged.
