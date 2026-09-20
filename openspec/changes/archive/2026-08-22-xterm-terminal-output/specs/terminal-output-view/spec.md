## ADDED Requirements

### Requirement: Terminal rendering of command output
The execution page SHALL render `stdout` and `stderr` with an embedded xterm.js terminal widget that replays the stored raw stream, so ANSI control sequences (colors, cursor movement, line erase) display as they would in a real terminal.

#### Scenario: Progress bar renders as one updating line
- **WHEN** a command emits a rich progress bar (carriage-return/erase-line redraws) and the execution page is opened
- **THEN** the terminal widget shows the bar as a single updating line, not one line per redraw frame

#### Scenario: Replaying a finished execution
- **WHEN** the page for a finished execution is loaded
- **THEN** the stored stream is replayed once into the widget and no polling occurs

#### Scenario: Terminal width follows configuration
- **WHEN** the execution page is opened
- **THEN** the widget initializes at the configured terminal dimensions for faithful replay

### Requirement: Live delta updates
While the command is running, the widget SHALL poll an offset-based endpoint and append only newly written characters to the terminal, with a poll interval of ~500 ms, and stop polling once the command is finished.

#### Scenario: Only new characters are transferred
- **WHEN** the widget polls with `offset=N` and `M > N` characters are stored
- **THEN** the response contains exactly the characters `N..M` and the new offset `M`

#### Scenario: Polling stops on completion
- **WHEN** the endpoint reports the command as finished
- **THEN** the widget performs one final fetch of the remaining output and stops polling

#### Scenario: Auto-scroll behavior
- **WHEN** new output arrives and the user has not scrolled away from the bottom
- **THEN** the widget scrolls to the bottom; if the user scrolled up, the view position is preserved

### Requirement: Raw stream storage with tail cap
Stored `stdout`/`stderr` SHALL contain only raw command output (no embedded truncation marker), capped to the last `ADMIN_RUNNER_MAX_OUTPUT` characters (default 2,000,000). When output was truncated, the endpoint SHALL report it (e.g. `truncated_head`) so the widget can display a notice.

#### Scenario: Verbose output capped without marker
- **WHEN** a command produces more characters than the cap
- **THEN** the stored field contains the last `ADMIN_RUNNER_MAX_OUTPUT` raw characters and no truncation text inside the stream

#### Scenario: Clean replay of a truncated stream
- **WHEN** a capped stream starts mid-escape-sequence
- **THEN** the served replay content begins with a terminal reset so the widget renders from a clean screen state
