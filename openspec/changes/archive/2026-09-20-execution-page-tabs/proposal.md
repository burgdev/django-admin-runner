# Proposal: execution-page-tabs

## Why

The `CommandExecution` change page mixes live output with static metadata in
one long form: the terminals sit below command name, kwargs, task id, etc.
Output is what you open the page for (especially while a command runs), and
the surrounding metadata plus the Django "Save" button invite the wrong
interaction (users think they must click Save to see output — they don't).

## What Changes

- Reorganize the change page into two tabs:
  - **Output** (default tab): status badge + live timer, the stdout and
    stderr terminals, and the result HTML block.
  - **Input**: command name, kwargs (parameters), triggered_by, backend,
    task_id, created/started/finished timestamps — the metadata.
- Unfold: use its native fieldset tabs (`classes=["tab"]` on the fieldsets)
  — no custom work beyond restructuring.
- Base Django admin theme: ship a small fallback (tab bar CSS + ~30 lines
  JS in the package's static files) applied via the change_form template so
  both themes render tabs; Unfold's own tabs are used when installed.
- Terminal live behaviour, endpoints, and widget code are unchanged — this
  is layout only. The terminals render at **100% width** of the content
  area in both themes (they were squeezed inside narrow fieldset columns). The terminals always render (existing behaviour after the
  empty-output placeholder fix), so opening the page right after launching a
  command shows live output in the default tab immediately.

## Capabilities

### New Capabilities

- `execution-page-tabs`: tabbed execution change page (Output default,
  Input metadata), Unfold-native plus base-theme fallback.

## Impact

- **Code**: `admin.py` (fieldsets restructuring), base-theme change_form
  template (tab fallback assets), new small static JS/CSS.
- **Templates**: the Unfold change form picks up `classes=["tab"]`
  automatically; the base change_form gets the fallback.
- **Behaviour**: no data or endpoint changes; the "Save" button remains
  (Django change form) but the Output tab works without any interaction.
