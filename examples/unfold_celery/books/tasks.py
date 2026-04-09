"""Celery tasks for the books app.

NOTE: Per-command Celery tasks are now registered automatically by
django-admin-runner.  Each ``@register_command``-decorated management command
gets its own task named ``<app_label>.<command_name>`` (e.g. ``books.import_books``).

This file previously defined those tasks manually — that is no longer needed.
You can delete this file; it is kept here only as a migration reference.
"""
