"""
Unfold + Django-Q2 example: async execution with zero external services.

No Docker, no Redis — uses Django ORM as the message broker.
"""

import os

from django.urls import reverse, reverse_lazy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "unfold-django-q2-example-secret-key-change-in-production"
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
    "django_q",
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

# Django-Q2 — ORM broker (no external services)
Q_CLUSTER = {
    "name": "DJANGORM",
    "orm": "default",
    # retry must exceed timeout, or q2 re-delivers tasks before they
    # finish (and re-runs commands).
    "retry": 7200,
    # django-q2 SIGKILLs workers whose task exceeds this limit — the task
    # row then needs a Force Stop to be finalized. Keep it well above the
    # longest command you run (simulate_workload defaults to 5 min).
    "timeout": 3600,
}

ADMIN_RUNNER_BACKEND = "django-q2"

# Terminal layout height for command output (exported as LINES, rich lays
# out for this): 50 fits the workload simulator's 20 progress bars. The
# embedded widget height is separate (ADMIN_RUNNER_TERM_VIEW_ROWS, default 20).
ADMIN_RUNNER_TERM_ROWS = 50

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
                        "title": "Commands",
                        "icon": "terminal",
                        "link": reverse_lazy(
                            "admin:django_admin_runner_registeredcommand_changelist"
                        ),
                        # Exact match: Unfold's default active detection is
                        # substring-based, which would also light up this
                        # entry on the pinned group views below.
                        "active": lambda request: request.path
                        == reverse("admin:django_admin_runner_registeredcommand_changelist"),
                        "permission": lambda request: request.user.is_staff,
                    },
                    {
                        # Commands changelist pinned to one group, on its
                        # own URL so the menu entry gets highlighted.
                        "title": "Maintenance",
                        "icon": "build",
                        "link": lambda request=None: reverse(
                            "admin:django_admin_runner_registeredcommand_group",
                            args=["Maintenance"],
                        ),
                        "active": lambda request: request.path
                        == reverse(
                            "admin:django_admin_runner_registeredcommand_group",
                            args=["Maintenance"],
                        ),
                        "permission": lambda request: request.user.is_staff,
                    },
                    {
                        # Multi-group pinned view: "+"-separated groups.
                        "title": "Data (Import/Export)",
                        "icon": "sync",
                        "link": lambda request=None: reverse(
                            "admin:django_admin_runner_registeredcommand_group",
                            args=["Import+Export"],
                        ),
                        "active": lambda request: request.path
                        == reverse(
                            "admin:django_admin_runner_registeredcommand_group",
                            args=["Import+Export"],
                        ),
                        "permission": lambda request: request.user.is_staff,
                    },
                    {
                        "title": "Schedules",
                        "icon": "schedule",
                        "link": reverse_lazy(
                            "admin:django_admin_runner_scheduledcommand_changelist"
                        ),
                        "permission": lambda request: request.user.is_staff,
                    },
                    {
                        "title": "Results",
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
                "title": "Scheduled Tasks",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Schedules",
                        "icon": "schedule",
                        "link": reverse_lazy("admin:django_q_schedule_changelist"),
                    },
                    {
                        "title": "Successful tasks",
                        "icon": "check_circle",
                        "link": reverse_lazy("admin:django_q_success_changelist"),
                    },
                    {
                        "title": "Failed tasks",
                        "icon": "error",
                        "link": reverse_lazy("admin:django_q_failure_changelist"),
                    },
                    {
                        "title": "Queued tasks",
                        "icon": "list_alt",
                        "link": reverse_lazy("admin:django_q_ormq_changelist"),
                    },
                ],
            },
        ]
    }
}
