from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import Book

# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = ["title", "author", "published_date", "isbn"]
    search_fields = ["title", "author", "isbn"]


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
