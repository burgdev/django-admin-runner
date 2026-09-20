# execution-rerun Specification

## Purpose
TBD - created by archiving change execution-rerun. Update Purpose after archive.
## Requirements
### Requirement: Rerun button on the execution change page
The CommandExecution change page SHALL show a "Rerun" object-tools button
that links to the command's run view with a `rerun=<execution.pk>` query
parameter, when the command is still registered and the user has run
permission for it. The page SHALL NOT show the default "Save" or "Save and
continue editing" submit buttons, because all fields are read-only.

#### Scenario: Rerun link for a registered command
- **WHEN** a staff user opens the change page of an execution whose
  `command_name` is registered and the user has run permission
- **THEN** a "Rerun" button links to the run view URL with
  `?rerun=<execution.pk>` appended

#### Scenario: Rerun disabled while executing
- **WHEN** the execution's status is pending or running
- **THEN** the "Rerun" button renders disabled (no link, reduced opacity,
  not-allowed cursor) with a hint that the command is still executing

#### Scenario: No Rerun button for unregistered commands
- **WHEN** the execution's command is no longer registered (or the user
  lacks run permission)
- **THEN** no "Rerun" button is rendered and the page opens normally

#### Scenario: Save buttons hidden
- **WHEN** the execution change page renders
- **THEN** the submit row contains no "Save" and no "Save and continue
  editing" button

### Requirement: Run form prepopulation from a past execution
The command run view SHALL accept a `rerun=<execution.pk>` query parameter
and, on GET, prefill the run form with that execution's stored `kwargs` as
initial data. The referenced execution SHALL be looked up through the
permission-restricted admin queryset.

#### Scenario: Prefilled form
- **WHEN** the user opens `<run-url>?rerun=<pk>` for a still-registered
  command
- **THEN** every form field whose name exists in the stored kwargs renders
  with the stored value as its initial value, without validation errors

#### Scenario: String value for a multi-select field
- **WHEN** a stored kwarg is a single string but the corresponding form
  field is a multiple-choice field
- **THEN** the string is split on commas/whitespace and the resulting list
  is used as the field's initial value

#### Scenario: Stale kwargs degrade gracefully
- **WHEN** stored kwargs contain keys that no longer exist on the form
- **THEN** those keys are ignored and the form opens with defaults for the
  affected fields

#### Scenario: Missing or inaccessible execution
- **WHEN** `rerun` references a nonexistent execution, or one outside the
  user's queryset, or the parameter is absent
- **THEN** the run form renders with no prefill and no error
