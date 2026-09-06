"""
War of Justice Django settings.

All secrets/config come from environment variables (see .env.example) —
never hard-code credentials here. Uses SQLite by default for local dev;
point DB_* vars at Postgres for staging/production.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",

    # War of Justice apps
    "apps.accounts",
    "apps.categories",
    "apps.posts",
    "apps.media_lib",
    "apps.videos",
    "apps.comments",
    "apps.notifications",
    "apps.analytics",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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

# ---- Database (SQLite for local dev; swap to Postgres via env for prod) ----
if config("DB_ENGINE", default="sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="newshub"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- CORS / CSRF: only the Next.js frontend origin(s) may call the API ----
# CORS_ALLOW_CREDENTIALS is required for the httpOnly refresh-token cookie
# to be sent/received cross-origin (frontend on :3000, backend on :8000) —
# without it, browsers silently drop the Set-Cookie header.
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv()
)
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="http://localhost:3000", cast=Csv()
)

# ---- DRF ----
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 15,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ---- JWT (short-lived access token + rotating, blacklisted refresh token) ----
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "War of Justice API",
    "DESCRIPTION": "REST API powering the War of Justice Next.js website and future Flutter app.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---- Cloudflare R2 (images/files) — S3-compatible, accessed via boto3 ----
R2_ENDPOINT_URL = config("R2_ENDPOINT_URL", default="")  # https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID = config("R2_ACCESS_KEY_ID", default="")
R2_SECRET_ACCESS_KEY = config("R2_SECRET_ACCESS_KEY", default="")
R2_BUCKET_NAME = config("R2_BUCKET_NAME", default="newshub-media")
R2_PUBLIC_BASE_URL = config("R2_PUBLIC_BASE_URL", default="https://media.newshub.example.com")

# ---- Bunny Stream (video) ----
BUNNY_STREAM_LIBRARY_ID = config("BUNNY_STREAM_LIBRARY_ID", default="")
BUNNY_STREAM_API_KEY = config("BUNNY_STREAM_API_KEY", default="")  # server-side only, never sent to frontend
BUNNY_STREAM_CDN_HOSTNAME = config("BUNNY_STREAM_CDN_HOSTNAME", default="")  # e.g. vz-xxxx.b-cdn.net
BUNNY_WEBHOOK_SECRET = config("BUNNY_WEBHOOK_SECRET", default="")  # validates Bunny's status-update webhook

# ---- Frontend URL (for building links inside emails, e.g. password reset) ----
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")

# ---- Email ----
# Defaults to printing emails to the console — safe for local dev, sends
# nothing real. Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# and the SMTP_* vars in .env for real delivery (Postgres-style hosted
# email providers like SendGrid/Mailgun/SES all work via SMTP or their own
# Django backend package — swap EMAIL_BACKEND accordingly).
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="War of Justice <no-reply@warofjustice.com>")

# ---- Production security hardening (only active when DEBUG=False) ----
# These are no-ops in local dev (DEBUG=True) so they never get in the way
# of `runserver` over plain HTTP, but are essential once deployed behind
# a real domain with HTTPS.
if not DEBUG:
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Needed if deployed behind a proxy/load balancer that terminates TLS
    # (Railway, Render, Heroku-style platforms, or nginx in front of gunicorn).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
