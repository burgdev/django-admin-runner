from __future__ import annotations

import importlib
import logging
import pkgutil

logger = logging.getLogger(__name__)

_registry: dict[str, dict] = {}


def register_command(
    name: str | None = None,
    *,
    group: str | None = None,
    permission: str | list[str] = "superuser",
    params: list | None = None,
    exclude_params: list | None = None,
    models: list | None = None,
    widgets: dict | None = None,
    form_class=None,
    display_name: str | None = None,
):
    """
    Decorator to register a management command with the admin runner.

    Args:
        name: Command name. Defaults to the command's module name.
        group: Group label shown in the admin list. Defaults to the app label.
        permission: Who may run this command. ``"superuser"`` (default) restricts
            to superusers only. Pass a Django permission string such as
            ``"myapp.change_mymodel"`` or a list of permission strings (all must
            be held — AND logic). Superusers always bypass permission checks.
        params: Allowlist of argument ``dest`` names to include in the generated
            form. All others are excluded.
        exclude_params: Denylist of argument ``dest`` names to exclude from the
            generated form.
        models: List of Django model classes. A "Run" link for this command will
            appear on each model's admin change-list page when
            ``CommandRunnerModelAdminMixin`` is used.
        widgets: Per-parameter widget or field overrides. Keys are argument
            ``dest`` names; values are either a
            :class:`~django.forms.Widget` instance (swaps the widget on the
            auto-detected field) or a :class:`~django.forms.Field` instance
            (replaces the auto-detected field entirely, e.g.
            ``FileOrPathField()``, ``forms.FileField()``,
            ``forms.ImageField()``).  The ``widget=`` kwarg on ``add_argument``
            takes priority over this dict.  Unfold widget auto-replacement is
            skipped for parameters that have an entry here.
        form_class: A fully custom :class:`~django.forms.Form` class. When set,
            ``form_from_command`` returns it directly — all auto-generation,
            ``params``/``exclude_params`` filtering, and Unfold widget
            replacement are bypassed.
        display_name: Human-readable name for the command. Defaults to the
            command name with underscores replaced by spaces and title-cased
            (e.g., ``"import_books"`` → ``"Import Books"``).
    """

    def decorator(cls):
        cmd_name = name or _module_to_command_name(cls.__module__)
        app_label = _module_to_app_label(cls.__module__)
        _registry[cmd_name] = {
            "name": cmd_name,
            "group": group or app_label,
            "permission": permission,
            "params": params,
            "exclude_params": list(exclude_params or []),
            "models": list(models or []),
            "widgets": dict(widgets or {}),
            "form_class": form_class,
            "command_class": cls,
            "app_label": app_label,
            "display_name": display_name or cmd_name.replace("_", " ").title(),
        }
        return cls

    return decorator


def _module_to_command_name(module: str) -> str:
    """Extract command name from a management command's module path."""
    return module.rsplit(".", 1)[-1]


def _module_to_app_label(module: str) -> str:
    """Extract app label from a management command's module path.

    For ``myapp.management.commands.mycommand`` returns ``"myapp"``.
    For ``myapp.sub.management.commands.mycommand`` returns ``"sub"``.
    """
    parts = module.split(".")
    try:
        mgmt_idx = parts.index("management")
        app_parts = parts[:mgmt_idx]
        return app_parts[-1] if app_parts else parts[0]
    except ValueError:
        return parts[0]


def has_permission(user, entry: dict) -> bool:
    """Return True if *user* is allowed to run the command described by *entry*."""
    if user.is_superuser:
        return True
    perm = entry["permission"]
    if perm == "superuser":
        return False
    perms = [perm] if isinstance(perm, str) else list(perm)
    return all(user.has_perm(p) for p in perms)


def autodiscover_commands() -> None:
    """Import all management command modules to trigger ``@register_command`` decorators."""
    from django.apps import apps as django_apps

    for app_config in django_apps.get_app_configs():
        pkg_path = f"{app_config.name}.management.commands"
        try:
            pkg = importlib.import_module(pkg_path)
        except ImportError:
            continue
        if not hasattr(pkg, "__path__"):
            continue
        for _finder, module_name, is_pkg in pkgutil.iter_modules(pkg.__path__):
            if not is_pkg:
                try:
                    importlib.import_module(f"{pkg_path}.{module_name}")
                except Exception:
                    logger.warning(
                        "django-admin-runner: failed to import %s.%s",
                        pkg_path,
                        module_name,
                        exc_info=True,
                    )

    # Register Celery tasks for all discovered commands (no-op if Celery is not installed).
    from .celery_tasks import _register_celery_tasks

    _register_celery_tasks()
