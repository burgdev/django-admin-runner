import random
import time

from django.core.management.base import BaseCommand
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from django_admin_runner import register_command

STAGES = ["Indexing", "Parsing", "Validating", "Transforming", "Loading", "Finalizing"]
UNITS = ["rows", "records", "docs", "items", "chunks", "events"]


@register_command(
    group="Maintenance",
    flush_interval=0.1,  # smooth live progress-bar updates in the admin
)
class Command(BaseCommand):
    help = "Simulate a long-running job with rich live progress output"

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=float,
            default=1.0,
            help="How long the simulation runs (minutes)",
        )
        parser.add_argument(
            "--bars",
            type=int,
            default=3,
            help="How many progress bars to animate (1-40)",
        )

    def handle(self, *args, **options):
        minutes = max(0.01, options["minutes"])
        num_bars = max(1, min(40, options["bars"]))
        deadline = time.monotonic() + minutes * 60

        overall = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        )
        overall_task = overall.add_task("Overall", total=minutes * 60)

        stage = Progress(
            SpinnerColumn(),
            TextColumn("[yellow]{task.fields[stage]}"),
            TimeElapsedColumn(),
        )
        stage_task = stage.add_task("Stage", stage=STAGES[0])

        bars = Progress(
            TextColumn("[cyan]{task.description:>14}"),
            BarColumn(complete_style="green", finished_style="bright_green"),
            TaskProgressColumn(),
            TextColumn("[dim]{task.fields[unit]}"),
            TimeElapsedColumn(),
        )
        bar_tasks = []
        for i in range(num_bars):
            bar_tasks.append(
                bars.add_task(
                    f"Worker {i + 1}",
                    total=random.randint(20, 100),
                    unit=random.choice(UNITS),
                )
            )

        throughput_txt = Text("0.0 units/s")
        errors_txt = Text("0", style="green")
        eta_txt = Text(f"{minutes:.1f} min")
        stats = Table.grid(padding=(0, 1))
        stats.add_column(style="bold", justify="right")
        stats.add_column()
        stats.add_row("Throughput:", throughput_txt)
        stats.add_row("Errors:", errors_txt)
        stats.add_row("ETA:", eta_txt)

        widget = Panel(
            Group(overall, stage, Text(""), bars, Text(""), stats),
            title=f"[bold]Workload Simulator[/] — {num_bars} workers",
            subtitle="[dim]ctrl-c to abort[/]",
            border_style="blue",
        )

        errors = 0
        processed = 0
        with Live(widget, refresh_per_second=4, screen=False):
            while time.monotonic() < deadline:
                elapsed = time.monotonic() - (deadline - minutes * 60)
                overall.update(overall_task, completed=min(elapsed, minutes * 60))
                stage.update(stage_task, stage=STAGES[int(elapsed / (minutes * 60) * len(STAGES))])

                for i, task_id in enumerate(bar_tasks):
                    step = random.choice([0, 1, 1, 2, 5])
                    bars.advance(task_id, step)
                    processed += step
                    task = bars.tasks[i]
                    if task.finished:
                        bars.reset(task_id, total=random.randint(20, 100))
                    if random.random() < 0.02:
                        errors += 1
                        self.stderr.write(f"[worker {i + 1}] unit {processed} failed (simulated)")

                throughput_txt.plain = f"{processed / max(elapsed, 0.1):.1f} units/s"
                errors_txt.plain = str(errors)
                errors_txt.stylize("red" if errors else "green", 0, len(errors_txt.plain))
                eta_txt.plain = f"{max(0.0, (deadline - time.monotonic()) / 60):.1f} min"

                time.sleep(0.25)

        self.stdout.write(
            self.style.SUCCESS(
                f"Simulated {processed} units across {num_bars} workers in {minutes:g} min"
            )
        )
        if errors:
            self.stderr.write(f"{errors} simulated errors occurred")
