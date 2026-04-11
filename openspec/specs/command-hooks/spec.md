# command-hooks Specification

## Purpose
TBD - created by archiving change fix-file-upload-hooks. Update Purpose after archive.
## Requirements
### Requirement: CommandHook protocol
The system SHALL provide a `CommandHook` protocol with `setup()` and `teardown()` methods. Each method SHALL receive `command_name`, `kwargs`, `execution`, and a shared `HookContext` object.

#### Scenario: Hook receives execution context
- **WHEN** a hook's `setup()` or `teardown()` method is called
- **THEN** it SHALL receive the command name, kwargs dict, `CommandExecution` instance, and a `HookContext` object as arguments

### Requirement: HookContext state bag
The system SHALL provide a `HookContext` class that acts as a mutable dict-like state bag scoped to a single command execution.

#### Scenario: Hook writes and reads state
- **WHEN** a hook writes a value to `HookContext` in `setup()` (e.g., `ctx["upload_dir"] = path`)
- **THEN** the same hook or another hook SHALL be able to read that value in `teardown()`

#### Scenario: Context is fresh per execution
- **WHEN** a new command execution starts
- **THEN** a new `HookContext` instance SHALL be created with no state from previous executions

### Requirement: Hooks called around command execution
`execute_command()` SHALL call `setup()` on all registered hooks before `call_command()` and `teardown()` on all hooks (in reverse order) in the `finally:` block after command execution.

#### Scenario: Hooks execute in order
- **WHEN** hooks A, B, C are registered
- **THEN** setup SHALL be called in order A, B, C and teardown SHALL be called in order C, B, A

#### Scenario: Teardown runs even on command failure
- **WHEN** `call_command()` raises an exception
- **THEN** teardown SHALL still be called for all registered hooks

### Requirement: Hook registration via Django setting
Hooks SHALL be registered via the `ADMIN_RUNNER_HOOKS` Django setting, which accepts a list of dotted import paths to hook classes.

#### Scenario: Hooks loaded from setting
- **WHEN** `ADMIN_RUNNER_HOOKS = ["myapp.hooks.NotificationHook"]` is configured
- **THEN** `NotificationHook` SHALL be imported, instantiated once (singleton), and called on every command execution

#### Scenario: Invalid hook path raises error
- **WHEN** a dotted path in `ADMIN_RUNNER_HOOKS` cannot be imported or does not implement the hook protocol
- **THEN** an appropriate error SHALL be raised at startup or first execution

### Requirement: Built-in TempFileHook
The system SHALL provide a `TempFileHook` that creates a unique temp directory under `ADMIN_RUNNER_UPLOAD_PATH` in `setup()` and removes it in `teardown()`.

#### Scenario: TempFileHook creates and cleans up directory
- **WHEN** `TempFileHook.setup()` is called with `ADMIN_RUNNER_UPLOAD_PATH` configured
- **THEN** a unique subdirectory SHALL be created under that path and its location stored in `HookContext`

#### Scenario: TempFileHook removes directory after execution
- **WHEN** `TempFileHook.teardown()` is called
- **THEN** the temp directory and all its contents SHALL be deleted

#### Scenario: TempFileHook is inactive without upload path
- **WHEN** `ADMIN_RUNNER_UPLOAD_PATH` is not set
- **THEN** `TempFileHook` SHALL NOT be registered and SHALL NOT create or clean up any directories

### Requirement: Teardown errors are non-fatal
Errors raised during hook teardown SHALL be logged but SHALL NOT override the command execution status or raise exceptions.

#### Scenario: Teardown error does not mask command success
- **WHEN** `call_command()` succeeds but a hook's `teardown()` raises an exception
- **THEN** the command execution status SHALL remain `SUCCESS` and the teardown error SHALL be logged
