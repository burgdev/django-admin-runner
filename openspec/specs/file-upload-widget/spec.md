# file-upload-widget Specification

## Purpose
TBD - created by archiving change fix-file-upload-hooks. Update Purpose after archive.
## Requirements
### Requirement: File upload renders with admin styling
`FileOrPathWidget` SHALL render a properly styled file upload input in both classic Django admin and Unfold admin themes.

#### Scenario: Classic admin renders styled file input
- **WHEN** `FileOrPathWidget` is rendered in classic Django admin and `ADMIN_RUNNER_UPLOAD_PATH` is configured
- **THEN** the file input SHALL be visible with standard Django admin CSS classes and the browser file dialog SHALL open on click

#### Scenario: Unfold admin renders styled file input
- **WHEN** `FileOrPathWidget` is rendered in Unfold admin and `ADMIN_RUNNER_UPLOAD_PATH` is configured
- **THEN** the file input SHALL display an upload icon/trigger styled with Unfold's Tailwind classes and the browser file dialog SHALL open when the trigger is clicked

### Requirement: Graceful degradation without upload path
`FileOrPathWidget` SHALL degrade to a text-only path input when `ADMIN_RUNNER_UPLOAD_PATH` is not set.

#### Scenario: No upload path configured
- **WHEN** `ADMIN_RUNNER_UPLOAD_PATH` is not set or is empty
- **THEN** `FileOrPathWidget` SHALL render only the text input for server-side paths, with no file upload element visible

#### Scenario: Upload path configured
- **WHEN** `ADMIN_RUNNER_UPLOAD_PATH` is set to a valid directory path
- **THEN** `FileOrPathWidget` SHALL render both the file upload input and the text path input with an "or" separator

### Requirement: Uploaded files saved to configured directory
`FileOrPathField.compress()` SHALL save uploaded files to a subdirectory under `ADMIN_RUNNER_UPLOAD_PATH` instead of the OS temp directory.

#### Scenario: File upload saved to shared volume
- **WHEN** a file is uploaded via `FileOrPathField` and `ADMIN_RUNNER_UPLOAD_PATH` is set
- **THEN** the uploaded file SHALL be saved to a unique subdirectory under `ADMIN_RUNNER_UPLOAD_PATH` and the cleaned value SHALL be the absolute path to the saved file

#### Scenario: Path input returns typed path
- **WHEN** only a path string is typed (no file uploaded)
- **THEN** `compress()` SHALL return the typed path string unchanged

### Requirement: Unfold widget replacement applies to file sub-widget
`_apply_unfold_widget()` SHALL replace the file upload sub-widget with the Unfold-styled template when Unfold is installed.

#### Scenario: Unfold replaces file sub-widget template
- **WHEN** Unfold is installed and `FileOrPathField` is rendered
- **THEN** the widget SHALL use the Unfold-specific template (`file_or_path_unfold.html`) for rendering

#### Scenario: User-specified widgets are never replaced
- **WHEN** a user explicitly sets a widget via `widget=` kwarg or `widgets=` decorator
- **THEN** that widget SHALL NOT be overridden by Unfold auto-replacement
