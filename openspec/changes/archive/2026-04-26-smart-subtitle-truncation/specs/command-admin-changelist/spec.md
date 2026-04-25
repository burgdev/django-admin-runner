## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: List templates truncate long descriptions
Both the base and Unfold `list.html` templates SHALL apply CSS truncation (`overflow:hidden; text-overflow:ellipsis; white-space:nowrap`) to command description text, so that very long help text does not break the layout.

#### Scenario: Long description in Unfold list template
- **WHEN** a command's help text exceeds the available width in the Unfold list view
- **THEN** the description is truncated with an ellipsis

#### Scenario: Long description in base list template
- **WHEN** a command's help text exceeds the available width in the base list view
- **THEN** the description is truncated with an ellipsis
