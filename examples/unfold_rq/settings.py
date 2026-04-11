"""
Unfold + Django-RQ example: demonstrates the custom runner interface.

Requires: docker-compose up -d
Then: ./manage.py runserver 8765
And: ./manage.py rqworker
"""

import os

from django.urls import reverse_lazy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "unfold-rq-example-secret-key-change-in-production"
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
    "django_rq",
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

ADMIN_RUNNER_BASE_URL = "http://127.0.0.1:8000"

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

RQ_QUEUES = {
    "default": {
        "HOST": os.environ.get("REDIS_HOST", "localhost"),
        "PORT": 6379,
        "DB": 0,
    }
}

# Use the custom RQ runner defined in runners.py
ADMIN_RUNNER_BACKEND = "runners.RqCommandRunner"

UNFOLD = {
    "SIDEBAR": {
        "navigation": [
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
        ]
    }
}
