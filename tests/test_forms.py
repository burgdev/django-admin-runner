import pytest
from django import forms

from django_admin_runner.forms import form_from_command
from django_admin_runner.registry import _registry


@pytest.mark.django_db
class TestFormFromCommand:
    def test_store_true_becomes_boolean(self):
        FormClass = form_from_command("param_command")
        assert isinstance(FormClass().fields["verbose"], forms.BooleanField)

    def test_int_type_becomes_integer(self):
        FormClass = form_from_command("param_command")
        assert isinstance(FormClass().fields["count"], forms.IntegerField)

    def test_choices_become_choice_field(self):
        FormClass = form_from_command("param_command")
        assert isinstance(FormClass().fields["mode"], forms.ChoiceField)

    def test_choice_field_options(self):
        FormClass = form_from_command("param_command")
        field = FormClass().fields["mode"]
        choice_values = [v for v, _ in field.choices]
        assert "fast" in choice_values
        assert "slow" in choice_values

    def test_default_sets_initial(self):
        FormClass = form_from_command("param_command")
        assert FormClass().fields["count"].initial == 1

    def test_help_text(self):
        FormClass = form_from_command("param_command")
        assert "Number of iterations" in FormClass().fields["count"].help_text

    def test_hidden_true_excludes_field(self):
        FormClass = form_from_command("hidden_command")
        assert "secret" not in FormClass().fields

    def test_public_param_included(self):
        FormClass = form_from_command("hidden_command")
        assert "public" in FormClass().fields

    def test_exclude_params_removes_field(self):
        # hidden_command is registered with exclude_params=["internal"]
        FormClass = form_from_command("hidden_command")
        assert "internal" not in FormClass().fields

    def test_default_django_params_excluded(self):
        FormClass = form_from_command("simple_command")
        excluded = {
            "verbosity",
            "traceback",
            "settings",
            "pythonpath",
            "no_color",
            "force_color",
            "skip_checks",
            "version",
        }
        for param in excluded:
            assert param not in FormClass().fields, f"{param} should be excluded"

    def test_params_allowlist(self):
        # Temporarily set params allowlist on param_command
        original = _registry["param_command"]["params"]
        _registry["param_command"]["params"] = ["count"]
        try:
            FormClass = form_from_command("param_command")
            assert "count" in FormClass().fields
            assert "mode" not in FormClass().fields
            assert "verbose" not in FormClass().fields
        finally:
            _registry["param_command"]["params"] = original

    def test_no_params_allowlist_includes_all(self):
        _registry["param_command"]["params"] = None
        FormClass = form_from_command("param_command")
        assert "count" in FormClass().fields
        assert "mode" in FormClass().fields
        assert "verbose" in FormClass().fields

    def test_simple_command_no_fields(self):
        # simple_command has no custom arguments → empty form
        FormClass = form_from_command("simple_command")
        assert len(FormClass().fields) == 0

    def test_form_is_valid_with_defaults(self):
        FormClass = form_from_command("param_command")
        form = FormClass(data={"count": "5", "mode": "slow"})
        assert form.is_valid(), form.errors
