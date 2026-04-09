import argparse

from django.core.management.base import BaseCommand

from django_admin_runner import FileOrPathField, register_command


@register_command(group="Import", params=["source", "dry_run", "limit"])
class Command(BaseCommand):
    help = "Import books from a source file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            widget=FileOrPathField(),
            default="books.csv",
            help="Source file path or upload",
        )
        parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
        parser.add_argument("--limit", type=int, default=0, help="Max records (0 = all)")
        parser.add_argument("--internal-flag", help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        self.stdout.write(
            f"Importing from {options['source']} "
            f"(dry_run={options['dry_run']}, limit={options['limit']})"
        )
