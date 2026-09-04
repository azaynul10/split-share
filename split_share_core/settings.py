"""
Django settings for the Sub-Share project.

Two deliberate choices worth noting:

1. No Django ORM is used anywhere. There are no models and no migrations.
   Every database operation goes through django.db.connection.cursor() with
   parameterised raw SQL. django.contrib.auth and django.contrib.admin are
   therefore not installed.

2. Sessions are stored in a signed cookie rather than a database table.
   This keeps the split_share database at exactly the 12 tables defined in
   db/schema.sql, with no Django-generated tables mixed in. The trade-off is
   that a session cannot be revoked server-side, which is why access control
   re-reads the user's row on every protected request.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-key-change-before-any-public-deployment",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# ---------------------------------------------------------------------------
# Applications
# django.contrib.sessions is intentionally absent: the signed-cookie session
# backend needs no database table, so the app (and its migrations) is not
# required. django.contrib.messages has no models, so nothing to migrate.
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "marketplace",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "split_share_core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "marketplace.context_processors.current_user",
            ],
        },
    },
]

WSGI_APPLICATION = "split_share_core.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# Configured so connection.cursor() works. No ORM models are defined.
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "split_share"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
    }
}

# ---------------------------------------------------------------------------
# Sessions and flash messages, both cookie-backed so the database stays clean.
#
# A signed cookie cannot be revoked from the server, because there is no
# server-side session record to delete. Two things limit the damage: the
# lifetime is short and tied to the browser session, and every protected
# request re-checks the user's row (see marketplace/decorators.py).
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 60 * 8

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

# ---------------------------------------------------------------------------
# Password hashing
# Used through make_password() / check_password() from django.contrib.auth.hashers.
# These helpers work without django.contrib.auth being installed.
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = False

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_CHARSET = "utf-8"
