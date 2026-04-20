# rich-result-page Specification

## Purpose
TBD - update Purpose after archive.

## Requirements

### Requirement: result_html field on CommandExecution
`CommandExecution` SHALL have a `result_html` TextField (blank by default) that stores rich HTML output produced by the command or hooks.

#### Scenario: Default value is empty
- **WHEN** a new `CommandExecution` is created
- **THEN** `result_html` SHALL be an empty string

#### Scenario: Result HTML persisted after execution
- **WHEN** a command calls `set_result_html("<div>Done</div>")` during execution
- **THEN** the `CommandExecution.result_html` field SHALL contain `"<div>Done</div>"` after the execution completes

### Requirement: URL auto-linking in ANSI output
The ANSI-to-HTML renderer SHALL convert URLs (matching `https?://\S+`) in stdout and stderr to clickable `<a>` tags with `target="_blank"`.

#### Scenario: URL in stdout becomes clickable
- **WHEN** stdout contains `File saved to https://example.com/export.csv`
- **THEN** the rendered HTML SHALL contain `<a href="https://example.com/export.csv" target="_blank">https://example.com/export.csv</a>`

#### Scenario: URL without protocol is not linked
- **WHEN** stdout contains `example.com/file.csv` without `http://` or `https://`
- **THEN** it SHALL NOT be converted to a link

#### Scenario: URL alongside ANSI color codes
- **WHEN** stdout contains ANSI-colored text with an embedded URL
- **THEN** the URL SHALL be converted to a link and the surrounding ANSI formatting SHALL be preserved

#### Scenario: Multiple URLs in output
- **WHEN** stdout contains multiple URLs on different lines
- **THEN** each URL SHALL be independently converted to a clickable link

### Requirement: Standalone result view
The admin SHALL provide a standalone result view at `/admin/django_admin_runner/commandexecution/<pk>/result/` that renders the execution result as a full page.

#### Scenario: Result HTML is set
- **WHEN** `CommandExecution.result_html` is non-empty
- **THEN** the result view SHALL render `result_html` as the primary content

#### Scenario: Result HTML is empty
- **WHEN** `CommandExecution.result_html` is empty
- **THEN** the result view SHALL render stdout and stderr with ANSI formatting

#### Scenario: Permission check
- **WHEN** a user without permission to view the execution accesses the result URL
- **THEN** they SHALL receive a 403 Forbidden response

### Requirement: Result button in change list
The `CommandExecution` change list SHALL display a button linking to the result view. The button SHALL open in a new tab.

#### Scenario: Button label with result HTML
- **WHEN** an execution has non-empty `result_html`
- **THEN** the change list SHALL show a `[RESULT]` button linking to the result view

#### Scenario: Button label without result HTML
- **WHEN** an execution has empty `result_html`
- **THEN** the change list SHALL show an `[OUTPUT]` button linking to the result view

#### Scenario: Button opens in new tab
- **WHEN** the result button is clicked
- **THEN** the result view SHALL open in a new browser tab (`target="_blank"`)

### Requirement: Result HTML preview in detail view
The `CommandExecution` detail/change view SHALL show a scrollable preview of `result_html` when it is set, with a "Full View" link to the standalone result page.

#### Scenario: Preview rendered for result HTML
- **WHEN** an execution has non-empty `result_html`
- **THEN** the detail view SHALL render the HTML in a container with a maximum height and `overflow: auto`

#### Scenario: Full View link
- **WHEN** an execution has non-empty `result_html`
- **THEN** the detail view SHALL display a "Full View" link that opens the standalone result page

#### Scenario: No preview when result HTML is empty
- **WHEN** an execution has empty `result_html`
- **THEN** the detail view SHALL NOT show the result HTML preview section
