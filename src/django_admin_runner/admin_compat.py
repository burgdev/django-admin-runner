from __future__ import annotations


def is_unfold_installed() -> bool:
    """Return True if django-unfold is in INSTALLED_APPS."""
    from django.conf import settings

    return "unfold" in getattr(settings, "INSTALLED_APPS", [])


def get_model_admin_base():
    """Return the appropriate ModelAdmin base class."""
    if is_unfold_installed():
        from unfold.admin import ModelAdmin

        return ModelAdmin
    from django.contrib.admin import ModelAdmin

    return ModelAdmin


def get_template(name: str) -> str:
    """Return the template path for *name* (``"list"`` or ``"run"``)."""
    if is_unfold_installed():
        return f"django_admin_runner/unfold/{name}.html"
    return f"django_admin_runner/base/{name}.html"
