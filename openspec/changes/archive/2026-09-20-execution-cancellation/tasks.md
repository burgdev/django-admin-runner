- [x] 1. Model: add `stop_requested` and `worker_pid` fields and
  `Status.CANCELLED` (check constraint update) + migration
- [x] 2. tasks.py: `CommandCancelledError`; record `worker_pid` on
  RUNNING transition; conditional-update final save; idempotency guard
  for duplicate attempts (terminal-state bail)
- [x] 3. tasks.py: stop-flag check on the `_LiveTtyStringIO` flush
  heartbeat (once per flush interval, RUNNING only) raising
  `CommandCancelledError`; CANCELLED finalization preserving output and
  appending a "Cancelled by <user>" line to stderr
- [x] 4. Distinguish SIGTERM-from-stop vs cluster shutdown in the SIGTERM
  handler (stop flag → `CommandCancelledError`)
- [x] 5. Runner API: `BaseCommandRunner.stop(execution, requested_by)`
  (graceful) and `force_stop(execution)` (default no-op), plus a
  `supports_force_stop` flag (True for celery, django-q2)
- [x] 6. Celery runner: graceful `revoke(terminate=True, SIGTERM)`,
  force `revoke(terminate=True, SIGKILL)`
- [x] 7. django-q2 runner: enqueue with retry disabled; PID verification
  (start time / cmdline via `/proc`) before SIGTERM (graceful) and
  SIGKILL (force) on `worker_pid`
- [x] 8. Admin: stop endpoint (POST with `force` flag, permission-gated,
  conditional on status=RUNNING, idempotent; graceful sets flag +
  runner signal, force calls runner force kill), `has_stop_permission`
  defaulting to change permission
- [x] 9. UI base theme: stop control on change page — "Stop" while
  RUNNING without request, "Force Stop" while RUNNING with request,
  nothing otherwise; hidden Force Stop on backends without support
- [x] 10. UI Unfold theme: same control in Unfold styling
- [x] 11. UI live run/result view: stop control in header with same
  state logic; poller re-renders the button from status/flag
- [x] 12. Status display: CANCELLED badge/filters (base + Unfold)
- [x] 13. Tests: graceful stop via flag (printing command), SIGTERM →
  CANCELLED, manual force kill (second request), no auto-escalation,
  retry/idempotency guard, button state matrix (statuses ×
  stop_requested × permissions × backend support), completion race,
  PID verification
- [x] 14. Docs: README/docs section — stop semantics (graceful first,
  explicit force kill, user-controlled timing), backend support matrix
  (forced unsupported on sync/django-tasks)
