## Context

The docs currently use a "Reference" nav section containing guide-style content (decorator usage, runner config, execution context, admin themes). There is no auto-generated API reference. mkdocstrings is already configured in `mkdocs.yml` with the Python handler pointing at `src/` — we just need to create the `.md` pages that use `:::` directives.

The hooks system is documented as a subsection of `execution-context.md` rather than having its own page. This makes the execution context page long and makes hooks harder to discover.

Current nav structure in `mkdocs.yml`:
```
- Reference:
    - decorator.md, runners.md, custom-runner.md, execution-context.md, admin-themes.md
```

## Goals / Non-Goals

**Goals:**
- Rename "Reference" → "Guides" in mkdocs.yml nav to accurately describe the content
- Extract hooks into a standalone `docs/hooks.md` guide page
- Add "API Reference" nav section with auto-generated docs from source via mkdocstrings
- Keep existing page URLs stable (no page moves, just section rename and new pages)

**Non-Goals:**
- Rewriting existing guide content beyond extracting hooks
- Changing mkdocstrings configuration (already set up)
- Adding new source code docstrings (existing ones are sufficient)
- Changing the site theme or plugins

## Decisions

### 1. Guides nav uses `navigation.indexes` with a `guides.md` landing page

The Guides section will have an index page (`guides.md`) that links to all guides, consistent with how the "Getting Started" section already uses `index.md`.

### 2. API Reference pages organized by module

One `.md` file per logical group:
- `api/register-command.md` — `register_command` decorator
- `api/context.md` — `is_admin_runner`, `set_result_html`
- `api/forms.md` — `FileOrPathField`, `FileOrPathWidget`, `FileField`, `ImageField`, `form_from_command`
- `api/hooks.md` — `CommandHook`, `HookContext`, `TempFileHook`
- `api/runners.md` — `BaseCommandRunner`, `RunResult`, all runner classes, `get_runner`
- `api/models.md` — `CommandExecution`, `RegisteredCommand`
- `api/admin.md` — `CommandRunnerModelAdminMixin`

Each page uses `::: module.Class` mkdocstrings directives with appropriate options.

### 3. Hooks extracted from execution-context.md

The "Hooks" section (including TempFileHook, custom hooks, hook lifecycle table) is moved to a new `docs/hooks.md`. A brief cross-reference link is left in `execution-context.md` pointing to the hooks guide.

### 4. API Reference index page lists all API objects with one-line descriptions

`api-reference.md` serves as the landing page with a table of all public APIs grouped by module, linking to their detail pages.

## Risks / Trade-offs

- [mkdocstrings rendering issues] → If docstrings have formatting issues, they'll show in the generated docs. Mitigation: verify with `just docs` build.
- [Nav section rename changes top-level tab] → Users accustomed to "Reference" tab will see "Guides". Low risk since this is a docs-only project not yet at 1.0.
