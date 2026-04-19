## MODIFIED Requirements

### Requirement: Per-execution context via contextvars
The system SHALL use a `contextvars.ContextVar` to hold a mutable dict scoped to a single command execution. The dict SHALL be set before hook setup and cleared after post_save hooks complete.

The documentation for execution context (`docs/execution-context.md`) SHALL cover only context detection (`is_admin_runner`), rich HTML results (`set_result_html`), and ANSI output. Hooks content SHALL be moved to a dedicated `docs/hooks.md` guide page with a cross-reference link.

#### Scenario: Context is set during execution
- **WHEN** `execute_command()` runs
- **THEN** a mutable dict SHALL be stored in the contextvar for the duration of the execution

#### Scenario: Context is cleared after execution
- **WHEN** `execute_command()` completes (success or failure)
- **THEN** the contextvar SHALL be set to `None`

#### Scenario: Context is isolated per task
- **WHEN** two command executions run concurrently (e.g., different Celery workers)
- **THEN** each SHALL have its own independent context dict

#### Scenario: Execution context guide links to hooks guide
- **WHEN** a user reads the execution-context.md guide page
- **THEN** the page links to the dedicated hooks guide for hook-related documentation
