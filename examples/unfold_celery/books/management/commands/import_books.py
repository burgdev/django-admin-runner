import argparse
import csv

from django.core.management.base import BaseCommand

from django_admin_runner import FileOrPathField, register_command, set_result_html


@register_command(group="Import", params=["source", "dry_run", "limit"])
class Command(BaseCommand):
    help = "Import books from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            widget=FileOrPathField(),
            default="books.csv",
            help="CSV file path or upload (columns: title, author, published_date, isbn)",
        )
        parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
        parser.add_argument("--limit", type=int, default=0, help="Max records (0 = all)")
        parser.add_argument("--internal-flag", help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        source = options["source"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        try:
            fh = open(source)  # noqa: SIM115
        except FileNotFoundError:
            self.stderr.write(f"File not found: {source}")
            return

        rows_imported = []
        skipped = 0

        with fh:
            reader = csv.DictReader(fh)
            created = 0

            for row in reader:
                title = row.get("title", "").strip()
                author = row.get("author", "").strip()
                if not title or not author:
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  Would import: {title} by {author}")
                else:
                    from books.models import Book

                    Book.objects.get_or_create(
                        title=title,
                        author=author,
                        defaults={
                            "published_date": row.get("published_date") or None,
                            "isbn": row.get("isbn", "").strip(),
                        },
                    )
                rows_imported.append((title, author))
                created += 1

                if limit and created >= limit:
                    break

        action = "Would import" if dry_run else "Imported"
        self.stdout.write(self.style.SUCCESS(f"{action} {created} book(s), skipped {skipped}"))

        # Generate HTML summary table
        table_rows = "".join(
            f"<tr><td>{title}</td><td>{author}</td></tr>" for title, author in rows_imported
        )
        set_result_html(
            f"<h2>{action} {created} book(s), skipped {skipped}</h2>"
            f'<table border="1" cellpadding="4" cellspacing="0">'
            f"<tr><th>Title</th><th>Author</th></tr>"
            f"{table_rows}"
            f"</table>"
        )
