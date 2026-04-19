## Why

All example projects (classic, unfold_celery, unfold_rq) return a 404 when accessing the root URL ("/"). Django has a built-in welcome page ("The install worked successfully!") that shows when the URLconf contains only the admin pattern. However, the `static()` call for media files adds extra URL patterns, which causes Django's default-urlconf check to fail — resulting in a generic 404 instead of the welcome page.

## What Changes

- Remove the `static()` media URL patterns from example `urls.py` files so Django's built-in welcome page is shown at the root URL
- No changes to the main package — this is an example-only fix

## Capabilities

### New Capabilities

- `root-welcome-page`: Show Django's default welcome page at the root URL in example projects by removing unnecessary static media patterns

### Modified Capabilities

## Impact

- Example project `urls.py` files only (classic, unfold_celery, unfold_rq)
- No impact on the main `django_admin_runner` package or its users
