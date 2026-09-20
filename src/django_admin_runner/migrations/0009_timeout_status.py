from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_admin_runner", "0008_execution_cancellation"),
    ]

    operations = [
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
                    ("TIMEOUT", "Timed out"),
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
                    status__in=[
                        "PENDING",
                        "RUNNING",
                        "SUCCESS",
                        "FAILED",
                        "CANCELLED",
                        "TIMEOUT",
                    ]
                ),
                name="django_admin_runner_commandexecution_status_valid",
            ),
        ),
    ]
