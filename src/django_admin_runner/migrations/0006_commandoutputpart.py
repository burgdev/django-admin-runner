import django.db.models.deletion
from django.db import migrations, models

PART_SIZE = 512 * 1024


def forwards(apps, schema_editor):
    CommandExecution = apps.get_model("django_admin_runner", "CommandExecution")
    CommandOutputPart = apps.get_model("django_admin_runner", "CommandOutputPart")

    for execution in CommandExecution.objects.iterator():
        for field_name in ("stdout", "stderr"):
            text = execution.__dict__.get(field_name) or ""
            if not text:
                continue
            parts = []
            for i in range(0, len(text), PART_SIZE):
                parts.append(
                    CommandOutputPart(
                        execution=execution,
                        field=field_name,
                        seq=i // PART_SIZE,
                        text=text[i : i + PART_SIZE],
                    )
                )
            CommandOutputPart.objects.bulk_create(parts)


def backwards(apps, schema_editor):
    # Best-effort: recreate the legacy fields and concatenate parts back.
    CommandExecution = apps.get_model("django_admin_runner", "CommandExecution")
    CommandOutputPart = apps.get_model("django_admin_runner", "CommandOutputPart")

    for execution in CommandExecution.objects.iterator():
        for field_name in ("stdout", "stderr"):
            text = "".join(
                part.text
                for part in CommandOutputPart.objects.filter(
                    execution=execution, field=field_name
                ).order_by("seq")
            )
            setattr(execution, field_name, text)
        execution.save(update_fields=["stdout", "stderr"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "django_admin_runner",
            "0005_commandexecution_django_admin_runner_commandexecution_status_valid",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="CommandOutputPart",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "field",
                    models.CharField(
                        choices=[("stdout", "stdout"), ("stderr", "stderr")], max_length=10
                    ),
                ),
                ("seq", models.IntegerField()),
                ("text", models.TextField()),
                (
                    "execution",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="output_parts",
                        to="django_admin_runner.commandexecution",
                    ),
                ),
            ],
            options={
                "ordering": ["execution", "field", "seq"],
            },
        ),
        migrations.AddConstraint(
            model_name="commandoutputpart",
            constraint=models.UniqueConstraint(
                fields=("execution", "field", "seq"),
                name="django_admin_runner_part_unique_seq",
            ),
        ),
        migrations.AddConstraint(
            model_name="commandoutputpart",
            constraint=models.CheckConstraint(
                condition=models.Q(field__in=["stdout", "stderr"]),
                name="django_admin_runner_part_field_valid",
            ),
        ),
        # Data migration: move legacy stdout/stderr into parts, then drop the fields.
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="commandexecution",
            name="stdout",
        ),
        migrations.RemoveField(
            model_name="commandexecution",
            name="stderr",
        ),
    ]
