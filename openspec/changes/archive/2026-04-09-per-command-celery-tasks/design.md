## Context

django-admin-runner currently uses a single generic Celery task (`django_admin_runner.execute_command`) to run all registered management commands. The command name is passed as a payload argument, making all commands indistinguishable in Celery results, Flower, and monitoring tools. A separate `schedule_command` task exists for Beat periodic tasks with duplicated execution logic.

The registry already holds per-command metadata (`app_label`, `command_class`, `name`) from `@register_command()` decorators applied during Django startup. This metadata is sufficient to derive Celery task names, descriptions, and display names without any Celery-specific configuration.

## Goals / Non-Goals

**Goals:**
- One named Celery task per registered management command, named `<app_label>.<command_name>`
- Task metadata (name, description) derived from existing command metadata
- Single task per command handles both admin-triggered and Beat-triggered execution
- Optional `display_name` on `@register_command()` — generic, not Celery-specific

**Non-Goals:**
- Custom Celery task configuration per command (retry policies, rate limits, queues, etc.)
- Per-command task routing or queue assignment
- Celery canvas support (chains, groups, chords)
- Changing the non-Celery runners (sync, django-tasks)

## Decisions

### 1. Dynamic task registration during app startup

Register Celery tasks inside `autodiscover_commands()` after the command registry is populated. Use Celery's `shared_task` to create one task per command dynamically.

**Why**: The registry is fully populated by the end of `autodiscover_commands()`. Registering tasks at the same point avoids a separate registration step and keeps the user's mental model simple — decorate a command, it appears everywhere.

**Alternative considered**: Separate `register_celery_tasks()` call from `apps.py`. Rejected because it requires users to add another import/call. The single `autodiscover_commands()` should handle everything.

### 2. Task naming: `<app_label>.<command_name>`

**Why**: Matches Django's app structure. Short and readable in Flower. Risk of collision with user-defined tasks is acceptable — the namespace is predictable and documented.

**Alternative considered**: `django_admin_runner.<app_label>.<command_name>`. Rejected as unnecessarily verbose.

### 3. Unified task signature: `(kwargs=None, execution_pk=None)`

Each per-command task accepts optional `execution_pk`. When present (admin trigger), use the existing `CommandExecution`. When absent (Beat trigger), create one.

**Why**: Eliminates the separate `schedule_command` task. One task, two entry paths. The `execution_pk` is the discriminator — no ambiguity.

**Alternative considered**: Separate task classes per command. Rejected — function-based tasks with a conditional are simpler and more consistent with the current codebase.

### 4. `display_name` as generic `@register_command()` parameter

**Why**: Title-cased command name is a reasonable default, but users should be able to override it. This is useful for the admin UI command listing, not just Celery. Making it Celery-specific would be wrong — it's a display concern.

### 5. Lazy task registration — only when Celery is installed

The dynamic task registration should be guarded by a try/except on `celery` import. Projects not using Celery should not fail at startup.

**Why**: django-admin-runner supports multiple backends. The Celery-specific code should only activate when Celery is available.

## Risks / Trade-offs

- **[Breaking change for Beat users]** Users with existing Beat entries pointing to `django_admin_runner.schedule_command` must reconfigure to use per-command task names. → Mitigation: document migration clearly. The new approach is strictly better (simpler kwargs, direct task selection).
- **[Breaking change for direct task callers]** Any code calling `execute_command_task.delay()` directly must switch to per-command task names. → Mitigation: this is likely rare (internal use only). Document in changelog.
- **[Dynamic task registration]** Celery workers must run Django startup to register tasks. This is already the standard pattern for Django+Celery projects. No additional risk.
- **[Task name collisions]** `<app_label>.<command_name>` could collide with user-defined tasks. → Acceptable risk — the naming pattern is predictable and documented.
