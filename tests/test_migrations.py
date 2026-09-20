"""Tests for the 0006 output-parts migration (legacy fields → parts)."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

APP = "django_admin_runner"
MIG_0005 = "0005_commandexecution_django_admin_runner_commandexecution_status_valid"
MIG_0006 = "0006_commandoutputpart"


@pytest.mark.django_db(transaction=True)
class TestOutputPartsMigration:
    @pytest.fixture(autouse=True)
    def _restore_latest(self):
        yield
        # Always end at the latest migration so other tests see full state.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([(APP, MIG_0006)])

    def _migrate_to(self, name):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([(APP, name)])
        return executor

    def _model(self, name, at):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        state = executor.loader.project_state([(APP, at)])
        return state.apps.get_model(APP, name)

    def test_forward_splits_and_reverse_joins(self):
        part_size = 512 * 1024
        text = "abcdefgh" * 80_000  # 640k chars → 2 parts
        stderr_text = "boom"

        # Roll back to the pre-parts schema (legacy fields present).
        self._migrate_to(MIG_0005)
        OldExecution = self._model("CommandExecution", MIG_0005)
        ex = OldExecution.objects.create(command_name="cmd", stdout=text, stderr=stderr_text)

        # Forward: parts created, legacy fields dropped.
        self._migrate_to(MIG_0006)
        NewExecution = self._model("CommandExecution", MIG_0006)
        NewPart = self._model("CommandOutputPart", MIG_0006)

        assert not any(f.name in ("stdout", "stderr") for f in NewExecution._meta.get_fields())
        parts = list(
            NewPart.objects.filter(execution_id=ex.pk, field="stdout")
            .order_by("seq")
            .values_list("text", flat=True)
        )
        assert [len(p) for p in parts] == [part_size, len(text) - part_size]
        assert "".join(parts) == text  # byte-identical
        stderr_parts = list(
            NewPart.objects.filter(execution_id=ex.pk, field="stderr").values_list(
                "text", flat=True
            )
        )
        assert stderr_parts == [stderr_text]

        # Reverse: fields recreated and parts concatenated back.
        self._migrate_to(MIG_0005)
        OldExecution = self._model("CommandExecution", MIG_0005)
        restored = OldExecution.objects.get(pk=ex.pk)
        assert restored.stdout == text
        assert restored.stderr == stderr_text

    def test_empty_fields_skipped(self):
        self._migrate_to(MIG_0005)
        OldExecution = self._model("CommandExecution", MIG_0005)
        ex = OldExecution.objects.create(command_name="cmd2", stdout="", stderr="")

        self._migrate_to(MIG_0006)
        NewPart = self._model("CommandOutputPart", MIG_0006)
        assert NewPart.objects.filter(execution_id=ex.pk).count() == 0
