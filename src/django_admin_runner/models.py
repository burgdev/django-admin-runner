from django.conf import settings
from django.db import models


class RegisteredCommand(models.Model):
    name = models.CharField(max_length=200, unique=True)
    group = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    app_label = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group", "name"]
        verbose_name = "Command"
        verbose_name_plural = "Commands"

    def __str__(self) -> str:
        return self.name


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
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
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

    def __str__(self) -> str:
        return f"{self.command_name} ({self.status})"
