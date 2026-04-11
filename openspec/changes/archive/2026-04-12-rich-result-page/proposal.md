## Why

Command execution results are limited to stdout/stderr text rendered as ANSI HTML. Commands that produce files (exports, reports) have no way to present download links or rich output in the admin. Hooks have no opportunity to shape what gets persisted — they can only clean up after the save has already happened. URLs in output are not clickable.

## What Changes

- Add `result_html` TextField to `CommandExecution` model — commands (and hooks) can set rich HTML as the execution result
- Add `contextvars`-based execution context: `is_admin_runner()` lets commands detect admin runner mode, `set_result_html()` sets the result HTML (last-writer-wins, no-op outside admin runner)
- Add URL auto-linking in the ANSI-to-HTML renderer — URLs in stdout/stderr become clickable `<a>` tags
- **BREAKING**: Restructure hook protocol from `setup`/`teardown` to three hook points: `setup`, `pre_save`, `post_save`
  - `pre_save` runs after command execution but before the DB save — hooks can read/modify stdout, stderr, result_html
  - `post_save` runs after the record is persisted — cleanup, notifications, uploads
- Add standalone result view (`/admin/.../commandexecution/<pk>/result/`) that renders `result_html` if set, or stdout/stderr otherwise
- Add `[RESULT]` / `[OUTPUT]` button in the change list, opening the result view in a new tab
- Show `result_html` preview (max-height, scrollable) in the detail/change view with a "Full View" link
- Update example commands: `export_report` writes file to media and generates HTML with download link; `import_books` generates an HTML summary table of imported books

## Capabilities

### New Capabilities

- `rich-result-page`: `result_html` field on CommandExecution, contextvars API (`is_admin_runner`, `set_result_html`), admin result view with standalone page and list/detail integration, URL auto-linking in ANSI renderer
- `execution-context`: `contextvars`-based per-execution context bag — provides `is_admin_runner()` and `set_result_html()` for commands and hooks

### Modified Capabilities

- `command-hooks`: Replace two hook points (`setup`/`teardown`) with three (`setup`/`pre_save`/`post_save`). `pre_save` enables hooks to modify execution state before persistence. `post_save` replaces `teardown` with clearer semantics (record is already durable).

## Impact

- **Models**: `CommandExecution` gains `result_html` TextField — requires a migration
- **Hooks**: **BREAKING** — `CommandHook` subclasses must rename `teardown` to `post_save` and optionally add `pre_save`. `TempFileHook` updated accordingly.
- **Tasks**: `execute_command()` restructured — saves after hooks, collects `result_html` from context
- **Admin**: New URL (`result/`), new column in change list, updated detail view fieldsets
- **Templates**: New result page template, updated change list template
- **ANSI renderer**: URL auto-linking post-processor in `_ansi.py`
- **Public API**: New `is_admin_runner()` and `set_result_html()` functions (importable from `django_admin_runner`)
- **Examples**: `export_report` and `import_books` updated to generate result HTML
