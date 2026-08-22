from django.conf import settings
from django.db import models


class RegisteredCommand(models.Model):
    name = models.CharField(max_length=200, unique=True)
    group = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    app_label = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)  # type: ignore[assignment]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group", "name"]
        verbose_name = "Command"
        verbose_name_plural = "Commands"

    def __str__(self) -> str:
        return self.name  # type: ignore[return-value]


class CommandExecution(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    command_name = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    result_html = models.TextField(blank=True)
    kwargs = models.JSONField(default=dict)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="command_executions",
    )
    backend = models.CharField(max_length=100, blank=True)
    task_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Result"
        verbose_name_plural = "Results"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "RUNNING", "SUCCESS", "FAILED"]),
                name="django_admin_runner_commandexecution_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.command_name} ({self.status})"

    # ------------------------------------------------------------------
    # Output parts helpers
    # ------------------------------------------------------------------

    def output_parts_for(self, field: str):
        """All output parts for *field* ("stdout"/"stderr"), ordered by seq."""
        return self.output_parts.filter(field=field).order_by("seq")

    def output_text(self, field: str) -> str:
        """Concatenated retained output for *field*."""
        return "".join(part.text for part in self.output_parts_for(field))

    def output_len(self, field: str) -> int:
        """Total retained characters for *field*."""
        from django.db.models.functions import Length

        return (
            self.output_parts_for(field).aggregate(total=models.Sum(Length("text")))["total"] or 0
        )

    def has_output(self, field: str) -> bool:
        return self.output_parts.filter(field=field).exists()


class CommandOutputPart(models.Model):
    """One sealed chunk of command output (at most ``PART_SIZE`` characters).

    Output is stored as an ordered sequence of immutable parts per
    (execution, field).  Live flushes append at the database level to the
    single *active* (highest-seq) part; when a part would exceed
    ``PART_SIZE`` it is sealed and a new empty part becomes active.
    """

    PART_SIZE = 512 * 1024

    class Field(models.TextChoices):
        STDOUT = "stdout", "stdout"
        STDERR = "stderr", "stderr"

    execution = models.ForeignKey(
        CommandExecution,
        on_delete=models.CASCADE,
        related_name="output_parts",
        db_index=True,
    )
    field = models.CharField(max_length=10, choices=Field.choices)
    seq = models.IntegerField()
    text = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "field", "seq"],
                name="django_admin_runner_part_unique_seq",
            ),
            models.CheckConstraint(
                condition=models.Q(field__in=["stdout", "stderr"]),
                name="django_admin_runner_part_field_valid",
            ),
        ]
        ordering = ["execution", "field", "seq"]

    def __str__(self) -> str:
        return f"{self.execution_id}:{self.field}:{self.seq}"
