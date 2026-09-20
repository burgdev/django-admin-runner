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
        CANCELLED = "CANCELLED", "Cancelled"
        TIMEOUT = "TIMEOUT", "Timed out"

    command_name = models.CharField(max_length=200)
    label = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Optional label: set on the run form (manual runs) "
        "or copied from the schedule (scheduled runs).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    result_html = models.TextField(blank=True)
    kwargs = models.JSONField(default=dict)
    stop_requested = models.BooleanField(
        default=False,  # type: ignore[assignment]
        help_text="Set when a graceful stop was requested from the admin.",
    )
    worker_pid = models.IntegerField(
        null=True,
        blank=True,
        help_text="OS PID of the process running the command, recorded at start.",
    )
    schedule = models.ForeignKey(
        "ScheduledCommand",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="executions",
    )
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


class ScheduledCommand(models.Model):
    """Library-owned schedule definition — the source of truth.

    Rows are materialized into the active runner's native schedule objects
    (e.g. django-q2 ``Schedule``) via the runner's schedule CRUD API; the
    native reference is stored in ``backend_schedule_key``.  ``enabled=False``
    removes the native object but keeps this row (audit trail / re-enabling).
    """

    class Kind(models.TextChoices):
        CRON = "cron", "Cron"
        INTERVAL = "interval", "Interval"
        CLOCKED = "clocked", "One-off (clocked)"

    class Source(models.TextChoices):
        CODE = "code", "Declared in code"
        ADMIN = "admin", "Created in admin"

    command_name = models.CharField(max_length=200)
    label = models.CharField(max_length=200, blank=True)
    enabled = models.BooleanField(default=True)  # type: ignore[assignment]
    source = models.CharField(
        max_length=10,
        choices=Source.choices,
        default=Source.ADMIN,
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    cron = models.CharField(max_length=100, blank=True)
    interval_minutes = models.PositiveIntegerField(null=True, blank=True)
    repeats = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of runs for interval schedules (empty = run forever).",
    )
    run_at = models.DateTimeField(null=True, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)
    backend_schedule_key = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["command_name", "label"]
        verbose_name = "Schedule"
        verbose_name_plural = "Schedules"
        constraints = [
            # Identity of declarative schedules: (command_name, source=code, label).
            models.UniqueConstraint(
                fields=["command_name", "source", "label"],
                condition=models.Q(source="code"),
                name="django_admin_runner_scheduledcommand_code_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["cron", "interval", "clocked"]),
                name="django_admin_runner_scheduledcommand_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=["code", "admin"]),
                name="django_admin_runner_scheduledcommand_source_valid",
            ),
        ]

    def __str__(self) -> str:
        return str(self.label or f"{self.command_name} ({self.get_kind_display()})")

    def clean(self) -> None:
        from django.core.exceptions import ValidationError
        from django.utils.timezone import now

        from .forms import validate_command_kwargs
        from .models import RegisteredCommand

        errors = {}
        is_active = (
            RegisteredCommand.objects.filter(name=self.command_name, active=True).exists()
            if self.command_name
            else False
        )
        if not self.command_name or not is_active:
            errors["command_name"] = ValidationError(
                "Select a valid, active command.", code="invalid"
            )

        if self.kind == self.Kind.CRON:
            if not self.cron:
                errors["cron"] = ValidationError("Enter a cron expression.", code="required")
            else:
                try:
                    from .schedules import validate_cron_expression

                    validate_cron_expression(str(self.cron))
                except ValueError as exc:
                    errors["cron"] = ValidationError(str(exc), code="invalid")
        elif self.kind == self.Kind.INTERVAL:
            if not self.interval_minutes or self.interval_minutes <= 0:
                errors["interval_minutes"] = ValidationError(
                    "Interval must be a positive number of minutes.", code="invalid"
                )
        elif self.kind == self.Kind.CLOCKED:
            if self.run_at is None:
                errors["run_at"] = ValidationError("Enter a run date/time.", code="required")
            elif self.run_at <= now():
                errors["run_at"] = ValidationError(
                    "Run date/time must be in the future.", code="invalid"
                )

        if self.command_name and is_active:
            try:
                validate_command_kwargs(str(self.command_name), self.kwargs or {})  # type: ignore[arg-type]
            except ValidationError as exc:
                errors["kwargs"] = exc

        if errors:
            raise ValidationError(errors)

    def schedule_summary(self) -> str:
        if self.kind == self.Kind.CRON:
            return str(self.cron or "—")
        if self.kind == self.Kind.INTERVAL:
            return f"every {self.interval_minutes} min"
        if self.kind == self.Kind.CLOCKED:
            if not self.run_at:
                return "—"
            from django.utils.formats import localize
            from django.utils.timezone import localtime

            return localize(localtime(self.run_at))
        return self.get_kind_display()
