## Why

Command descriptions in the admin changelist are truncated at a hard-coded `max-width:300px` with CSS `text-overflow:ellipsis`. This cuts off short descriptions that happen to wrap, while long descriptions may still feel too wide. The truncation should be based on the actual available space in the column rather than an arbitrary fixed width.

## What Changes

- Remove the hard-coded `max-width:300px` from the description `<span>` in `RegisteredCommandAdmin.name_link`.
- Apply CSS-based truncation that uses the full available column width (e.g., `max-width:100%` or width relative to the parent) so descriptions only truncate when they genuinely overflow their container.
- Apply the same responsive truncation to the description text in the Unfold `list.html` template (currently untruncated, which can cause layout issues with very long help text).
- Apply the same to the base `list.html` template description column.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-admin-changelist`: Description truncation in the admin changelist will use container-relative sizing instead of a fixed pixel width.

## Impact

- `src/django_admin_runner/admin.py` — `name_link` method CSS changes
- `src/django_admin_runner/templates/django_admin_runner/unfold/list.html` — add truncation CSS to description
- `src/django_admin_runner/templates/django_admin_runner/base/list.html` — add truncation CSS to description
