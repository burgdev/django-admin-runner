## ADDED Requirements

### Requirement: Custom Schedule admin with registered command choices
The example project SHALL replace django-q2's default `ScheduleAdmin` with a custom admin that changes the `func` field from a plain text input to a dropdown (`Select` widget) listing all registered management commands from the admin-runner registry (`_registry`).

#### Scenario: Schedule form shows registered commands
- **WHEN** a user opens the Schedule add/change form in the admin
- **THEN** the `func` field SHALL display a dropdown containing all registered management commands, with each choice labeled by the command's display name and valued as `django_admin_runner.tasks.execute_command`

#### Scenario: Schedule form preserves free-text func entry
- **WHEN** a user needs to schedule a function that is not a registered management command
- **THEN** the `func` dropdown SHALL include a blank/empty option allowing manual entry of any dotted function path

#### Scenario: Creating a scheduled command
- **WHEN** a user selects a command from the dropdown and fills in `args` (positional args) with the command name, sets `kwargs` as JSON for command arguments, and chooses a schedule type
- **THEN** the Schedule SHALL be created and django-q2 SHALL execute the command on the specified schedule
