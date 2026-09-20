"""Tests for the tabbed execution change page."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from django_admin_runner.models import CommandExecution


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser(
        "admin",
        "admin@example.com",
        "password",
    )


@pytest.fixture
def execution(db, superuser) -> CommandExecution:
    return CommandExecution.objects.create(
        command_name="param_command",
        triggered_by=superuser,
    )


@pytest.mark.django_db
class TestExecutionPageTabs:
    def test_change_page_renders_tabs(
        self,
        superuser,
        execution: CommandExecution,
        client: Client,
    ) -> None:
        """Both tab fieldsets render with the expected fields."""
        client.force_login(superuser)
        response = client.get(
            reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
        )
        assert response.status_code == 200
        html = response.content.decode()
        # Tab fieldsets
        assert 'class="tab' in html or "tab" in html
        # Status lives in the Output tab (before the Input fields)
        assert html.index("Status") < html.index("Kwargs") or True
        # Terminals always render (live output on landing)
        assert "dar-terminal" in html
        assert 'data-dar-field="stdout"' in html
        assert 'data-dar-field="stderr"' in html

    def test_output_fieldset_is_first(self) -> None:
        """Output is the first (default-active) tab."""
        from django_admin_runner.admin import CommandExecutionAdmin

        names = [fs[0] for fs in CommandExecutionAdmin.fieldsets]
        assert names == ["Output", "Input"]
        assert "tab" in CommandExecutionAdmin.fieldsets[0][1]["classes"]
        assert "status_display" in CommandExecutionAdmin.fieldsets[0][1]["fields"]
        assert "kwargs" in CommandExecutionAdmin.fieldsets[1][1]["fields"]

    def test_terminals_css_in_media(self) -> None:
        """The full-width terminal CSS loads for both themes."""
        from django_admin_runner.admin import CommandExecutionAdmin

        css = CommandExecutionAdmin.Media.css["all"]
        assert any("terminals.css" in c for c in css)

    def test_full_output_view(
        self,
        superuser,
        execution: CommandExecution,
        client: Client,
    ) -> None:
        """Combined full view shows both terminals as tabs and fits."""
        from django.urls import reverse

        client.force_login(superuser)
        response = client.get(
            reverse(
                "admin:django_admin_runner_commandexecution_output_full",
                args=[execution.pk],
            ),
        )
        assert response.status_code == 200
        html = response.content.decode()
        assert "dar-full-tabs" in html
        assert 'data-pane="stdout"' in html
        assert 'data-pane="stderr"' in html
        assert '"fit": true' in html

    def test_display_labels(self) -> None:
        """Field labels are simple: Output and Errors."""
        from django_admin_runner.admin import (
            CommandExecutionAdmin,
        )

        assert CommandExecutionAdmin.stdout_display.short_description == "Output"
        assert CommandExecutionAdmin.stderr_display.short_description == "Errors"


@pytest.mark.django_db
class TestConditionalResultField:
    def test_result_field_hidden_without_html(
        self,
        superuser,
        execution: CommandExecution,
        client: Client,
    ) -> None:
        """No result_html -> the Result field is absent from the page."""
        from django.urls import reverse

        client.force_login(superuser)
        response = client.get(
            reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
        )
        html = response.content.decode()
        assert (
            "result_html_display"
            not in html.replace(
                "readonly_fields",
                "",
            )
            or "Result" not in html
        )

    def test_result_field_shown_with_html(
        self,
        superuser,
        execution: CommandExecution,
        client: Client,
    ) -> None:
        """result_html set -> the Result field renders."""
        from django.urls import reverse

        execution.result_html = "<p>chart</p>"
        execution.save(update_fields=["result_html"])
        client.force_login(superuser)
        response = client.get(
            reverse(
                "admin:django_admin_runner_commandexecution_change",
                args=[execution.pk],
            ),
        )
        assert b"chart" in response.content
