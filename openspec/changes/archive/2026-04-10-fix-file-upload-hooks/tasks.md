## 1. Hooks System Core

- [x] 1.1 Create `src/django_admin_runner/hooks.py` with `CommandHook` protocol class (abstract `setup` and `teardown` methods), `HookContext` (dict-like state bag), and `get_hooks()` loader that reads `ADMIN_RUNNER_HOOKS` setting and instantiates hook singletons
- [x] 1.2 Implement `TempFileHook` in `hooks.py` — `setup()` creates unique dir under `ADMIN_RUNNER_UPLOAD_PATH` and stores path in `HookContext`, `teardown()` deletes the directory; auto-registers only when `ADMIN_RUNNER_UPLOAD_PATH` is set
- [x] 1.3 Integrate hooks into `execute_command()` in `tasks.py` — create `HookContext`, call `setup()` on all hooks before `call_command()`, call `teardown()` in `finally:` block in reverse order; teardown errors logged but not raised

## 2. Widget Fix

- [x] 2.1 Update `FileOrPathWidget` in `forms.py` — override `get_context()` to pass `upload_enabled` flag (checks `ADMIN_RUNNER_UPLOAD_PATH` setting at render time), select template name based on Unfold availability
- [x] 2.2 Rewrite `src/django_admin_runner/templates/django_admin_runner/widgets/file_or_path.html` for classic admin — styled file input with admin CSS, text path input, conditional rendering based on `upload_enabled`
- [x] 2.3 Create `src/django_admin_runner/templates/django_admin_runner/widgets/file_or_path_unfold.html` for Unfold — upload icon trigger (`file_upload` material symbol), hidden file input, Unfold Tailwind classes, no clear/download buttons
- [x] 2.4 Update `FileOrPathField.compress()` to save files to `ADMIN_RUNNER_UPLOAD_PATH` instead of `tempfile.mkdtemp()`, using the temp dir path from `HookContext` when available

## 3. Unfold Integration

- [x] 3.1 Update `_apply_unfold_widget()` in `forms.py` to replace `FileOrPathField`'s template with the Unfold variant instead of only swapping the text sub-widget

## 4. Tests

- [x] 4.1 Test `HookContext` — dict-like get/set, fresh instance per execution
- [x] 4.2 Test `get_hooks()` — loads hooks from setting, auto-registers `TempFileHook` when upload path set, skips when not set
- [x] 4.3 Test `TempFileHook` — creates and deletes temp directory, stores path in context, teardown is non-fatal on error
- [x] 4.4 Test hooks integration in `execute_command()` — setup/teardown called in correct order, teardown runs on command failure, teardown errors logged but don't override status
- [x] 4.5 Test `FileOrPathWidget` rendering — file input present when upload enabled, absent when disabled, correct template selected for classic/Unfold
- [x] 4.6 Test `FileOrPathField.compress()` — saves to `ADMIN_RUNNER_UPLOAD_PATH`, returns path string
