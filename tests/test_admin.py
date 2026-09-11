import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from django_admin_runner.models import CommandExecution

User = get_user_model()


# ---------------------------------------------------------------------------
# Run view — GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommandRunViewGet:
    def test_run_view_ok(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        response = admin_client.get(url)
        assert response.status_code == 200

    def test_run_view_has_form_in_context(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        response = admin_client.get(url)
        assert "form" in response.context

    def test_run_view_form_has_correct_fields(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        response = admin_client.get(url)
        form = response.context["form"]
        assert "count" in form.fields
        assert "mode" in form.fields
        assert "verbose" in form.fields

    def test_run_view_404_for_unknown_command(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["nonexistent_command"])
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_run_view_403_without_permission(self, staff_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        response = staff_client.get(url)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Run view — POST
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommandRunViewPost:
    def test_valid_post_creates_execution(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        admin_client.post(url, {})
        assert CommandExecution.objects.filter(command_name="simple_command").exists()

    def test_valid_post_redirects(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        response = admin_client.post(url, {})
        assert response.status_code == 302

    def test_valid_post_execution_sets_triggered_by(self, admin_client, superuser):
        url = reverse("admin:django_admin_runner_command_run", args=["simple_command"])
        admin_client.post(url, {})
        ex = CommandExecution.objects.filter(command_name="simple_command").first()
        assert ex.triggered_by == superuser

    def test_valid_post_with_params(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        admin_client.post(url, {"count": "3", "mode": "slow"})
        ex = CommandExecution.objects.filter(command_name="param_command").first()
        assert ex is not None

    def test_invalid_post_rerenders_form(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        # Pass an invalid integer for count
        response = admin_client.post(url, {"count": "not-a-number", "mode": "slow"})
        assert response.status_code == 200
        assert "form" in response.context
        assert response.context["form"].errors


# ---------------------------------------------------------------------------
# CommandExecutionAdmin queryset filtering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommandExecutionAdminQueryset:
    def test_superuser_sees_all_executions(self, admin_client, db):
        u1 = User.objects.create_user("u1", "u1@e.com", "pw")
        CommandExecution.objects.create(command_name="cmd", triggered_by=u1)
        CommandExecution.objects.create(command_name="cmd2", triggered_by=None)

        url = reverse("admin:django_admin_runner_commandexecution_changelist")
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.context["cl"].queryset.count() == 2

    def test_regular_user_sees_own_executions_only(self, client, db):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        user = User.objects.create_user("limited", "l@e.com", "pw", is_staff=True)
        other = User.objects.create_user("other", "o@e.com", "pw")

        # Staff user needs at least view permission to access the changelist
        ct = ContentType.objects.get_for_model(CommandExecution)
        perm = Permission.objects.get(content_type=ct, codename="view_commandexecution")
        user.user_permissions.add(perm)

        CommandExecution.objects.create(command_name="mine", triggered_by=user)
        CommandExecution.objects.create(command_name="theirs", triggered_by=other)

        client.force_login(user)
        url = reverse("admin:django_admin_runner_commandexecution_changelist")
        response = client.get(url)
        assert response.status_code == 200
        qs = response.context["cl"].queryset
        assert qs.count() == 1
        assert qs.first().command_name == "mine"


# ---------------------------------------------------------------------------
# Result view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestResultView:
    def test_result_view_with_result_html(self, admin_client, superuser):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            triggered_by=superuser,
            status="SUCCESS",
            result_html="<h1>Report</h1><p>Done</p>",
        )
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[execution.pk])
        response = admin_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "<h1>Report</h1>" in content

    def test_result_view_without_result_html_shows_stdout(self, admin_client, superuser):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            triggered_by=superuser,
            status="SUCCESS",
        )
        from django_admin_runner.tasks import _append_output

        _append_output(execution, "stdout", "Hello world output")
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[execution.pk])
        response = admin_client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        # stdout is rendered by the terminal widget, replayed from the delta
        # endpoint rather than embedded in the HTML
        assert 'data-dar-field="stdout"' in content
        output_url = reverse(
            "admin:django_admin_runner_commandexecution_output", args=[execution.pk]
        )
        assert output_url in content

    def test_result_view_404_for_invalid_pk(self, admin_client):
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[99999])
        response = admin_client.get(url)
        assert response.status_code == 404

    def test_result_view_permission_denied_for_other_user(self, client, db):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        user = User.objects.create_user("limited", "l@e.com", "pw", is_staff=True)
        other = User.objects.create_superuser("admin2", "a2@e.com", "pw")
        ct = ContentType.objects.get_for_model(CommandExecution)
        perm = Permission.objects.get(content_type=ct, codename="view_commandexecution")
        user.user_permissions.add(perm)

        execution = CommandExecution.objects.create(
            command_name="cmd",
            triggered_by=other,
            result_html="<p>Secret</p>",
        )

        client.force_login(user)
        url = reverse("admin:django_admin_runner_commandexecution_result", args=[execution.pk])
        response = client.get(url)
        assert response.status_code == 404  # get_queryset filters it out


# ---------------------------------------------------------------------------
# Rerun: prefilled run form from a past execution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRerunPrefill:
    def _execution(self, **kwargs):
        return CommandExecution.objects.create(
            command_name="param_command",
            kwargs=kwargs,
        )

    def _run_url(self, execution):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        return f"{url}?rerun={execution.pk}"

    def test_prefills_stored_kwargs(self, admin_client):
        execution = self._execution(count=5, mode="slow", verbose=True)
        response = admin_client.get(self._run_url(execution))
        assert response.status_code == 200
        initial = response.context["form"].initial
        assert initial["count"] == 5
        assert initial["mode"] == "slow"
        assert initial["verbose"] is True

    def test_string_value_split_for_multiple_choice(self, admin_client):
        execution = self._execution(tag="alpha, beta")
        response = admin_client.get(self._run_url(execution))
        assert response.context["form"].initial["tag"] == ["alpha", "beta"]

    def test_list_value_kept_for_multiple_choice(self, admin_client):
        execution = self._execution(tag=["alpha", "gamma"])
        response = admin_client.get(self._run_url(execution))
        assert response.context["form"].initial["tag"] == ["alpha", "gamma"]

    def test_stale_kwargs_keys_dropped(self, admin_client):
        execution = self._execution(count=2, removed_arg="x")
        response = admin_client.get(self._run_url(execution))
        initial = response.context["form"].initial
        assert initial["count"] == 2
        assert "removed_arg" not in initial

    def test_missing_rerun_pk_empty_form(self, admin_client):
        url = reverse("admin:django_admin_runner_command_run", args=["param_command"])
        response = admin_client.get(url + "?rerun=99999")
        assert response.context["form"].initial == {}

    def test_rerun_of_other_command_not_prefilled(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            kwargs={"anything": 1},
        )
        response = admin_client.get(self._run_url(execution))
        assert response.context["form"].initial == {}

    def test_rerun_of_inaccessible_execution_empty(self, client, db):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        user = User.objects.create_user("limited", "l@e.com", "pw", is_staff=True)
        other = User.objects.create_user("someone", "s@e.com", "pw")
        ct = ContentType.objects.get_for_model(CommandExecution)
        perm = Permission.objects.get(content_type=ct, codename="view_commandexecution")
        user.user_permissions.add(perm)
        client.force_login(user)

        execution = CommandExecution.objects.create(
            command_name="param_command",
            kwargs={"count": 9},
            triggered_by=other,
        )
        response = client.get(self._run_url(execution))
        assert response.status_code in (200, 403)
        if response.status_code == 200:
            assert response.context["form"].initial == {}


# ---------------------------------------------------------------------------
# Rerun: change page button and hidden Save
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRerunChangePage:
    def _change_url(self, execution):
        return reverse("admin:django_admin_runner_commandexecution_change", args=[execution.pk])

    def test_save_buttons_hidden(self, admin_client):
        execution = CommandExecution.objects.create(command_name="simple_command")
        response = admin_client.get(self._change_url(execution))
        assert response.context["show_save"] is False
        assert response.context["show_save_and_continue"] is False

    def test_rerun_url_in_context_for_registered_command(self, admin_client):
        execution = CommandExecution.objects.create(command_name="simple_command")
        response = admin_client.get(self._change_url(execution))
        assert f"rerun={execution.pk}" in response.context["dar_rerun_url"]

    def test_no_rerun_url_for_unregistered_command(self, admin_client):
        execution = CommandExecution.objects.create(command_name="nonexistent_command")
        response = admin_client.get(self._change_url(execution))
        assert response.context["dar_rerun_url"] is None

    def test_no_rerun_link_rendered_for_unregistered_command(self, admin_client):
        execution = CommandExecution.objects.create(command_name="nonexistent_command")
        response = admin_client.get(self._change_url(execution))
        assert "Rerun" not in response.rendered_content

    def test_rerun_link_rendered_for_registered_command(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            status=CommandExecution.Status.SUCCESS,
        )
        response = admin_client.get(self._change_url(execution))
        assert f"rerun={execution.pk}" in response.rendered_content

    def test_rerun_disabled_while_executing(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            status=CommandExecution.Status.RUNNING,
        )
        response = admin_client.get(self._change_url(execution))
        assert response.context["dar_rerun_running"] is True
        assert 'aria-disabled="true"' in response.rendered_content

    def test_rerun_enabled_when_finished(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            status=CommandExecution.Status.SUCCESS,
        )
        response = admin_client.get(self._change_url(execution))
        assert response.context["dar_rerun_running"] is False
        assert 'aria-disabled="true"' not in response.rendered_content


# ---------------------------------------------------------------------------
# Status badges
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStatusBadge:
    def _change_url(self, execution):
        return reverse("admin:django_admin_runner_commandexecution_change", args=[execution.pk])

    def test_changelist_renders_badges(self, admin_client):
        CommandExecution.objects.create(
            command_name="simple_command", status=CommandExecution.Status.RUNNING
        )
        CommandExecution.objects.create(
            command_name="simple_command", status=CommandExecution.Status.SUCCESS
        )
        url = reverse("admin:django_admin_runner_commandexecution_changelist")
        response = admin_client.get(url)
        content = response.rendered_content
        assert "dar-spin" in content  # running spinner
        assert "#16a34a" in content  # success green

    def test_change_page_running_shows_spinner(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command", status=CommandExecution.Status.RUNNING
        )
        response = admin_client.get(self._change_url(execution))
        assert "dar-spin" in response.rendered_content

    def test_change_page_failed_shows_cross(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command", status=CommandExecution.Status.FAILED
        )
        response = admin_client.get(self._change_url(execution))
        content = response.rendered_content
        assert "#dc2626" in content
        assert "M18 6 6 18M6 6l12 12" in content  # cross icon path

    def test_success_shows_check(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command", status=CommandExecution.Status.SUCCESS
        )
        response = admin_client.get(self._change_url(execution))
        assert "M20 6 9 17l-5-5" in response.rendered_content  # check icon path

    def test_badge_carries_data_status_for_live_updates(self, admin_client):
        execution = CommandExecution.objects.create(
            command_name="simple_command",
            status=CommandExecution.Status.RUNNING,
        )
        response = admin_client.get(self._change_url(execution))
        content = response.rendered_content
        assert 'id="dar-status-badge"' in content
        assert 'data-status="RUNNING"' in content
