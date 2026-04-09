import pytest
from django import forms
from django.contrib.admin.widgets import AdminIntegerFieldWidget, AdminTextInputWidget

from django_admin_runner.forms import FileOrPathField, form_from_command
from django_admin_runner.registry import _registry


@pytest.mark.django_db
class TestFormFromCommand:
    # ------------------------------------------------------------------
    # Basic field-type mapping
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Default Django admin widgets (Option A)
    # ------------------------------------------------------------------

    def test_charfield_uses_admin_text_widget(self):
        # hidden_command has --public which is a plain CharField
        FormClass = form_from_command("hidden_command")
        assert isinstance(FormClass().fields["public"].widget, AdminTextInputWidget)

    def test_integerfield_uses_admin_integer_widget(self):
        FormClass = form_from_command("param_command")
        assert isinstance(FormClass().fields["count"].widget, AdminIntegerFieldWidget)

    # ------------------------------------------------------------------
    # Filtering: hidden=, exclude_params, params allowlist
    # ------------------------------------------------------------------

    def test_hidden_true_excludes_field(self):
        FormClass = form_from_command("hidden_command")
        assert "secret" not in FormClass().fields

    def test_public_param_included(self):
        FormClass = form_from_command("hidden_command")
        assert "public" in FormClass().fields

    def test_exclude_params_removes_field(self):
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
        FormClass = form_from_command("simple_command")
        assert len(FormClass().fields) == 0

    def test_form_is_valid_with_defaults(self):
        FormClass = form_from_command("param_command")
        form = FormClass(data={"count": "5", "mode": "slow"})
        assert form.is_valid(), form.errors

    # ------------------------------------------------------------------
    # widget= kwarg in add_argument (Option B — command-level)
    # ------------------------------------------------------------------

    def test_widget_kwarg_widget_instance_swaps_widget(self):
        """widget=Textarea() on add_argument swaps the widget on auto-detected field."""
        FormClass = form_from_command("widget_command")
        field = FormClass().fields["notes"]
        assert isinstance(field, forms.CharField)
        assert isinstance(field.widget, forms.Textarea)

    def test_widget_kwarg_field_instance_replaces_field(self):
        """widget=FileOrPathField() on add_argument replaces the field entirely."""
        FormClass = form_from_command("widget_command")
        field = FormClass().fields["source"]
        assert isinstance(field, FileOrPathField)

    def test_widget_kwarg_plain_param_gets_admin_widget(self):
        """Params without widget= still get the default admin widget."""
        FormClass = form_from_command("widget_command")
        field = FormClass().fields["name"]
        assert isinstance(field.widget, AdminTextInputWidget)

    # ------------------------------------------------------------------
    # widgets dict in register_command decorator (Option B — decorator-level)
    # ------------------------------------------------------------------

    def test_decorator_widgets_dict_swaps_widget(self):
        original = _registry["param_command"].get("widgets")
        _registry["param_command"]["widgets"] = {"count": forms.Textarea()}
        try:
            FormClass = form_from_command("param_command")
            # Field type stays IntegerField, widget is replaced
            field = FormClass().fields["count"]
            assert isinstance(field.widget, forms.Textarea)
        finally:
            _registry["param_command"]["widgets"] = original or {}

    def test_decorator_widgets_dict_field_instance(self):
        original = _registry["param_command"].get("widgets")
        _registry["param_command"]["widgets"] = {"count": FileOrPathField()}
        try:
            FormClass = form_from_command("param_command")
            assert isinstance(FormClass().fields["count"], FileOrPathField)
        finally:
            _registry["param_command"]["widgets"] = original or {}

    # ------------------------------------------------------------------
    # form_class in register_command decorator (Option C)
    # ------------------------------------------------------------------

    def test_form_class_returned_directly(self):
        class MyForm(forms.Form):
            custom_field = forms.CharField()

        original = _registry["param_command"].get("form_class")
        _registry["param_command"]["form_class"] = MyForm
        try:
            FormClass = form_from_command("param_command")
            assert FormClass is MyForm
        finally:
            _registry["param_command"]["form_class"] = original

    # ------------------------------------------------------------------
    # Positional arguments
    # ------------------------------------------------------------------

    def test_positional_argument_included(self):
        FormClass = form_from_command("positional_command")
        assert "filename" in FormClass().fields

    def test_positional_argument_is_required(self):
        FormClass = form_from_command("positional_command")
        assert FormClass().fields["filename"].required is True

    def test_optional_argument_is_not_required(self):
        FormClass = form_from_command("positional_command")
        assert FormClass().fields["count"].required is False

    def test_positional_and_optional_both_included(self):
        FormClass = form_from_command("positional_command")
        assert "filename" in FormClass().fields
        assert "count" in FormClass().fields
