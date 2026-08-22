## ADDED Requirements

### Requirement: Output delta endpoint
The system SHALL provide a staff-only JSON endpoint per `CommandExecution` that returns output written since a given character offset: `GET .../output/?field=stdout|stderr&offset=N` responding with the field status, the new chunk, the new offset, and whether the command is finished.

#### Scenario: Delta request
- **WHEN** a staff user with view permission requests `?field=stdout&offset=100` and 250 characters are stored
- **THEN** the response contains the characters 100..250, `offset: 250`, the execution status, and `finished: false` for a running command

#### Scenario: No new output
- **WHEN** the stored length equals the requested offset
- **THEN** the response contains an empty chunk and the unchanged offset

#### Scenario: Offset clamping and validation
- **WHEN** the offset is negative, non-numeric, or larger than the stored length
- **THEN** the offset is clamped to `[0, len]` (or rejected with 400 for non-numeric values)

#### Scenario: Permission enforcement
- **WHEN** a user without staff/permission access requests the endpoint
- **THEN** the request is rejected with 403/404 equal to the admin change-form rules

#### Scenario: Invalid field rejected
- **WHEN** the `field` parameter is anything other than `stdout` or `stderr`
- **THEN** the endpoint responds with 400
