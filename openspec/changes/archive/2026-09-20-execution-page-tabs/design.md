# Design: execution-page-tabs

## Context

- `CommandExecutionAdmin.fieldsets` currently has three flat sections
  (metadata, Result, Output); the terminals are last.
- Unfold renders any fieldset with `classes=["tab"]` as a tab (see
  `unfold/templates/admin/change_form.html`: fieldsets without `"tab"` render
  inline, tabbed ones via `fieldsets_tabs.html`).
- The base Django admin theme has no tabs.

## Goals / Non-Goals

**Goals:** Output-first layout; identical behaviour under Unfold and the
base theme; no changes to widget/endpoints.

**Non-Goals:** removing the Save button (Django change form mechanics);
per-field customization; history tab.

## Decisions

### D1: Fieldset structure (drives both themes)

```python
fieldsets = [
    ("Output", {"classes": ["tab"], "fields": [
        "status", "stdout_display", "stderr_display", "result_html_display",
    ]}),
    ("Input", {"classes": ["tab"], "fields": [
        "command_name", "kwargs", "triggered_by", "backend", "task_id",
        "created_at", "started_at", "finished_at",
    ]}),
]
```

- Output first ⇒ default/active tab in Unfold (first tab is active).
- `status` (readonly) moves into Output next to the terminals — the user
  sees run state where the output lives.
- Timestamps become readonly displays in Input (they already are).

### D2: Base-theme fallback

The package's `change_form.html` (base variant) includes a tiny
`execution-tabs.js` + `execution-tabs.css`:

- JS wraps the `.tab`-classed fieldsets' h2 headers into a tab bar, toggles
  visibility on click, activates the first tab. Progressive enhancement: if
  JS fails, all fieldsets render stacked (status quo).
- No dependencies; ~30 lines vanilla JS, ~20 lines CSS matching admin
  chrome.

### D3: Terminal width

The terminals fill the full content width in both themes: a small CSS rule
(scoped to `.dar-terminal` and its wrapper, shipped with the fallback assets
and also loaded under Unfold) sets `width: 100%` and lets the xterm resize
logic use the container width. Django admin fieldsets constrain form rows;
the wrapper escapes that by spanning all columns.

### D4: Unfold detection unchanged

`is_unfold_installed()` already gates template choice; the Unfold variant
needs only the restructured fieldsets (its `fieldsets_tabs.html` does the
rest). The fallback assets are only referenced by the base template.

## Risks / Trade-offs

- [Fieldset reshuffle breaks screenshots/muscle memory] → accepted; the
  information gain (output first) outweighs it.
- [Base-theme fallback styling drift across Django versions] → minimal CSS
  using existing admin classes; degradation is graceful (stacked).

## Migration Plan

Single release, layout only; no data, no endpoint, no widget changes.

## Open Questions

- None.
