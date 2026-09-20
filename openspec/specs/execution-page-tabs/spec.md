# execution-page-tabs Specification

## Purpose
TBD - created by archiving change execution-page-tabs. Update Purpose after archive.
## Requirements
### Requirement: Tabbed execution change page
The `CommandExecution` change page SHALL organize its content into two tabs: **Output** (the default/active tab) containing the status, the stdout and stderr terminals, and the result HTML; and **Input** containing command name, kwargs, triggered_by, backend, task_id, and timestamps.

#### Scenario: Output tab is default
- **WHEN** the execution change page is opened
- **THEN** the Output tab is active and shows status plus the terminals without any interaction

#### Scenario: Input tab shows parameters
- **WHEN** the Input tab is selected
- **THEN** command name, kwargs, and the remaining metadata are visible

### Requirement: Tabs work in Unfold and the base admin theme
Under Unfold the tabs SHALL be rendered by Unfold's native fieldset tab mechanism (`classes=["tab"]`). Under the base Django admin theme the package SHALL provide a fallback (small JS/CSS) that renders an equivalent tab bar; when scripting is unavailable the fieldsets SHALL degrade to stacked sections.

#### Scenario: Unfold tabs
- **WHEN** the page renders with Unfold installed
- **THEN** the two fieldsets appear as Unfold tabs with Output active

#### Scenario: Base theme fallback
- **WHEN** the page renders with the base admin theme
- **THEN** a tab bar toggles between Output and Input, and without JS all sections remain visible stacked

### Requirement: Full-width terminals
The terminal placeholders SHALL occupy 100% of the available content width on the execution change page in both themes.

#### Scenario: Terminal spans the content area
- **WHEN** the Output tab renders
- **THEN** the stdout and stderr terminals span the full width of the form content area
