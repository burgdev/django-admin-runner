import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_admin_runner", "0006_commandoutputpart"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledCommand",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("command_name", models.CharField(max_length=200)),
                ("label", models.CharField(blank=True, max_length=200)),
                ("enabled", models.BooleanField(default=True)),  # type: ignore[assignment]
                (
                    "source",
                    models.CharField(
                        choices=[("code", "Declared in code"), ("admin", "Created in admin")],
                        default="admin",
                        max_length=10,
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("cron", "Cron"),
                            ("interval", "Interval"),
                            ("clocked", "One-off (clocked)"),
                        ],
                        max_length=10,
                    ),
                ),
                ("cron", models.CharField(blank=True, max_length=100)),
                ("interval_minutes", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "repeats",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Number of runs for interval schedules (empty = run forever).",
                        null=True,
                    ),
                ),
                ("run_at", models.DateTimeField(blank=True, null=True)),
                ("kwargs", models.JSONField(default=dict, blank=True)),
                ("backend_schedule_key", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Schedule",
                "verbose_name_plural": "Schedules",
                "ordering": ["command_name", "label"],
            },
        ),
        migrations.AddConstraint(
            model_name="scheduledcommand",
            constraint=models.UniqueConstraint(
                condition=models.Q(source="code"),
                fields=("command_name", "source", "label"),
                name="django_admin_runner_scheduledcommand_code_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="scheduledcommand",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=["cron", "interval", "clocked"]),
                name="django_admin_runner_scheduledcommand_kind_valid",
            ),
        ),
        migrations.AddField(
            model_name="commandexecution",
            name="schedule",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="executions",
                to="django_admin_runner.scheduledcommand",
            ),
        ),
    ]
