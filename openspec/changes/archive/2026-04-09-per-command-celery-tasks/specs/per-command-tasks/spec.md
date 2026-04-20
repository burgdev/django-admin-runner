## ADDED Requirements

### Requirement: Per-command Celery task registration
The system SHALL register one Celery `shared_task` per management command in the registry. Each task SHALL be named `<app_label>.<command_name>` (e.g., `books.import_books`). Registration SHALL occur automatically during `autodiscover_commands()` after the command registry is populated. Registration SHALL be a no-op when Celery is not installed.

#### Scenario: Command registered as Celery task
- **WHEN** a management command `import_books` in app `books` is registered via `@register_command()`
- **THEN** a Celery task named `books.import_books` is available and callable

#### Scenario: Celery not installed
- **WHEN** Celery is not installed and `autodiscover_commands()` runs
- **THEN** command registration completes without error and no Celery tasks are registered

### Requirement: Task description from command help
Each per-command Celery task SHALL have its description set from the `help` attribute of the Django `BaseCommand` class. If `help` is empty or not set, the description SHALL be empty.

#### Scenario: Command has help text
- **WHEN** a command class defines `help = "Import books from a source file"`
- **THEN** the Celery task description is `"Import books from a source file"`

#### Scenario: Command has no help text
- **WHEN** a command class does not define `help` or sets it to `""`
- **THEN** the Celery task description is `""`

### Requirement: Unified task execution flow
Each per-command Celery task SHALL accept `kwargs=None` and `execution_pk=None`. When `execution_pk` is provided, the task SHALL use the existing `CommandExecution` record. When `execution_pk` is not provided, the task SHALL create a new `CommandExecution` record with `backend="celery"` before executing.

#### Scenario: Admin-triggered execution with existing record
- **WHEN** the task is called with `execution_pk=42` and `kwargs={"source": "books.csv"}`
- **THEN** the task loads `CommandExecution` pk 42 and runs the command with the given kwargs

#### Scenario: Beat-triggered execution without existing record
- **WHEN** the task is called with `kwargs={"source": "books.csv"}` and no `execution_pk`
- **THEN** the task creates a new `CommandExecution` record with `backend="celery"` and runs the command

### Requirement: CeleryCommandRunner uses per-command tasks
`CeleryCommandRunner` SHALL look up the per-command Celery task by command name and dispatch to it, instead of calling a generic `execute_command_task`.

#### Scenario: Runner dispatches to named task
- **WHEN** `CeleryCommandRunner.run("import_books", ...)` is called
- **THEN** it resolves and calls the `books.import_books` Celery task with `execution_pk` set

### Requirement: Generic tasks removed
The generic `django_admin_runner.execute_command` and `django_admin_runner.schedule_command` tasks SHALL be removed.

#### Scenario: Generic tasks no longer exist
- **WHEN** the module is imported
- **THEN** no task named `django_admin_runner.execute_command` or `django_admin_runner.schedule_command` is registered

### Requirement: Optional display_name on register_command
`@register_command()` SHALL accept an optional `display_name` parameter. When provided, it SHALL be stored in the registry entry. When not provided, the system SHALL derive a display name by replacing underscores with spaces and title-casing the command name (e.g., `import_books` → `"Import Books"`).

#### Scenario: Explicit display_name
- **WHEN** `@register_command(display_name="Import Books from CSV")` decorates a command
- **THEN** the registry entry contains `display_name="Import Books from CSV"`

#### Scenario: Default display_name
- **WHEN** `@register_command()` decorates a command named `import_books` without `display_name`
- **THEN** the registry entry contains `display_name="Import Books"`
