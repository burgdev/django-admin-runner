# output-delta-endpoint Specification

## Purpose
TBD - update Purpose after archive.

## Requirements

### Requirement: Output delta endpoint
The system SHALL provide a staff-only JSON endpoint per `CommandExecution` that returns output written after a given cursor: `GET .../output/?field=stdout|stderr&cursor=<seq>:<offset>` responding with the new `chunk`, the advanced `cursor`, and whether the command is `finished`. An empty cursor SHALL mean replay from the start of the retained output.

#### Scenario: Delta request
- **WHEN** a staff user with view permission polls with a valid `?field=stdout&cursor=3:120` and new output exists
- **THEN** the response contains only the new characters, the advanced cursor, and `finished: false` for a running command

#### Scenario: Empty delta
- **WHEN** the client polls with a cursor matching the end of stored output and no new output exists
- **THEN** the response contains an empty chunk and the unchanged cursor

#### Scenario: Reset after pruning
- **WHEN** the client cursor refers to a part that has been pruned
- **THEN** the response contains `reset: true` with the full retained output and its cursor so the client can reset and replay

#### Scenario: Invalid cursor rejected
- **WHEN** the cursor is malformed or does not match the `<seq>:<offset>` format
- **THEN** the endpoint responds with 400

#### Scenario: Permission enforcement
- **WHEN** a user without staff/permission access requests the endpoint
- **THEN** the request is rejected with 403/404 equal to the admin change-form rules

#### Scenario: Invalid field rejected
- **WHEN** the `field` parameter is anything other than `stdout` or `stderr`
- **THEN** the endpoint responds with 400

#### Scenario: Finished flag
- **WHEN** the command has finished
- **THEN** the response reports `finished: true` so the client can stop polling
