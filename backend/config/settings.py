"""Django settings.

The non-Django configuration (storefront, scraper tuning, secrets, CORS) still
lives in ``boot/config.toml`` + environment variables, read through
``boot.boot.initialize_app``. Django-specific settings are derived from it here.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from boot.boot import initialize_app

BASE_DIR = Path(__file__).resolve().parent.parent

CFG = initialize_app()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database(cfg: dict) -> dict:
    db = cfg["DB"]
    url = (db.get("url") or "").strip()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        parsed = urlparse(url)
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/") or "postgres",
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"connect_timeout": 10},
        }
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db.get("dbname", "postgres"),
        "USER": db.get("user", ""),
        "PASSWORD": db.get("password", ""),
        "HOST": db.get("host", "127.0.0.1"),
        "PORT": str(db.get("port", 5432)),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 10},
    }


SECRET_KEY = CFG["Security"]["jwtKey"] or "django-insecure-dev-only"
DEBUG = _as_bool(os.getenv("DJANGO_DEBUG"), default=False)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "app",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": _database(CFG)}

AUTH_PASSWORD_VALIDATORS: list[dict] = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "app.api.auth.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "EXCEPTION_HANDLER": "app.api.exceptions.domain_exception_handler",
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

CORS_ALLOWED_ORIGINS = list(CFG["CORS"]["allowOrigins"])
# Always allow local dev ports; extend via CORS_ORIGIN_REGEXES (e.g. Vercel previews).
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://(localhost|127\.0\.0\.1):\d+$",
    *list(CFG["CORS"].get("allowOriginRegexes") or []),
]
CORS_ALLOW_CREDENTIALS = True

# The raw boot config is exposed so the core/services can read it when lazily
# constructed (see app/core/bootstrap.py).
PRICE_TRACKER = CFG

# JWT signer/verifier configuration.
from app.api.auth.jwt import configure as _configure_jwt  # noqa: E402

_configure_jwt(CFG["Security"]["jwtKey"], CFG["Security"]["jwtTtlHours"])
