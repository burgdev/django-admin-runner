<!-- Auto generated. Run 'just release' in order to update -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-20

#### 🚀 Features

- xterm.js terminal output, scheduling, cancellation, and execution UX overhaul ([#7](https://github.com/burgdev/django-admin-runner/pull/7))
  - **Live terminal output** — stdout/stderr render in an embedded, vendored xterm.js terminal (no CDN): ANSI colors and progress bars display as in a real terminal, replacing the old ANSI-to-HTML conversion; cursor-based delta polling every 250 ms transfers only new characters regardless of output size
  - **Scalable output storage** — append-only 512 KB `CommandOutputPart` rows with browser-cacheable sealed parts and a 500 MB retention cap per field (`ADMIN_RUNNER_MAX_OUTPUT`); deterministic terminal layout via `ADMIN_RUNNER_TERM_COLS`/`TERM_ROWS` (exported as `COLUMNS`/`LINES`) and per-command `flush_interval`
  - **Scheduling** — interactive "Add schedule" admin UI (cron / interval / one-off) and declarative `@register_command(schedule=…)` via `CronSchedule` / `IntervalSchedule` / `ClockedSchedule`, materialized into django-q2's native periodic tasks with an overlap guard and one-off auto-disable
  - **Cancellation & timeouts** — graceful Stop via the output-flush heartbeat escalating to Force Stop (Celery `revoke(terminate=True)`, django-q2 PID-targeted kill); new `TIMEOUT` status with Celery soft-limit mapping (detected by class name regardless of Celery's presence) and a stale-run sweeper that finalizes executions of dead workers
  - **Execution page UX** — output/stderr/result tabs, rerun action prefilled with the original parameters, run labels, schedule filter, and status badges on a redesigned changelist

#### 🐛 Fixes

- Improve subtitle in admin view ([#6](https://github.com/burgdev/django-admin-runner/pull/6))
- Fixed parameter type parsing ([#5](https://github.com/burgdev/django-admin-runner/pull/5))

## [0.1.0] - 2026-04-08

### Features

- Initial release
- `@register_command` decorator with `group`, `permission`, `params`, `exclude_params`, and `models` support
- Auto-generated forms from argparse introspection
- Pluggable task runners: `SyncCommandRunner`, `DjangoTaskRunner`, `CeleryCommandRunner`
- `CommandRunnerModelAdminMixin` for attaching run links to model admin pages
- Plain Django admin and Unfold admin support
- `CommandExecution` model with full audit trail
