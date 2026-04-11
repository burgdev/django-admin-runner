## MODIFIED Requirements

### Requirement: CommandHook protocol
The system SHALL provide a `CommandHook` protocol with `setup()`, `pre_save()`, and `post_save()` methods. Each method SHALL receive `command_name`, `kwargs`, `execution`, and a shared `HookContext` object.

#### Scenario: Hook receives execution context
- **WHEN** a hook's `setup()`, `pre_save()`, or `post_save()` method is called
- **THEN** it SHALL receive the command name, kwargs dict, `CommandExecution` instance, and a `HookContext` object as arguments

### Requirement: HookContext state bag
The system SHALL provide a `HookContext` class that acts as a mutable dict-like state bag scoped to a single command execution.

#### Scenario: Hook writes and reads state
- **WHEN** a hook writes a value to `HookContext` in `setup()` (e.g., `ctx["upload_dir"] = path`)
- **THEN** the same hook or another hook SHALL be able to read that value in `pre_save()` or `post_save()`

#### Scenario: Context is fresh per execution
- **WHEN** a new command execution starts
- **THEN** a new `HookContext` instance SHALL be created with no state from previous executions

### Requirement: Hooks called around command execution
`execute_command()` SHALL call hooks at three points: `setup()` before `call_command()`, `pre_save()` after command execution but before the DB save, and `post_save()` after the DB save completes.

#### Scenario: Hooks execute in order
- **WHEN** hooks A, B, C are registered
- **THEN** setup SHALL be called in order A, B, C; pre_save SHALL be called in order A, B, C; post_save SHALL be called in order C, B, A

#### Scenario: Pre-save hooks can modify execution state
- **WHEN** a pre_save hook sets `execution.result_html = "<div>Result</div>"`
- **THEN** the persisted `CommandExecution` record SHALL contain that value

#### Scenario: Pre-save hooks can read stdout/stderr
- **WHEN** a pre_save hook accesses `execution.stdout`
- **THEN** it SHALL see the command's full stdout output

#### Scenario: All hooks run even on command failure
- **WHEN** `call_command()` raises an exception
- **THEN** pre_save and post_save hooks SHALL still be called

### Requirement: Built-in TempFileHook
The system SHALL provide a `TempFileHook` that creates a unique temp directory under `ADMIN_RUNNER_UPLOAD_PATH` in `setup()` and removes it in `post_save()`.

#### Scenario: TempFileHook creates and cleans up directory
- **WHEN** `TempFileHook.setup()` is called with `ADMIN_RUNNER_UPLOAD_PATH` configured
- **THEN** a unique subdirectory SHALL be created under that path and its location stored in `HookContext`

#### Scenario: TempFileHook removes directory after execution
- **WHEN** `TempFileHook.post_save()` is called
- **THEN** the temp directory and all its contents SHALL be deleted

#### Scenario: TempFileHook is inactive without upload path
- **WHEN** `ADMIN_RUNNER_UPLOAD_PATH` is not set
- **THEN** `TempFileHook` SHALL NOT be registered and SHALL NOT create or clean up any directories

### Requirement: Hook errors are non-fatal
Errors raised during any hook method SHALL be logged but SHALL NOT override the command execution status or raise exceptions.

#### Scenario: Pre-save error does not mask command success
- **WHEN** `call_command()` succeeds but a hook's `pre_save()` raises an exception
- **THEN** the command execution status SHALL remain `SUCCESS` and the error SHALL be logged

#### Scenario: Post-save error does not mask command success
- **WHEN** `call_command()` succeeds but a hook's `post_save()` raises an exception
- **THEN** the command execution status SHALL remain `SUCCESS` and the error SHALL be logged

## REMOVED Requirements

### Requirement: Teardown errors are non-fatal
**Reason**: Replaced by the more general "Hook errors are non-fatal" requirement covering all three hook points.
**Migration**: Use `post_save()` instead of `teardown()`. Error handling behavior is unchanged.
