## 1. Execution Context (contextvars)

- [x] 1.1 Create `src/django_admin_runner/context.py` with `_execution_ctx` ContextVar, `is_admin_runner()`, and `set_result_html()` functions
- [x] 1.2 Export `is_admin_runner` and `set_result_html` from `__init__.py`
- [x] 1.3 Add tests for `is_admin_runner()` returning True during execution, False outside
- [x] 1.4 Add test for `set_result_html()` storing value and being a no-op outside execution

## 2. Model & Migration

- [x] 2.1 Add `result_html = models.TextField(blank=True)` to `CommandExecution` model
- [x] 2.2 Create and commit the migration

## 3. Hook Protocol Restructure

- [x] 3.1 Rename `teardown()` to `post_save()` on `CommandHook` base class in `hooks.py`
- [x] 3.2 Add `pre_save()` method to `CommandHook` base class (no-op default)
- [x] 3.3 Update `TempFileHook` to use `post_save()` instead of `teardown()`
- [x] 3.4 Update `execute_command()` in `tasks.py` to call hooks at three points: setup → call_command → pre_save → save → post_save
- [x] 3.5 Wire contextvar into `execute_command()`: set before setup, read result_html after pre_save, clear after post_save
- [x] 3.6 Add tests for three hook points executing in correct order
- [x] 3.7 Add test for pre_save hook modifying execution state (e.g., setting result_html)
- [x] 3.8 Add test for pre_save/post_save running even on command failure

## 4. URL Auto-Linking

- [x] 4.1 Add URL auto-linking post-processor to `_ansi.py` — regex find `https?://\S+` and wrap in `<a href="..." target="_blank">...</a>`
- [x] 4.2 Ensure URL linking works correctly alongside ANSI color spans
- [x] 4.3 Add tests: URL in plain text, URL with ANSI codes, multiple URLs, no protocol = no link
- [x] 4.4 Apply URL linking in `_ansi_to_html()` in `admin.py` (both stdout and stderr rendering)

## 5. Admin Result View

- [x] 5.1 Add `result_view` URL to `CommandExecutionAdmin.get_urls()` at `commandexecution/<pk>/result/`
- [x] 5.2 Implement `_result_view()` method: render result_html if set, otherwise stdout/stderr
- [x] 5.3 Add permission check (reuse `get_queryset` logic or `has_view_permission`)
- [x] 5.4 Create result view template (both base and Unfold variants)
- [x] 5.5 Add result button column to change list (`[RESULT]` or `[OUTPUT]`) with `target="_blank"`
- [x] 5.6 Update change list template to include the result button
- [x] 5.7 Add `result_html` preview to detail view fieldsets — scrollable container with max-height, plus "Full View" link
- [x] 5.8 Add tests for result view (result_html set, empty, permission denied)

## 6. Update Example Commands

- [x] 6.1 Update `export_report` command in all example projects: write CSV/JSON to `MEDIA_ROOT`, call `set_result_html()` with download link HTML
- [x] 6.2 Update `import_books` command in all example projects: call `set_result_html()` with an HTML summary table of imported books
- [x] 6.3 Verify examples work manually (or note in README)

## 7. Final Checks

- [x] 7.1 Run `just tests` — all tests pass
- [x] 7.2 Run `just check` — linting passes
- [x] 7.3 Run `just check types` — pyright passes
