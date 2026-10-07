from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "django_admin_runner",
            "0011_scheduledcommand_django_admin_runner_scheduledcommand_source_valid",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="commandexecution",
            name="worker_host",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Host (machine or container) running the command, recorded at start. "
                    "PIDs are only meaningful inside their own PID namespace, so stop "
                    "signals are only sent when this matches the local host."
                ),
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="commandexecution",
            name="worker_started_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Start time of the worker OS process, recorded at start. Compared "
                    "against the process currently holding the PID to detect reuse."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="commandexecution",
            name="last_heartbeat_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Liveness heartbeat refreshed periodically by the worker while "
                    "running. The stale-run sweeper finalizes RUNNING executions whose "
                    "heartbeat went stale."
                ),
                null=True,
            ),
        ),
    ]
