import argparse

from django.core.management.base import BaseCommand

from django_admin_runner import is_admin_runner, register_command, set_result_html


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
        fmt = options["format"]
        self.stdout.write(f"Exporting report as {fmt}")

        # Write a sample report file to MEDIA_ROOT
        import os

        from django.conf import settings

        media_root = getattr(settings, "MEDIA_ROOT", "")
        if media_root:
            os.makedirs(media_root, exist_ok=True)
            filename = f"report.{fmt}"
            filepath = os.path.join(media_root, filename)
            with open(filepath, "w") as f:
                f.write("title,author\nHamlet,Shakespeare\n")
            media_url = getattr(settings, "MEDIA_URL", "/media/")
            download_url = f"{media_url.rstrip('/')}/{filename}"

            if is_admin_runner():
                base_url = getattr(settings, "ADMIN_RUNNER_BASE_URL", "")
                if base_url:
                    download_url = f"{base_url.rstrip('/')}{download_url}"

            self.stdout.write(self.style.SUCCESS(f"Report saved to {download_url}"))

            # Set rich result HTML with a download link
            set_result_html(
                f"<h2>Export Complete</h2>"
                f"<p>Format: <strong>{fmt.upper()}</strong></p>"
                f'<p><a href="{download_url}">Download report</a></p>'
            )
