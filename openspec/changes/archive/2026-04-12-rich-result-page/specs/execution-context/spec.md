## ADDED Requirements

### Requirement: Per-execution context via contextvars
The system SHALL use a `contextvars.ContextVar` to hold a mutable dict scoped to a single command execution. The dict SHALL be set before hook setup and cleared after post_save hooks complete.

#### Scenario: Context is set during execution
- **WHEN** `execute_command()` runs
- **THEN** a mutable dict SHALL be stored in the contextvar for the duration of the execution

#### Scenario: Context is cleared after execution
- **WHEN** `execute_command()` completes (success or failure)
- **THEN** the contextvar SHALL be set to `None`

#### Scenario: Context is isolated per task
- **WHEN** two command executions run concurrently (e.g., different Celery workers)
- **THEN** each SHALL have its own independent context dict

### Requirement: is_admin_runner detection function
The system SHALL provide an `is_admin_runner()` function that returns `True` when called during a command execution triggered through the admin runner, and `False` otherwise.

#### Scenario: Called inside admin runner execution
- **WHEN** `is_admin_runner()` is called from within a command's `handle()` method during an admin-triggered execution
- **THEN** it SHALL return `True`

#### Scenario: Called outside admin runner
- **WHEN** `is_admin_runner()` is called from a management command run via `manage.py` directly, or from any non-admin-runner context
- **THEN** it SHALL return `False`

#### Scenario: Called from a hook
- **WHEN** `is_admin_runner()` is called from within a hook's `setup()`, `pre_save()`, or `post_save()` method
- **THEN** it SHALL return `True`

### Requirement: set_result_html function
The system SHALL provide a `set_result_html(html)` function that stores HTML content in the execution context. When called outside an admin runner execution, it SHALL be a no-op.

#### Scenario: Set result HTML during command execution
- **WHEN** `set_result_html("<div>Result</div>")` is called from a command's `handle()` method
- **THEN** the HTML string SHALL be stored in the execution context and later persisted to `CommandExecution.result_html`

#### Scenario: Last writer wins
- **WHEN** `set_result_html()` is called multiple times during a single execution (by the command, then by a hook)
- **THEN** the last call's value SHALL be the one persisted

#### Scenario: No-op outside admin runner
- **WHEN** `set_result_html()` is called outside of an admin runner execution
- **THEN** it SHALL not raise an error and SHALL not store any value
