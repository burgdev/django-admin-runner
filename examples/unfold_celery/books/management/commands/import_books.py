from django.core.management.base import BaseCommand

from django_admin_runner import register_command


@register_command(group="Import", params=["source", "dry_run", "limit"])
class Command(BaseCommand):
    help = "Import books from a source file"

    def add_arguments(self, parser):
        parser.add_argument("--source", default="books.csv", help="Source file path")
        parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
        parser.add_argument("--limit", type=int, default=0, help="Max records (0 = all)")
        parser.add_argument("--internal-flag", hidden=True, help="Internal use only")

    def handle(self, *args, **options):
        self.stdout.write(
            f"Importing from {options['source']} "
            f"(dry_run={options['dry_run']}, limit={options['limit']})"
        )
