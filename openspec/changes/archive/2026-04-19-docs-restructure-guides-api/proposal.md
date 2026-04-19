## Why

The documentation currently has a "Reference" section that contains guide-style content (how-tos for the decorator, runners, execution context, etc.) alongside the `@register_command` reference. There is no auto-generated API reference from source code — all API docs are hand-written markdown. Users looking for precise type signatures, parameters, and return values must read the source. The hooks system is buried inside the "Execution Context" guide rather than having its own dedicated page.

## What Changes

- Rename the "Reference" nav section to "Guides" — its content is guide-style, not API reference material.
- Add a `docs/guides.md` index page for the Guides section (with `navigation.indexes` support).
- Extract the hooks content from `execution-context.md` into a dedicated `docs/hooks.md` guide page, placed after execution context in the nav.
- Create a new "API Reference" nav section with auto-generated API documentation using mkdocstrings (already configured in `mkdocs.yml`).
- Add `docs/api-reference.md` as the API Reference index/landing page.
- Add `docs/api/register-command.md` — auto-generated docs for `register_command`.
- Add `docs/api/context.md` — auto-generated docs for `is_admin_runner`, `set_result_html`.
- Add `docs/api/forms.md` — auto-generated docs for `FileOrPathField`, `FileOrPathWidget`, `FileField`, `ImageField`, `form_from_command`.
- Add `docs/api/hooks.md` — auto-generated docs for `CommandHook`, `HookContext`, `TempFileHook`.
- Add `docs/api/runners.md` — auto-generated docs for `BaseCommandRunner`, `RunResult`, `SyncCommandRunner`, `DjangoTaskRunner`, `CeleryCommandRunner`, `get_runner`.
- Add `docs/api/models.md` — auto-generated docs for `CommandExecution`, `RegisteredCommand`.
- Add `docs/api/admin.md` — auto-generated docs for `CommandRunnerModelAdminMixin`.
- Update `mkdocs.yml` nav to reflect the new structure.

## Capabilities

### New Capabilities
- `api-reference`: Auto-generated API reference pages using mkdocstrings for all public classes, functions, and models.
- `hooks-guide`: Dedicated guide page for the hooks system extracted from execution-context.md.

### Modified Capabilities
- `execution-context`: Remove hooks content (moved to its own guide page); keep context detection, rich HTML results, and ANSI output sections.

## Impact

- `mkdocs.yml` — nav section renamed, new pages added.
- `docs/` — new markdown files created, `execution-context.md` updated to remove hooks section.
- No source code changes required — mkdocstrings reads docstrings directly.
- No breaking changes to existing documentation URLs for pages that stay in place (decorator.md, runners.md, etc.).
