"""Admin customizations for the unfold_rq example.

Registers User and Group using Unfold's ``ModelAdmin`` so that all
admin models use the Unfold theme consistently.

Reference: https://unfoldadmin.com/docs/installation/auth/
"""

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

# ---------------------------------------------------------------------------
# User & Group — Unfold-styled versions
# ---------------------------------------------------------------------------

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class CustomUserAdmin(ModelAdmin, UserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class CustomGroupAdmin(ModelAdmin, GroupAdmin):
    pass
