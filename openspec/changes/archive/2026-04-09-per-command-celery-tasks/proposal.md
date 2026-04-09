## Why

All registered management commands route through a single generic Celery task (`django_admin_runner.execute_command`). This makes every command appear identical in Celery results, Flower, and monitoring tools — the actual command name is buried in the task payload. A separate `schedule_command` task for Beat duplicates execution logic with a slightly different signature.

## What Changes

- Register one named Celery task per registered management command using the `<app_label>.<command_name>` naming pattern (e.g., `books.import_books`).
- Derive task name, description, and display name from existing metadata — no Celery-specific configuration on `@register_command()`.
- Add optional generic `display_name` parameter to `@register_command()`, defaulting to title-cased command name.
- Each per-command task handles both admin-triggered execution (with existing `execution_pk`) and Beat-triggered execution (creates `CommandExecution` automatically).
- Refactor `CeleryCommandRunner` to look up the per-command task instead of calling a generic wrapper.
- **Drop `schedule_command`** — each per-command task works directly with Celery Beat.
- **Drop generic `execute_command_task`** — replaced by per-command tasks.

## Capabilities

### New Capabilities
- `per-command-tasks`: Dynamic registration of one Celery task per registered management command, with unified admin/Beat execution flow.

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- **Files changed**: `registry.py`, `celery_tasks.py`, `runners/celery.py`, `apps.py`
- **Breaking for Beat users**: `django_admin_runner.schedule_command` removed; users must reconfigure Beat entries to use per-command task names.
- **Breaking for direct task callers**: `django_admin_runner.execute_command` removed; callers must use the new per-command task names.
- **Dependencies**: No new dependencies — uses existing Celery `shared_task`.
