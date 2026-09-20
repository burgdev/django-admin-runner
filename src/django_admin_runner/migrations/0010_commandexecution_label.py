from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_admin_runner", "0009_timeout_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="commandexecution",
            name="label",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional label: set on the run form (manual runs) "
                "or copied from the schedule (scheduled runs).",
                max_length=200,
            ),
        ),
    ]
