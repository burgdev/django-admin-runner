## 1. Admin changelist description truncation

- [x] 1.1 In `admin.py` `RegisteredCommandAdmin.name_link`, replace the hard-coded `max-width:300px` with `max-width:100%` on the description `<span>`, and change `display:inline-block` to `display:block` so the element fills its parent column width
- [x] 1.2 Verify the description renders correctly in the Django admin changelist — short descriptions show in full, long ones truncate with ellipsis

## 2. List template description truncation

- [x] 2.1 In `templates/django_admin_runner/unfold/list.html`, add `style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"` to the description `<p>` element
- [x] 2.2 In `templates/django_admin_runner/base/list.html`, add `style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"` to the description `<td>` element

## 3. Verification

- [x] 3.1 Run `just check` to ensure linting passes
- [x] 3.2 Run `just tests` to ensure all tests pass
