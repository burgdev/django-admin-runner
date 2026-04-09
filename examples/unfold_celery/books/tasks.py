"""Per-command Celery tasks for the books app.

These tasks appear individually in Celery Beat's task selector, making it easy
to schedule specific commands without manually typing the task name.
"""
from __future__ import annotations

from celery import shared_task


@shared_task(name="books.import_books")
def import_books(source: str = "books.csv", dry_run: bool = False, limit: int = 0) -> None:
    """Import books from a source file."""
    from django_admin_runner.celery_tasks import schedule_command

    schedule_command("import_books", {"source": source, "dry_run": dry_run, "limit": limit})


@shared_task(name="books.export_report")
def export_report(format: str = "csv") -> None:  # noqa: A002
    """Export a book report."""
    from django_admin_runner.celery_tasks import schedule_command

    schedule_command("export_report", {"format": format})


@shared_task(name="books.cleanup_books")
def cleanup_books(older_than: int = 90) -> None:
    """Remove duplicate and orphaned book records."""
    from django_admin_runner.celery_tasks import schedule_command

    schedule_command("cleanup_books", {"older_than": older_than})
