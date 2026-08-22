# launch-terminal-size Specification

## Purpose
TBD - update Purpose after archive.

## Requirements

### Requirement: Fixed terminal size setting
The system SHALL use globally configured terminal dimensions (`ADMIN_RUNNER_TERM_COLS`, default 120, and `ADMIN_RUNNER_TERM_ROWS`, default 40) for every command execution: `execute_command` SHALL export them as `COLUMNS`/`LINES` for the duration of the command so output layout (e.g. progress bar width) is deterministic, and the terminal widget SHALL initialize at the configured size. Dimensions SHALL NOT depend on the caller or browser.

#### Scenario: Configured dimensions reach the command
- **WHEN** `ADMIN_RUNNER_TERM_COLS = 80` is configured and a command is started
- **THEN** `COLUMNS=80` is set in the worker environment during execution and output is laid out to 80 columns

#### Scenario: Defaults
- **WHEN** no terminal size settings are configured
- **THEN** `COLUMNS=120` and `LINES=40` are used

#### Scenario: Widget uses configured size
- **WHEN** the execution page is opened
- **THEN** the terminal widget initializes at the configured dimensions for faithful replay

#### Scenario: Environment restored after run
- **WHEN** the command has finished
- **THEN** `COLUMNS`/`LINES` are restored to their prior values in the worker process
