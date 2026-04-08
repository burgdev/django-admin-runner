"""Admin customizations for the unfold_celery example.

Registers User, Group, and all Celery Beat models using Unfold's ``ModelAdmin``
so that every model in the admin uses the Unfold theme consistently.

References:
- https://unfoldadmin.com/docs/installation/auth/
- https://unfoldadmin.com/docs/integrations/django-celery-beat/
"""

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django_celery_beat.admin import (
    ClockedScheduleAdmin,
    CrontabScheduleAdmin,
    IntervalScheduleAdmin,
    PeriodicTaskAdmin,
    SolarScheduleAdmin,
)
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)
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


# ---------------------------------------------------------------------------
# Celery Beat — Unfold-styled versions
# ---------------------------------------------------------------------------

for _model in [PeriodicTask, IntervalSchedule, CrontabSchedule, SolarSchedule, ClockedSchedule]:
    admin.site.unregister(_model)


@admin.register(PeriodicTask)
class UnfoldPeriodicTaskAdmin(ModelAdmin, PeriodicTaskAdmin):
    pass


@admin.register(IntervalSchedule)
class UnfoldIntervalScheduleAdmin(ModelAdmin, IntervalScheduleAdmin):
    pass


@admin.register(CrontabSchedule)
class UnfoldCrontabScheduleAdmin(ModelAdmin, CrontabScheduleAdmin):
    pass


@admin.register(SolarSchedule)
class UnfoldSolarScheduleAdmin(ModelAdmin, SolarScheduleAdmin):
    pass


@admin.register(ClockedSchedule)
class UnfoldClockedScheduleAdmin(ModelAdmin, ClockedScheduleAdmin):
    pass
