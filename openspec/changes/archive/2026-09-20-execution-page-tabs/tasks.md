## 1. Fieldsets + status placement

- [x] 1.1 Restructure `CommandExecutionAdmin.fieldsets` into two `classes=["tab"]` fieldsets: Output (status, stdout_display, stderr_display, result_html_display) and Input (command_name, kwargs, triggered_by, backend, task_id, timestamps); ensure all Input fields are readonly
- [x] 1.2 Verify Unfold renders Output as the active tab and terminals still attach (live polling unchanged)

## 2. Base-theme fallback

- [x] 2.1 Add `static/django_admin_runner/execution-tabs.js` + `.css`: build a tab bar from the `.tab` fieldset headers, toggle visibility, activate the first; graceful stacked degradation without JS
- [x] 2.2 Include the fallback assets in the base `change_form.html`; load the terminal-width CSS in both themes (Unfold variant too)

## 3. Tests + wrap-up

- [x] 3.1 Tests: change page renders both tabs with expected fields; status appears in the Output fieldset; fallback assets referenced in the base template only
- [x] 3.2 Full test suite, lint, type checks; manual browser check in both themes
