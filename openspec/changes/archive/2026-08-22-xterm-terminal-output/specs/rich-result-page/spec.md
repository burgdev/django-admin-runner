## REMOVED Requirements

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

**Reason**: stdout/stderr are now rendered by the xterm.js terminal widget, which replays raw ANSI and does not hyperlink; static ANSI-to-HTML conversion of stdout/stderr is removed from the execution page. URLs can be copied from the terminal as plain text.
**Migration**: Use the terminal widget's copy support or the stored raw field contents. `result_html` (which supports full HTML including links) is unaffected.
