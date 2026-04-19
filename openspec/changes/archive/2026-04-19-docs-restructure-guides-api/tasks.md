## 1. Navigation Restructure

- [x] 1.1 Rename "Reference" to "Guides" in mkdocs.yml nav section
- [x] 1.2 Add `docs/guides.md` index page linking to all guide pages
- [x] 1.3 Update `docs/index.md` quick navigation links to reflect section rename

## 2. Hooks Guide

- [x] 2.1 Extract hooks content from `docs/execution-context.md` into new `docs/hooks.md`
- [x] 2.2 Add cross-reference link in `docs/execution-context.md` pointing to the hooks guide
- [x] 2.3 Add `hooks.md` to the Guides nav section after `execution-context.md` in mkdocs.yml

## 3. API Reference Pages

- [x] 3.1 Create `docs/api-reference.md` index page listing all public APIs grouped by module
- [x] 3.2 Create `docs/api/register-command.md` with mkdocstrings directive for `register_command`
- [x] 3.3 Create `docs/api/context.md` with mkdocstrings directives for `is_admin_runner` and `set_result_html`
- [x] 3.4 Create `docs/api/forms.md` with mkdocstrings directives for `FileOrPathField`, `FileOrPathWidget`, `FileField`, `ImageField`, and `form_from_command`
- [x] 3.5 Create `docs/api/hooks.md` with mkdocstrings directives for `CommandHook`, `HookContext`, and `TempFileHook`
- [x] 3.6 Create `docs/api/runners.md` with mkdocstrings directives for `BaseCommandRunner`, `RunResult`, runner classes, and `get_runner`
- [x] 3.7 Create `docs/api/models.md` with mkdocstrings directives for `CommandExecution` and `RegisteredCommand`
- [x] 3.8 Create `docs/api/admin.md` with mkdocstrings directive for `CommandRunnerModelAdminMixin`

## 4. Navigation & Build Verification

- [x] 4.1 Add "API Reference" section to mkdocs.yml nav with all API pages
- [x] 4.2 Build docs with `just docs` and verify all pages render correctly
