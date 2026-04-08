from __future__ import annotations

import argparse
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
        action.hidden = hidden
        return action

    argparse._ActionsContainer.add_argument = patched  # noqa: SLF001
    try:
        yield
    finally:
        argparse._ActionsContainer.add_argument = original  # noqa: SLF001


def form_from_command(command_name: str) -> type[forms.Form]:
    """Build a Django ``Form`` class by introspecting *command_name*'s argparse parser.

    Filtering rules (applied in order):
    1. Default Django management params are always excluded.
    2. Arguments with ``hidden=True`` (custom attr) are excluded.
    3. ``exclude_params`` from the registry entry are excluded.
    4. If ``params`` allowlist is set, only those ``dest`` names are kept.
    """
    from django.core.management import get_commands, load_command_class

    from .registry import _registry

    entry = _registry.get(command_name, {})
    params_allowlist = entry.get("params")
    exclude_set = set(entry.get("exclude_params") or [])

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

        field = _action_to_field(action)
        if field is not None:
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
