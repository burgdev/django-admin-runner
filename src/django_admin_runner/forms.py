from __future__ import annotations

import argparse
import os
import tempfile
import uuid
from contextlib import contextmanager

from django import forms
from django.core.exceptions import ValidationError

_DEFAULT_EXCLUDED = frozenset(
    {
        "verbosity",
        "traceback",
        "settings",
        "pythonpath",
        "no-color",
        "no_color",
        "force-color",
        "force_color",
        "skip-checks",
        "skip_checks",
        "version",
    }
)


@contextmanager
def _hidden_aware_argparse():
    """Temporarily patch argparse so ``hidden=True`` and ``widget=...`` can be
    passed to ``add_argument``.

    Both kwargs are stripped before argparse sees them and stored as attributes
    on the returned ``Action`` object, where ``form_from_command`` reads them.

    - ``hidden=True`` — exclude this argument from the generated form entirely.
    - ``widget=<Field or Widget instance>`` — override the auto-detected field or
      widget for this argument (see :func:`form_from_command` for priority rules).
    """
    original = argparse._ActionsContainer.add_argument  # noqa: SLF001

    def patched(self, *args, **kwargs):
        hidden = kwargs.pop("hidden", False)
        widget = kwargs.pop("widget", None)
        action = original(self, *args, **kwargs)
        setattr(action, "hidden", hidden)
        setattr(action, "widget", widget)
        return action

    argparse._ActionsContainer.add_argument = patched  # noqa: SLF001
    try:
        yield
    finally:
        argparse._ActionsContainer.add_argument = original  # noqa: SLF001


# ---------------------------------------------------------------------------
# Convenience re-exports (Django built-in file fields)
# ---------------------------------------------------------------------------

#: File-upload-only field. Equivalent to :class:`django.forms.FileField`.
FileField = forms.FileField
#: Image-upload-only field (requires Pillow). Equivalent to :class:`django.forms.ImageField`.
ImageField = forms.ImageField


# ---------------------------------------------------------------------------
# File-or-path combined widget / field
# ---------------------------------------------------------------------------


class FileOrPathWidget(forms.MultiWidget):
    """Renders a file-upload input and a text-path input side by side.

    The user can either upload a file *or* type a path on the server.
    When ``ADMIN_RUNNER_UPLOAD_PATH`` is not set, the file input is hidden
    and only the text path input is shown.
    """

    template_name = "django_admin_runner/widgets/file_or_path.html"

    def __init__(self, attrs=None):
        super().__init__([forms.FileInput(), forms.TextInput()], attrs)

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        from django.conf import settings

        ctx["upload_enabled"] = bool(getattr(settings, "ADMIN_RUNNER_UPLOAD_PATH", ""))  # type: ignore[assignment]
        return ctx

    def decompress(self, value):
        # value is an existing path string (initial/default); show it in the text field
        return [None, value or ""]


class FileOrPathField(forms.MultiValueField):
    """Form field that accepts either an uploaded file or a typed server-side path.

    If a file is uploaded it is saved to a temporary directory and the path
    to that temp file is returned as the cleaned value (a plain ``str``).
    If only a path string is typed that string is returned directly.

    Typical usage in ``add_arguments``::

        from django_admin_runner import FileOrPathField

        parser.add_argument("--source", widget=FileOrPathField(), help="CSV path or upload")
    """

    widget = FileOrPathWidget

    def __init__(self, **kwargs):
        fields = [
            forms.FileField(required=False),
            forms.CharField(required=False),
        ]
        kwargs.setdefault("required", False)
        super().__init__(fields, **kwargs)

    def compress(self, data_list):
        uploaded_file = data_list[0] if data_list else None
        typed_path = data_list[1] if len(data_list) > 1 else ""

        if uploaded_file:
            from django.conf import settings

            upload_path = getattr(settings, "ADMIN_RUNNER_UPLOAD_PATH", "")
            if upload_path:
                tmp_dir = os.path.join(upload_path.rstrip("/"), f"upload_{uuid.uuid4().hex[:12]}")
                os.makedirs(tmp_dir, exist_ok=True)
            else:
                tmp_dir = tempfile.mkdtemp(prefix="django_admin_runner_")
            dest_path = os.path.join(tmp_dir, uploaded_file.name)
            with open(dest_path, "wb") as fh:
                for chunk in uploaded_file.chunks():
                    fh.write(chunk)
            return dest_path

        return typed_path or ""


# ---------------------------------------------------------------------------
# Unfold widget helpers
# ---------------------------------------------------------------------------


def _apply_unfold_widget(field: forms.Field) -> None:
    """Replace *field*'s widget with the Unfold-styled equivalent.

    No-ops silently when ``unfold`` is not in ``INSTALLED_APPS`` or not installed.
    Only called for auto-detected fields — user-specified widgets are never replaced.
    """
    from .admin_compat import is_unfold_installed

    if not is_unfold_installed():
        return

    try:
        from unfold.widgets import (
            UnfoldAdminIntegerFieldWidget,
            UnfoldAdminSelectWidget,
            UnfoldAdminTextInputWidget,
            UnfoldBooleanWidget,
        )
    except ImportError:
        return

    if isinstance(field, FileOrPathField):
        # Replace the text sub-widget (index 1) with the Unfold-styled version
        # and switch to the Unfold template.
        field.widget.widgets[1] = UnfoldAdminTextInputWidget()
        field.widget.template_name = "django_admin_runner/widgets/file_or_path_unfold.html"
    elif isinstance(field, forms.BooleanField):
        field.widget = UnfoldBooleanWidget()
    elif isinstance(field, forms.ChoiceField):
        field.widget = UnfoldAdminSelectWidget()
        # Re-sync choices from field to widget: replacing the widget above
        # creates a fresh instance with choices=[], so we must push the
        # field's choices back down via the setter.
        field.choices = field.choices  # type: ignore[assignment]
    elif isinstance(field, forms.IntegerField):
        field.widget = UnfoldAdminIntegerFieldWidget()
    elif isinstance(field, forms.CharField):
        field.widget = UnfoldAdminTextInputWidget()


# ---------------------------------------------------------------------------
# Dynamic form builder
# ---------------------------------------------------------------------------


def form_from_command(command_name: str) -> type[forms.Form]:
    """Build a Django ``Form`` class by introspecting *command_name*'s argparse parser.

    Both optional (``--flag``) and positional arguments are included; positional
    arguments preserve the ``required=True`` constraint from argparse.

    Filtering rules (applied in order):

    1. Default Django management params are always excluded.
    2. Arguments with ``hidden=True`` (custom kwarg on ``add_argument``) are excluded.
    3. ``exclude_params`` from the registry entry are excluded.
    4. If ``params`` allowlist is set, only those ``dest`` names are kept.

    Widget / field override priority (highest wins):

    1. ``widget=<instance>`` kwarg on ``add_argument()`` — specified in the command
       itself, closest to the argument definition.
    2. ``widgets`` dict from the ``register_command`` decorator.
    3. Auto-detected from the argparse action type (uses Django admin widgets as
       the base so the form blends with the rest of the admin interface).

    If the value at priority 1 or 2 is a :class:`~django.forms.Field` instance it
    replaces the auto-detected field entirely (widget + validation).  If it is a
    :class:`~django.forms.Widget` instance the auto-detected field is kept but its
    widget is swapped.

    User-specified widgets (priorities 1 and 2) are **never** overridden by the
    Unfold auto-replacement.  Auto-detected fields (priority 3) receive Unfold
    widgets when Unfold is installed.

    If the registry entry has ``form_class`` set, it is returned directly —
    no auto-generation, no Unfold replacement.
    """
    from django.core.management import get_commands, load_command_class

    from .registry import _registry

    entry = _registry.get(command_name, {})

    # Option C: custom form class — skip all auto-generation
    if form_class := entry.get("form_class"):
        return form_class  # type: ignore[return-value]

    params_allowlist = entry.get("params")
    exclude_set = set(entry.get("exclude_params") or [])
    widgets_override: dict = entry.get("widgets") or {}

    app_name = get_commands().get(command_name, "django.core")

    with _hidden_aware_argparse():
        cmd = load_command_class(app_name, command_name)
        parser = cmd.create_parser("manage.py", command_name)

    fields: dict[str, forms.Field] = {}
    for action in parser._actions:  # noqa: SLF001
        dest = action.dest

        if dest in _DEFAULT_EXCLUDED:
            continue
        if isinstance(action, argparse._HelpAction | argparse._SubParsersAction):  # noqa: SLF001
            continue
        if getattr(action, "hidden", False):
            continue
        if dest in exclude_set:
            continue
        if params_allowlist is not None and dest not in params_allowlist:
            continue

        # Priority: action-level widget > decorator-level widget > auto-detect
        override = getattr(action, "widget", None) or widgets_override.get(dest)
        user_specified = override is not None

        if user_specified:
            if isinstance(override, forms.Field):
                # Full field replacement (e.g. FileOrPathField, FileField, ImageField)
                field: forms.Field | None = override
            else:
                # Widget instance — auto-detect the field, then swap its widget
                field = _action_to_field(action)
                if field is not None:
                    field.widget = override
        else:
            field = _action_to_field(action)

        if field is not None:
            if not user_specified or isinstance(field, FileOrPathField):
                _apply_unfold_widget(field)
            fields[dest] = field

    return type("CommandForm", (forms.Form,), fields)


class _TypedCharField(forms.CharField):
    """``CharField`` that coerces the cleaned string through an argparse ``type`` callable.

    Used when ``action.type`` is a callable that is not covered by a dedicated
    Django field (e.g. ``decimal.Decimal``, ``pathlib.Path``, custom lambdas).
    """

    def __init__(self, type_callable, **kwargs):
        super().__init__(**kwargs)
        self._type_callable = type_callable

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        try:
            return self._type_callable(value)
        except (ValueError, TypeError, argparse.ArgumentTypeError) as exc:
            raise ValidationError(str(exc) or "Enter a valid value.", code="invalid") from exc


def _action_to_field(action: argparse.Action) -> forms.Field | None:
    """Map an argparse *action* to the appropriate Django form field.

    Django admin widgets (``AdminTextInputWidget``, ``AdminIntegerFieldWidget``)
    are used by default so the run form blends with the rest of the admin
    interface.  Unfold widgets are applied on top via ``_apply_unfold_widget``
    when Unfold is installed.

    Positional arguments (``action.required is True``) produce ``required=True``
    form fields; optional arguments produce ``required=False`` fields.
    """
    from django.contrib.admin import widgets as admin_widgets

    help_text = action.help or ""
    # Strip argparse suppress sentinel
    if help_text == argparse.SUPPRESS:
        help_text = ""

    is_required = bool(getattr(action, "required", False))
    base_kwargs: dict = {"required": is_required, "help_text": help_text}
    if action.default not in (None, argparse.SUPPRESS):
        base_kwargs["initial"] = action.default

    if isinstance(action, argparse._StoreTrueAction | argparse._StoreFalseAction):  # noqa: SLF001
        return forms.BooleanField(required=False, help_text=help_text)

    if action.choices:
        choices = [(str(c), str(c)) for c in action.choices]
        return forms.ChoiceField(choices=choices, **base_kwargs)

    if action.type is int:
        field = forms.IntegerField(**base_kwargs)
        field.widget = admin_widgets.AdminIntegerFieldWidget()
        return field

    if action.type is float:
        return forms.FloatField(**base_kwargs)

    if callable(action.type):
        return _TypedCharField(action.type, **base_kwargs)

    field = forms.CharField(**base_kwargs)
    field.widget = admin_widgets.AdminTextInputWidget()
    return field
