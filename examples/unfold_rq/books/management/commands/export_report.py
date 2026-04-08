import argparse

from django.core.management.base import BaseCommand

from django_admin_runner import register_command


@register_command(group="Export")
class Command(BaseCommand):
    help = "Export a book report in various formats"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["csv", "json", "xlsx"],
            default="csv",
            help="Output format",
        )
        parser.add_argument("--output-path", help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        self.stdout.write(f"Exporting report as {options['format']}")
