"""
Unfold + Celery example: full production async setup.

Requires: docker-compose up -d
Then: ./manage.py runserver 8765
And: celery -A celery_app worker -l info
"""

import os

from django.urls import reverse_lazy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "unfold-celery-example-secret-key-change-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "django_celery_results",
    "django_admin_runner",
    "books",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True

ADMIN_RUNNER_BACKEND = "celery"
ADMIN_RUNNER_UPLOAD_PATH = os.path.join(BASE_DIR, "uploads")

UNFOLD = {
    "SIDEBAR": {
        "navigation": [
            {
                "title": "Models",
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": "Books",
                        "icon": "book",
                        "link": reverse_lazy("admin:books_book_changelist"),
                    },
                ],
            },
            {
                "title": "Command Runner",
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": "Run Commands",
                        "icon": "terminal",
                        "link": reverse_lazy("admin:django_admin_runner_command_list"),
                        "permission": lambda request: request.user.is_staff,
                    },
                    {
                        "title": "Command executions",
                        "icon": "history",
                        "link": reverse_lazy(
                            "admin:django_admin_runner_commandexecution_changelist"
                        ),
                        "permission": lambda request: request.user.is_staff,
                    },
                ],
            },
            {
                "title": "Authentication",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
            {
                "title": "Celery Tasks",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Periodic tasks",
                        "icon": "task",
                        "link": reverse_lazy("admin:django_celery_beat_periodictask_changelist"),
                    },
                    {
                        "title": "Intervals",
                        "icon": "timer",
                        "link": reverse_lazy(
                            "admin:django_celery_beat_intervalschedule_changelist"
                        ),
                    },
                    {
                        "title": "Crontabs",
                        "icon": "update",
                        "link": reverse_lazy("admin:django_celery_beat_crontabschedule_changelist"),
                    },
                    {
                        "title": "Solar events",
                        "icon": "event",
                        "link": reverse_lazy("admin:django_celery_beat_solarschedule_changelist"),
                    },
                    {
                        "title": "Clocked",
                        "icon": "hourglass_bottom",
                        "link": reverse_lazy("admin:django_celery_beat_clockedschedule_changelist"),
                    },
                ],
            },
            {
                "title": "Celery Results",
                "separator": False,
                "collapsible": True,
                "items": [
                    {
                        "title": "Task results",
                        "icon": "checklist_rtl",
                        "link": reverse_lazy("admin:django_celery_results_taskresult_changelist"),
                    },
                    {
                        "title": "Group results",
                        "icon": "playlist_add_check",
                        "link": reverse_lazy("admin:django_celery_results_groupresult_changelist"),
                    },
                ],
            },
        ]
    }
}
