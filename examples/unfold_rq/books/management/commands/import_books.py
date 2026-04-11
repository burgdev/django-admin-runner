import argparse

from django.core.management.base import BaseCommand

from django_admin_runner import register_command, set_result_html


@register_command(group="Import", params=["source", "dry_run", "limit"])
class Command(BaseCommand):
    help = "Import books from a source file"

    def add_arguments(self, parser):
        parser.add_argument("--source", default="books.csv", help="Source file path")
        parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
        parser.add_argument("--limit", type=int, default=0, help="Max records (0 = all)")
        parser.add_argument("--internal-flag", help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        source = options["source"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        self.stdout.write(f"Importing from {source} " f"(dry_run={dry_run}, limit={limit})")

        # Demo: generate an HTML summary table
        action = "Would import" if dry_run else "Imported"
        count = min(limit, 3) if limit else 3
        set_result_html(
            f"<h2>{action} {count} book(s)</h2>"
            f'<table border="1" cellpadding="4" cellspacing="0">'
            f"<tr><th>Title</th><th>Author</th></tr>"
            f"<tr><td>Hamlet</td><td>Shakespeare</td></tr>"
            f"<tr><td>The Odyssey</td><td>Homer</td></tr>"
            f"<tr><td>The Great Gatsby</td><td>Fitzgerald</td></tr>"
            f"</table>"
        )
