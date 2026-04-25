## ADDED Requirements

### Requirement: RegisteredCommand admin changelist is read-only with superuser delete
The system SHALL register a `ModelAdmin` for `RegisteredCommand` that disables add and change for all users. Superusers SHALL be allowed to delete `RegisteredCommand` rows (useful for manually cleaning up deactivated commands). Non-superusers SHALL NOT see delete actions.

#### Scenario: Superuser can delete rows
- **WHEN** a superuser views the `RegisteredCommand` changelist
- **THEN** delete actions and the "Delete selected" bulk action are available

#### Scenario: Non-superuser cannot modify rows
- **WHEN** a non-superuser staff user views the `RegisteredCommand` changelist
- **THEN** no "Add", "Edit", or "Delete" buttons or actions are shown

### Requirement: Changelist shows command metadata columns
The `RegisteredCommand` changelist SHALL display the following columns: `name`, `display_name`, `group`, `description` (truncated), `active`, `updated_at`, and a custom "Run" action column. The description SHALL use CSS `overflow:hidden; text-overflow:ellipsis; white-space:nowrap` on a block-level element without a fixed `max-width` in pixels, so that truncation only occurs when the text overflows the natural column width.

#### Scenario: Active command displayed in changelist
- **WHEN** the changelist is viewed and a `RegisteredCommand` with `name="cleanup_books"`, `group="Books"`, `active=True` exists
- **THEN** a row is shown with those values and a "Run" link pointing to the command run view

#### Scenario: Short description fits without truncation
- **WHEN** a `RegisteredCommand` has a description that fits within the column width
- **THEN** the full description is displayed without an ellipsis

#### Scenario: Long description is truncated with ellipsis
- **WHEN** a `RegisteredCommand` has a description longer than the available column width
- **THEN** the description is truncated with an ellipsis (`…`) at the point where it overflows

#### Scenario: No hard-coded pixel width on description
- **WHEN** the description `<span>` element is rendered
- **THEN** it SHALL NOT have a `max-width` set to a fixed pixel value (e.g., `300px`)

### Requirement: Run action links to the command run view
Each row in the changelist SHALL display a "Run" link (only for active commands) that navigates to the existing `django_admin_runner_command_run` URL for that command.

#### Scenario: Active command shows Run link
- **WHEN** a `RegisteredCommand` row with `active=True` is displayed
- **THEN** a "Run" link is shown that navigates to `{admin_prefix}/django_admin_runner/commandexecution/commands/{name}/run/`

#### Scenario: Inactive command shows no Run link
- **WHEN** a `RegisteredCommand` row with `active=False` is displayed
- **THEN** no "Run" link is shown; the action column displays a dash or "Inactive" indicator

### Requirement: Changelist supports search and filter
The changelist SHALL provide:
- `search_fields` on `name` and `display_name`
- `list_filter` on `active` and `group`

#### Scenario: Filter by active status
- **WHEN** a user clicks the "Active" filter and selects "Yes"
- **THEN** only `RegisteredCommand` rows with `active=True` are shown

### Requirement: Default filter shows active commands only
By default, the changelist SHALL apply a filter showing only `active=True` commands. Users can clear the filter to see all commands including inactive ones.

#### Scenario: Initial changelist load
- **WHEN** a user navigates to the `RegisteredCommand` changelist without any query parameters
- **THEN** only rows with `active=True` are displayed

### Requirement: History link filters CommandExecution changelist
Each active command row SHALL include a "History" link that navigates to the `CommandExecution` changelist filtered by `command_name`.

#### Scenario: History link on active command
- **WHEN** a user clicks the "History" link on the `cleanup_books` row
- **THEN** they are taken to the `CommandExecution` changelist with `?command_name=cleanup_books`

### Requirement: Broken admin/index.html template is removed
The file `src/django_admin_runner/templates/admin/index.html` SHALL be deleted. It was a template override that never loaded due to Django's `APP_DIRS` resolution order.

#### Scenario: Template file no longer exists
- **WHEN** the package is installed
- **THEN** no `admin/index.html` template override exists in the package's template directory

### Requirement: List templates truncate long descriptions
Both the base and Unfold `list.html` templates SHALL apply CSS truncation (`overflow:hidden; text-overflow:ellipsis; white-space:nowrap`) to command description text, so that very long help text does not break the layout.

#### Scenario: Long description in Unfold list template
- **WHEN** a command's help text exceeds the available width in the Unfold list view
- **THEN** the description is truncated with an ellipsis

#### Scenario: Long description in base list template
- **WHEN** a command's help text exceeds the available width in the base list view
- **THEN** the description is truncated with an ellipsis
