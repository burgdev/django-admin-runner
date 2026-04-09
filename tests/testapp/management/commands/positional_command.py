from django.core.management.base import BaseCommand

from django_admin_runner import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Command with a positional argument"

    def add_arguments(self, parser):
        parser.add_argument("filename", help="Input file path")
        parser.add_argument("--count", type=int, default=1, help="Repeat count")

    def handle(self, *args, **options):
        pass
