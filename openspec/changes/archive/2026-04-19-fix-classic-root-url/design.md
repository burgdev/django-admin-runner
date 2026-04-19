## Context

All three example projects (classic, unfold_celery, unfold_rq) are admin-only Django applications. Their `urls.py` files define an `admin/` path plus `static()` media serving in DEBUG mode. Django has a built-in "The install worked successfully!" welcome page that appears at `/` when the URLconf contains only the admin pattern. The `static()` call adds extra URL patterns (`^media/(?P<path>.*)$`), which causes Django's `technical_404_response` check (`len(tried) == 1`) to fail, producing a generic 404 instead of the welcome page.

## Goals / Non-Goals

**Goals:**
- Show Django's default welcome page at `/` in all example projects
- Keep the change minimal and consistent across all examples

**Non-Goals:**
- Creating a custom landing page or dashboard
- Changing the main `django_admin_runner` package in any way
- Adding any views, templates, or dependencies
- Serving media files in example projects (not needed — examples don't upload files)

## Decisions

**Remove `static()` media patterns from example `urls.py` files**
- The `static()` call is unnecessary for these example projects — they don't handle file uploads
- Removing it lets Django's built-in default-urlconf detection work, showing the welcome page
- This is the simplest fix — no new code, just removing unnecessary code
- Alternative considered: Adding a `RedirectView` to `/admin/` — but the welcome page is what Django shows by default for new projects and is the expected behavior

## Risks / Trade-offs

- [Media files won't be served in DEBUG mode] → Acceptable: example projects don't use media uploads. If needed, users can add `static()` back.
