## Context

`FileOrPathField` / `FileOrPathWidget` provide a dual file-upload-or-path input for management commands. The current implementation uses `forms.MultiWidget([forms.FileInput(), forms.TextInput()])` — the `FileInput` is a bare HTML widget with no admin styling. In Unfold admin, `_apply_unfold_widget()` only replaces the text sub-widget (index 1), leaving the file input invisible and non-functional.

The `FileOrPathField.compress()` method saves uploaded files to `tempfile.mkdtemp()` (OS temp dir). This breaks in containerized or multi-process deployments where the web process and task worker (Celery, Django Tasks) don't share `/tmp/`. There is also no cleanup mechanism after command execution.

All three runners (sync, Celery, Django Tasks) funnel through `execute_command()` in `tasks.py`, providing a single point for lifecycle hooks.

## Goals / Non-Goals

**Goals:**

- Fix file upload widget so the file dialog opens and uploads work in both classic and Unfold admin
- Add configurable shared upload directory (`ADMIN_RUNNER_UPLOAD_PATH`)
- Add pluggable setup/teardown hooks around `execute_command()`
- Clean up temp files after command execution
- Degrade gracefully when upload path is not configured (text-only path input)

**Non-Goals:**

- Auto-detection of `argparse.FileType` in `_action_to_field()` (future enhancement)
- File validation (extension/size limits) — out of scope
- Multiple file upload support
- Model-backed file storage (the widget is for temp uploads only)

## Decisions

### 1. Widget: custom templates per admin theme

**Decision**: Two separate templates — `file_or_path.html` (classic) and `file_or_path_unfold.html` (Unfold).

**Rationale**: Unfold's file widget (`UnfoldAdminFileFieldWidget`) is designed for model-backed file fields — it expects `value.url`, `is_initial`, clear checkboxes, download links. None of that applies to a temp file upload. A custom template gives us full control over the upload trigger UI without fighting Unfold's assumptions.

**Alternative considered**: Subclass `UnfoldAdminFileFieldWidget` and override template. Rejected because the data model (no `UploadedFile`, no URL) doesn't match.

### 2. Upload degradation via template context, not widget rebuild

**Decision**: Always build both sub-widgets in `FileOrPathWidget.__init__()`. Pass an `upload_enabled` flag in `get_context()`. Templates conditionally render the file input.

**Rationale**: The widget is instantiated at command import time via `widget=FileOrPathField()`, before Django settings are configured. Rebuilding sub-widgets based on settings would fail. Checking at render time is safe.

### 3. Hooks: protocol class with HookContext state bag

**Decision**: Hooks are singleton classes implementing `setup()` / `teardown()` methods. A `HookContext` (dict-like) object carries state between setup and teardown for a single execution.

**Rationale**: Singletons are cheap and stateless. The context bag lets hooks share data (e.g., `TempFileHook` writes `upload_dir`, reads it in teardown) without coupling hooks to each other. Fresh context per execution prevents state leakage.

**Alternative considered**: Per-execution hook instances with attributes. Rejected — more complex lifecycle, harder to manage.

### 4. Hook execution point: inside `execute_command()`

**Decision**: Hooks are called inside `execute_command()` in `tasks.py`, wrapping `call_command()`.

**Rationale**: Every runner (sync, Celery, Django Tasks) calls `execute_command()`. This is the natural choke point. Setup runs before `call_command()`, teardown in `finally:` block (reversed order). No runner-specific code needed.

### 5. Temp files saved to `ADMIN_RUNNER_UPLOAD_PATH`

**Decision**: `FileOrPathField.compress()` saves files to a subdirectory under `ADMIN_RUNNER_UPLOAD_PATH` instead of OS temp dir. `TempFileHook` handles cleanup.

**Rationale**: A configurable shared volume is the standard solution for web/worker file sharing in containerized deployments. The path is admin-configurable for different deployment topologies.

### 6. Hook registration via Django setting

**Decision**: `ADMIN_RUNNER_HOOKS` — list of dotted import paths to hook classes. `TempFileHook` is auto-registered when `ADMIN_RUNNER_UPLOAD_PATH` is set.

**Rationale**: Follows Django conventions (similar to `MIDDLEWARE`, `AUTHENTICATION_BACKENDS`). Auto-registration of `TempFileHook` keeps the common case simple — users only touch settings for custom hooks.

## Risks / Trade-offs

- **[Unfold template changes]** Unfold updates could break custom templates → Mitigation: keep templates minimal, only use Unfold's Tailwind classes (stable) not internal template structure
- **[Hook errors in teardown]** A failing teardown hook could mask the original command error → Mitigation: teardown errors are logged but not raised; command status is set before teardown runs
- **[Temp file cleanup failure]** If teardown doesn't run (hard crash, OOM kill), files linger → Mitigation: document that admins should run a periodic cleanup job for orphaned files in `ADMIN_RUNNER_UPLOAD_PATH`
- **[Multi-part form overhead]** Forms always have `enctype="multipart/form-data"` even when no file fields present → Acceptable: no functional impact, minimal overhead
