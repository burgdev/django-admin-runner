# terminal-output-view Specification

## Purpose
TBD - update Purpose after archive.

## Requirements

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
While the command is running, the widget SHALL poll a cursor-based endpoint (~250 ms poll interval) and append only newly written characters to the terminal, and stop polling once the command is finished.

#### Scenario: Only new characters are transferred
- **WHEN** the widget polls with a valid cursor and new output has been written
- **THEN** the response contains exactly the new characters and the advanced cursor

#### Scenario: Polling stops on completion
- **WHEN** the endpoint reports the command as finished
- **THEN** the widget performs one final fetch of the remaining output and stops polling

#### Scenario: Auto-scroll behavior
- **WHEN** new output arrives and the user has not scrolled away from the bottom
- **THEN** the widget scrolls to the bottom; if the user scrolled up, the view position is preserved

### Requirement: Raw stream storage with retention cap
Stored output SHALL contain only raw command output, held as append-only `CommandOutputPart` rows (each ≤512 KB). Total retained output SHALL be capped to `ADMIN_RUNNER_MAX_OUTPUT` (default 500 MB), enforced by pruning the oldest **sealed** parts; the active part SHALL never be pruned and no stored text SHALL be rewritten. No truncation marker SHALL be embedded in the stream; when the client cursor predates pruned parts, the endpoint SHALL report `reset: true` so the widget can display a notice and replay the retained output.

#### Scenario: Verbose output retained by pruning
- **WHEN** a command produces more output than the cap
- **THEN** the oldest sealed parts are deleted until within the cap, the active part is untouched, and no truncation text is written into the stream

#### Scenario: Clean replay after pruning
- **WHEN** the widget receives `reset: true` and replays the retained output
- **THEN** the replay begins from a clean terminal state so the widget renders without artifacts
