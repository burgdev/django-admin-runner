## 1. Output delta endpoint

- [x] 1.1 Add `output` JSON view on the `CommandExecution` admin (URL + view): `?field=stdout|stderr&offset=N` → `{status, offset, chunk, finished, truncated_head}`; offset clamping/validation (400 non-numeric, 400 invalid field), permission checks mirroring the change form
- [x] 1.2 Tests: delta response, empty delta, clamping, invalid field/offset, permissions, finished flag

## 2. Raw stream storage

- [x] 2.1 Change `_tail()` usage in `tasks.py`: store the raw capped tail (no embedded marker) in the field; track truncation and prepend `ESC c` on serve when `truncated_head`
- [x] 2.2 Raise `ADMIN_RUNNER_MAX_OUTPUT` default to 2,000,000; update docs/comment
- [x] 2.3 Tests: capped field contains raw output only; truncation flag surfaced by the endpoint

## 3. Fixed terminal size

- [x] 3.1 Add `ADMIN_RUNNER_TERM_COLS`/`ADMIN_RUNNER_TERM_ROWS` settings (defaults 120/40, bounds-validated)
- [x] 3.2 `execute_command`: export `COLUMNS`/`LINES` from the settings around `call_command`, restore afterwards
- [x] 3.3 Tests: env set/restored, defaults

## 4. xterm.js widget

- [x] 4.1 Vendor xterm.js assets (pinned version) under `static/django_admin_runner/vendor/xterm/`
- [x] 4.2 New `terminal-output.js`: init terminal at the configured size, initial replay from `offset=0`, 500 ms delta polling, auto-scroll unless scrolled up, stop on `finished` with one final fetch, keep timer/status-bar behavior
- [x] 4.3 Reduce `_LiveTtyStringIO` flush interval from 2.0 s to 0.5 s (match poll cadence); keep `flush_bytes` trigger
- [x] 4.4 Replace the stdout/stderr `<pre>` rendering on the execution change form with the widget; remove `live-output.js` and the ANSI-to-HTML/URL-linking path for stdout/stderr (`result_html` untouched)
- [x] 4.5 Truncation notice line above the terminal when `truncated_head` is true

## 5. Wrap-up

- [x] 5.1 Docs: README/admin-themes guide section for the terminal view, `ADMIN_RUNNER_MAX_OUTPUT`, terminal size behavior
- [x] 5.2 Full test suite, lint, type checks; manual browser verification with a progress-bar command (e.g. cartoload `generate_maps`)
