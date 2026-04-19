## ADDED Requirements

### Requirement: API Reference nav section with auto-generated docs
The documentation SHALL include an "API Reference" nav section in mkdocs.yml containing auto-generated API documentation pages using mkdocstrings `:::` directives. Each page SHALL render documentation from source code docstrings.

#### Scenario: API reference pages render correctly
- **WHEN** the docs are built with mkdocs
- **THEN** each API reference page renders the docstrings, signatures, and type annotations from the corresponding source module

#### Scenario: API reference index page lists all public APIs
- **WHEN** a user navigates to the API Reference section
- **THEN** an index page lists all public APIs grouped by module with links to their detail pages

### Requirement: API pages organized by module
The API reference SHALL be organized into pages by logical module group:
- `register-command.md` for `register_command`
- `context.md` for `is_admin_runner` and `set_result_html`
- `forms.md` for `FileOrPathField`, `FileOrPathWidget`, `FileField`, `ImageField`, and `form_from_command`
- `hooks.md` for `CommandHook`, `HookContext`, and `TempFileHook`
- `runners.md` for `BaseCommandRunner`, `RunResult`, `SyncCommandRunner`, `DjangoTaskRunner`, `CeleryCommandRunner`, and `get_runner`
- `models.md` for `CommandExecution` and `RegisteredCommand`
- `admin.md` for `CommandRunnerModelAdminMixin`

#### Scenario: Each API page documents its listed symbols
- **WHEN** a user opens an API reference page
- **THEN** the page contains mkdocstrings-rendered documentation for each listed symbol with signature, parameters, return types, and docstring content

### Requirement: mkdocs.yml nav updated with API Reference section
The mkdocs.yml nav SHALL include an "API Reference" section after Guides, containing all API reference pages.

#### Scenario: API Reference appears in navigation
- **WHEN** a user views the site navigation
- **THEN** an "API Reference" top-level section is visible after "Guides" with links to each API page
