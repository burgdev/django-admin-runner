## Why

File uploads in `FileOrPathWidget` are broken — the file dialog never opens in the admin (confirmed with Unfold; likely also broken in classic admin). The root cause is that the widget uses a bare `forms.FileInput()` without admin styling, and the Unfold `_apply_unfold_widget()` only replaces the text sub-widget, leaving the file input invisible/non-functional.

Additionally, there is no temp file lifecycle management. Uploaded files are saved to `tempfile.mkdtemp()` in the OS temp dir, which async workers (Celery, Django Tasks) cannot access in typical containerized setups. Files are never cleaned up after command execution completes.

## What Changes

- Fix `FileOrPathWidget` to render a properly styled file upload input for both classic Django admin and Unfold admin
- Add a second template (`file_or_path_unfold.html`) with Unfold-styled upload UI (icon trigger + hidden file input, no clear/download buttons)
- Degrade to text-only input when `ADMIN_RUNNER_UPLOAD_PATH` is not configured
- Add pluggable command hooks system: `setup()` / `teardown()` protocol with a shared `HookContext` state bag
- Add built-in `TempFileHook` that manages upload directory creation and cleanup
- Save uploaded files to `ADMIN_RUNNER_UPLOAD_PATH` (configurable shared volume) instead of OS temp dir

## Capabilities

### New Capabilities

- `file-upload-widget`: Properly styled file upload widget for `FileOrPathField` that works in both classic and Unfold admin, with graceful degradation when upload path is not configured
- `command-hooks`: Pluggable setup/teardown hook system for command execution, with built-in temp file management

### Modified Capabilities

## Impact

- **Forms**: `FileOrPathWidget`, `FileOrPathField`, `_apply_unfold_widget()` in `forms.py`
- **Templates**: `file_or_path.html` (rewrite), new `file_or_path_unfold.html`
- **Task execution**: `execute_command()` in `tasks.py` — hooks called around `call_command()`
- **New module**: `hooks.py` — `CommandHook` protocol, `HookContext`, `TempFileHook`, hook loading
- **Settings**: Two new Django settings (`ADMIN_RUNNER_UPLOAD_PATH`, `ADMIN_RUNNER_HOOKS`)
- **Runners**: No changes needed — all runners funnel through `execute_command()` so hooks work automatically for sync, Celery, and Django Tasks
