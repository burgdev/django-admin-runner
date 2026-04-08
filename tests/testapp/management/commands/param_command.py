from django.core.management.base import BaseCommand

from django_admin_runner.registry import register_command


@register_command(group="Test")
class Command(BaseCommand):
    help = "Command with typed parameters"

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1, help="Number of iterations")
        parser.add_argument(
            "--mode", choices=["fast", "slow"], default="fast", help="Execution mode"
        )
        parser.add_argument(
            "--verbose", action="store_true", default=False, help="Enable verbose output"
        )

    def handle(self, *args, **options):
        self.stdout.write(f"count={options['count']} mode={options['mode']}")
