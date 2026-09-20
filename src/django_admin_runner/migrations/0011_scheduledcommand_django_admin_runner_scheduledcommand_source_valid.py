from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_admin_runner", "0010_commandexecution_label"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="scheduledcommand",
            constraint=models.CheckConstraint(
                condition=models.Q(source__in=["code", "admin"]),
                name="django_admin_runner_scheduledcommand_source_valid",
            ),
        ),
    ]
