- [x] 1. Model: `Status.TIMEOUT` ("Timed out"), check-constraint update,
  migration
- [x] 2. tasks.py: classify `SoftTimeLimitExceeded` (defensive import) in
  the exception path → TIMEOUT with traceback; stop-request precedence
  kept
- [x] 3. Sweeper `sweep_stale_executions()` (tasks.py or sweeps.py):
  RUNNING + non-null `worker_pid` + PID dead (os.kill signal 0) +
  `started_at` past grace; legacy NULL-PID rows past
  `ADMIN_RUNNER_STALE_AFTER` (default 1 h); conditional
  `status=RUNNING` updates; cause note appended to stderr; never raises
- [x] 4. Runner API: `BaseCommandRunner.finalize_stale(execution)` →
  `None` default (caller falls back to FAILED/"worker lost")
- [x] 5. django-q2 `finalize_stale`: look up the task id in q2 Task /
  Failure records → TIMEOUT/FAILED with backend note (try/except
  guarded)
- [x] 6. Celery `finalize_stale`: AsyncResult state inspection →
  TIMEOUT/FAILED (try/except guarded)
- [x] 7. Admin wiring: run the sweeper in `change_view` and in
  `_output_view`, rate-limited per process to
  `ADMIN_RUNNER_SWEEP_INTERVAL` seconds (default 30)
- [x] 8. Status display: TIMEOUT badge (colors/icons in admin.py and
  terminal-output.js), `finished` includes TIMEOUT, result footer
  "Timed out" (base + Unfold), list filter choice
- [x] 9. Tests: soft-limit mapping, stop precedence, PID-dead sweep,
  live-worker not swept, legacy age sweep, race (conditional update),
  q2/celery attribution incl. fallback, badge/footer, sweep
  rate-limiting
- [x] 10. Docs: stopping-commands guide or new section — timeout
  semantics, sweeper settings (`ADMIN_RUNNER_SWEEP_INTERVAL`,
  `ADMIN_RUNNER_STALE_AFTER`), backend hard-limit configuration advice
  (q2 `Q_CLUSTER["timeout"]`, Celery soft/hard `time_limit`)
