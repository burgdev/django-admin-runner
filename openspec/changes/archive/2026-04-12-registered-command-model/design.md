## Context

django-admin-runner currently discovers management commands at import time via `@register_command` decorators, storing them in an in-memory `_registry` dict (`registry.py`). The admin UI renders a custom command list view (`_command_list_view`) using a template, and the admin index page relies on a broken template override (`admin/index.html`) that never loads due to Django's `APP_DIRS` template resolution order (Django's built-in admin template always wins).

`CommandExecution` records each run with a `command_name` CharField — no link to any command metadata beyond the name string.

The classic Django admin has no sidebar customization API (unlike Unfold's `SIDEBAR.navigation`), so adding persistent navigation entries requires either a model-backed changelist or fragile template hacks.

## Goals / Non-Goals

**Goals:**
- Provide a database-backed `RegisteredCommand` model that mirrors `_registry` entries
- Sync `_registry` → DB on every app startup via `AppConfig.ready()`
- Give classic admin users a native changelist for commands with search, filter, and "Run" action links
- Preserve historical execution data even when commands are renamed or removed from code
- Add an optional FK from `CommandExecution` to `RegisteredCommand` for convenient filtering

**Non-Goals:**
- Bidirectional sync (DB → registry). The in-memory `_registry` remains the single source of truth.
- Making `RegisteredCommand` editable from the admin (it's read-only; metadata comes from code).
- Removing the existing command list template views — they continue to work as-is.
- Adding per-command permissions at the DB level (the existing `permission` mechanism in `_registry` remains authoritative).

## Decisions

### 1. `RegisteredCommand` model fields

**Decision**: Store `name` (unique), `group`, `display_name`, `description`, `active`, `app_label`, `created_at`, `updated_at`.

**Rationale**: These fields come directly from `_registry` entries. `name` is the natural key (matches command name). `active` tracks whether the command is still present in `_registry`. Timestamps are useful for auditing. No `permission` field — that stays in the registry and is checked at runtime.

### 2. No FK from `CommandExecution` to `RegisteredCommand`

**Decision**: Do NOT add a FK. Keep `command_name` as the sole reference on `CommandExecution`.

**Rationale**:
- `command_name` is already stored and works fine for display.
- A FK would be nullable (executions can run before the model syncs, or for commands not in the registry).
- A FK creates coupling that makes historical data fragile — if a `RegisteredCommand` is deactivated, the FK still works, but if it's somehow deleted, executions lose their link.
- Filtering executions by command is already possible via `?command_name=cleanup_books` query parameter (already used in templates).
- The admin can still show a filtered changelist link via URL params — no FK needed.

### 3. Sync strategy: soft-delete only

**Decision**: Commands in the DB but not in `_registry` get `active=False`. They are never deleted. New commands are created. Existing commands have `group`, `display_name`, `description` updated if changed.

**Rationale**: Historical data (`CommandExecution` rows) references commands by name. Keeping deactivated rows preserves the ability to filter executions by deactivated commands and provides an audit trail of what commands existed.

### 4. Sync happens in `AppConfig.ready()`

**Decision**: After `autodiscover_commands()` populates `_registry`, call a sync function that reconciles `_registry` with `RegisteredCommand` rows.

**Rationale**: `ready()` is called once on startup, after all apps are imported. At this point `_registry` is fully populated. The sync is fast (one query + upserts). A `migrate`-style management command is unnecessary complexity for what amounts to ~10 rows.

**Alternative considered**: Management command (`sync_commands`). Rejected because it requires manual intervention and would drift between runs. Startup sync is automatic and always current.

### 5. `RegisteredCommandAdmin` is read-only with superuser delete

**Decision**: Register `RegisteredCommand` with a `ModelAdmin` that disables add and change for all users. Allow delete for superusers only (useful for manually cleaning up deactivated commands). Add a custom `run_button` column (like `result_button` on `CommandExecutionAdmin`) that links to the existing `_command_run_view`. Only show active commands by default, with a `list_filter` for `active`.

**Rationale**: The model is a projection of code-level configuration. Allowing edits would create drift between `_registry` and the DB. Deletion is safe because there's no FK from `CommandExecution` — the `command_name` string on executions is independent. Superusers may want to clean up old deactivated commands manually.

### 6. Remove broken `admin/index.html` template

**Decision**: Delete `src/django_admin_runner/templates/admin/index.html`.

**Rationale**: It never loads (Django's `APP_DIRS` order means `django.contrib.admin`'s template is found first). The `RegisteredCommand` changelist replaces the need for it.

## Risks / Trade-offs

- **Startup performance** → Sync adds one DB query + upserts on every `ready()`. For typical deployments (~10-50 commands), this is negligible. Mitigated by using `bulk_create`/`bulk_update` for efficiency.
- **No FK on CommandExecution** → Cannot do `JOIN`-based queries from command to executions efficiently. Acceptable because the existing `command_name` filter already works and the admin uses URL params for cross-linking.
- **Template override removal** → Anyone who manually placed our template in `DIRS` to make it work would lose that. Low risk — the template was broken out of the box.
- **Registry is still source of truth** → If someone queries `RegisteredCommand` directly, they might see stale data between restarts. Mitigated by documenting that the model is a cached projection.
