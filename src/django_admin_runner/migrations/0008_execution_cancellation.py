from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_admin_runner", "0007_scheduledcommand"),
    ]

    operations = [
        migrations.AddField(
            model_name="commandexecution",
            name="stop_requested",
            field=models.BooleanField(
                default=False,  # type: ignore[assignment]
                help_text="Set when a graceful stop was requested from the admin.",
            ),
        ),
        migrations.AddField(
            model_name="commandexecution",
            name="worker_pid",
            field=models.IntegerField(
                blank=True,
                help_text="OS PID of the process running the command, recorded at start.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="commandexecution",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("RUNNING", "Running"),
                    ("SUCCESS", "Success"),
                    ("FAILED", "Failed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="commandexecution",
            name="django_admin_runner_commandexecution_status_valid",
        ),
        migrations.AddConstraint(
            model_name="commandexecution",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=["PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]
                ),
                name="django_admin_runner_commandexecution_status_valid",
            ),
        ),
    ]
