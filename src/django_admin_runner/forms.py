from __future__ import annotations

import argparse
import os
import tempfile
from contextlib import contextmanager

from django import forms

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
    """Temporarily patch argparse so ``hidden=True`` can be passed to ``add_argument``.

    The ``hidden`` kwarg is stripped before argparse sees it and stored as an
    attribute on the returned ``Action`` object, where ``form_from_command``
    reads it.
    """
    original = argparse._ActionsContainer.add_argument  # noqa: SLF001

    def patched(self, *args, **kwargs):
        hidden = kwargs.pop("hidden", False)
        action = original(self, *args, **kwargs)
        setattr(action, "hidden", hidden)
        return action

    argparse._ActionsContainer.add_argument = patched  # noqa: SLF001
    try:
        yield
    finally:
        argparse._ActionsContainer.add_argument = original  # noqa: SLF001


# ---------------------------------------------------------------------------
# File-or-path combined widget / field
# ---------------------------------------------------------------------------


class FileOrPathWidget(forms.MultiWidget):
    """Renders a file-upload input and a text-path input side by side.

    The user can either upload a file *or* type a path on the server.
    """

    template_name = "django_admin_runner/widgets/file_or_path.html"

    def __init__(self, attrs=None):
        super().__init__([forms.FileInput(), forms.TextInput()], attrs)

    def decompress(self, value):
        # value is an existing path string (initial/default); show it in the text field
        return [None, value or ""]


class FileOrPathField(forms.MultiValueField):
    """Form field that accepts either an uploaded file or a typed server-side path.

    If a file is uploaded it is saved to a temporary directory and the path
    to that temp file is returned as the cleaned value (a plain ``str``).
    If only a path string is typed that string is returned directly.
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
        # Replace the text sub-widget (index 1) with the Unfold-styled version.
        field.widget.widgets[1] = UnfoldAdminTextInputWidget()
    elif isinstance(field, forms.BooleanField):
        field.widget = UnfoldBooleanWidget()
    elif isinstance(field, forms.ChoiceField):
        field.widget = UnfoldAdminSelectWidget()
    elif isinstance(field, forms.IntegerField):
        field.widget = UnfoldAdminIntegerFieldWidget()
    elif isinstance(field, forms.CharField):
        field.widget = UnfoldAdminTextInputWidget()


# ---------------------------------------------------------------------------
# Dynamic form builder
# ---------------------------------------------------------------------------


def form_from_command(command_name: str) -> type[forms.Form]:
    """Build a Django ``Form`` class by introspecting *command_name*'s argparse parser.

    Filtering rules (applied in order):
    1. Default Django management params are always excluded.
    2. Arguments with ``hidden=True`` (custom attr) are excluded.
    3. ``exclude_params`` from the registry entry are excluded.
    4. If ``params`` allowlist is set, only those ``dest`` names are kept.

    ``file_params`` entries are rendered as :class:`FileOrPathField` (file
    upload + text path) instead of a plain ``CharField``.

    When ``unfold`` is installed, Unfold-styled widgets are applied automatically.
    """
    from django.core.management import get_commands, load_command_class

    from .registry import _registry

    entry = _registry.get(command_name, {})
    params_allowlist = entry.get("params")
    exclude_set = set(entry.get("exclude_params") or [])
    file_params_set = set(entry.get("file_params") or [])

    app_name = get_commands().get(command_name, "django.core")

    with _hidden_aware_argparse():
        cmd = load_command_class(app_name, command_name)
        parser = cmd.create_parser("manage.py", command_name)

    fields: dict[str, forms.Field] = {}
    for action in parser._actions:  # noqa: SLF001
        dest = action.dest

        if dest in _DEFAULT_EXCLUDED:
            continue
        if isinstance(action, argparse._HelpAction):  # noqa: SLF001
            continue
        if getattr(action, "hidden", False):
            continue
        if dest in exclude_set:
            continue
        if params_allowlist is not None and dest not in params_allowlist:
            continue

        if dest in file_params_set:
            help_text = action.help or ""
            if help_text == argparse.SUPPRESS:
                help_text = ""
            field: forms.Field = FileOrPathField(required=False, help_text=help_text)
            if action.default not in (None, argparse.SUPPRESS):
                field.initial = action.default
        else:
            field = _action_to_field(action)  # type: ignore[assignment]

        if field is not None:
            _apply_unfold_widget(field)
            fields[dest] = field

    return type("CommandForm", (forms.Form,), fields)


def _action_to_field(action: argparse.Action) -> forms.Field | None:
    """Map an argparse *action* to the appropriate Django form field."""
    help_text = action.help or ""
    # Strip argparse suppress sentinel
    if help_text == argparse.SUPPRESS:
        help_text = ""

    base_kwargs: dict = {"required": False, "help_text": help_text}
    if action.default not in (None, argparse.SUPPRESS):
        base_kwargs["initial"] = action.default

    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):  # noqa: SLF001
        return forms.BooleanField(required=False, help_text=help_text)

    if action.choices:
        choices = [(str(c), str(c)) for c in action.choices]
        return forms.ChoiceField(choices=choices, **base_kwargs)

    if action.type is int:
        return forms.IntegerField(**base_kwargs)

    return forms.CharField(**base_kwargs)
