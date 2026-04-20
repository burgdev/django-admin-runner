## Context

The result page for command executions currently renders stdout/stderr as ANSI-colored `<pre>` blocks. Commands have no structured feedback channel — they write text to stdout and that's it. Hooks can only clean up in `teardown()` (which runs *after* the execution record is saved), so they can't shape what gets persisted. URLs in output are plain text.

The execution flow is: `setup hooks → call_command → save execution → teardown hooks`. The command is a black box communicating only through stdout/stderr buffers.

## Goals / Non-Goals

**Goals:**
- Enable commands and hooks to produce rich HTML results (tables, download links, summaries)
- Provide `is_admin_runner()` so commands can detect execution context
- Restructure hooks to allow pre-save state modification
- Make URLs in stdout/stderr clickable
- Present result HTML prominently in the admin (dedicated view, list button, detail preview)

**Non-Goals:**
- File serving or storage management (commands handle their own file I/O)
- Binary file handling in result_html (text-only HTML output)
- Structured result data / JSONField approach (raw HTML is simpler and more flexible)
- Permission-protected file downloads (commands that need this can implement their own views)

## Decisions

### 1. contextvars for execution context

Use `contextvars.ContextVar` to hold a mutable dict per execution. Commands call `set_result_html(html)` which writes to this dict. `execute_command()` reads it after hooks complete.

**Why contextvars over alternatives:**
- `self.result_html` on the command: requires loading command instance ourselves, bypassing `call_command`. More invasive.
- Extra kwargs to `call_command`: pollutes the command's options namespace.
- `HookContext`: only available to hooks, not to the command itself.
- Thread-local: doesn't work cleanly with async; contextvars are the modern replacement.

The contextvar dict also holds metadata hooks might need. `is_admin_runner()` checks whether the contextvar is set.

### 2. Hook point restructuring: setup / pre_save / post_save

Replace `setup`/`teardown` with three hook points:

```
setup()     → before call_command      (prepare resources)
pre_save()  → after command, before save (modify execution state)
post_save() → after save               (cleanup, notify)
```

**Why three points:**
- `pre_save` is the key addition — hooks can read stdout/stderr, transform output, set result_html, redact secrets
- `post_save` replaces `teardown` with clearer semantics: the record is durable, safe to reference by PK
- All three points are non-fatal on error (logged, not raised) matching existing teardown behavior

**Hook execution order:** setup runs A, B, C. pre_save runs A, B, C (forward — first hook gets first chance to shape output). post_save runs C, B, A (reverse — cleanup in LIFO order).

### 3. URL auto-linking in ANSI renderer

Add a post-processing step after `ansi_to_html()` that finds `https?://\S+` patterns and wraps them in `<a href="..." target="_blank">...</a>`. Applied to text content only — must not break existing `<span>` elements from ANSI processing.

**Why post-process after ANSI:** The ANSI renderer already HTML-escapes text content and wraps it in spans. Running URL detection on the raw text would be fragile (ANSI codes split URLs). Running on HTML output is more reliable since URLs appear as plain text between tags.

**Implementation approach:** After `ansi_to_html()` returns, regex-replace URL patterns in the HTML string. The regex operates on HTML-escaped text, so `&amp;` etc. are already resolved. Anchor tag insertion must not nest inside existing attributes.

### 4. Admin result view architecture

New URL: `/admin/django_admin_runner/commandexecution/<pk>/result/`

- If `result_html` is set: renders `result_html` as a full standalone page (via `mark_safe`)
- If not: renders stdout/stderr with ANSI formatting (same as current detail view)
- Protected by same permission checks as the detail view
- Linked from change list as `[RESULT]` or `[OUTPUT]` button (target `_blank`)
- Linked from detail view as "Full View" alongside a scrollable preview

### 5. result_html on the model, not a separate storage

`result_html = models.TextField(blank=True)` on `CommandExecution`. Simple, no file storage concerns, queryable.

**Why not FileField:** HTML is text, not a file. Storing it in the DB keeps the model self-contained and avoids MEDIA_ROOT configuration.

## Risks / Trade-offs

- **[XSS via result_html]** → result_html is developer-written (command authors). Same trust level as Django views. If dynamic content is included, command authors should use `format_html()`. Document this clearly.
- **[BREAKING hook protocol]** → All hook subclasses must rename `teardown` to `post_save`. `TempFileHook` is the only built-in. Document the migration path clearly.
- **[URL regex false positives]** → Long URLs with trailing punctuation may include unwanted chars. Use a conservative regex and consider trailing punctuation stripping.
- **[Large result_html]** → TextField has no size limit. Very large HTML could bloat the DB. → Mitigation: document that result_html should be summary-level, not full data dumps. Commands generating huge output should use stdout.
- **[contextvars in Celery prefork]** → Each worker process has its own context (contextvars are per-thread, and prefork creates new processes). This is correct behavior — each task execution gets an isolated context.

## Open Questions

- Should the result view template inherit from the admin base template (consistent chrome) or be a minimal standalone page? Lean toward admin chrome for consistency.
- Should `[RESULT]` vs `[OUTPUT]` use different colors/icons? Suggestion: same button, different label based on whether result_html is set.
