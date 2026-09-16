"""
War of Justice Django settings.

All secrets/config come from environment variables (see .env.example).
Never hard-code credentials here.

Uses SQLite by default for local development
and PostgreSQL when DATABASE_URL is provided.
"""

from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config


BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# DJANGO CORE
# ============================================================

SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="dev-only-insecure-key-change-me",
)

DEBUG = config(
    "DEBUG",
    default=True,
    cast=bool,
)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=Csv(),
)

AUTH_USER_MODEL = "accounts.User"


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "storages",

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


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "corsheaders.middleware.CorsMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


# ============================================================
# TEMPLATES
# ============================================================

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


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = config(
    "DATABASE_URL",
    default="",
)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME":
            "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME":
            "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME":
            "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"


# ============================================================
# CLOUDFLARE R2
# ============================================================

# Common R2 S3-compatible connection
R2_ENDPOINT_URL = config(
    "R2_ENDPOINT_URL",
    default="",
)

R2_ACCESS_KEY_ID = config(
    "R2_ACCESS_KEY_ID",
    default="",
)

R2_SECRET_ACCESS_KEY = config(
    "R2_SECRET_ACCESS_KEY",
    default="",
)


# ------------------------------------------------------------
# PRIVATE BUCKET
# ------------------------------------------------------------
# Used for sensitive Member & Contributor documents:
# - Selfie
# - Aadhaar
# - PAN
# - Identity proof
# - Supporting documents

R2_PRIVATE_BUCKET_NAME = config(
    "R2_PRIVATE_BUCKET_NAME",
    default="war-of-justice-media",
)


# ------------------------------------------------------------
# PUBLIC BUCKET
# ------------------------------------------------------------
# Used for public article/media files:
# - Featured images
# - Article images
# - Public media

R2_PUBLIC_BUCKET_NAME = config(
    "R2_PUBLIC_BUCKET_NAME",
    default="war-of-justice-public-media",
)


# Public browser-facing base URL for article images.
#
# Example:
# https://pub-xxxxxxxxxxxxxxxx.r2.dev

R2_PUBLIC_BASE_URL = config(
    "R2_PUBLIC_BASE_URL",
    default="",
)


# ============================================================
# DJANGO STORAGE
# ============================================================

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND":
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# ============================================================
# AWS S3 / CLOUDFLARE R2 SETTINGS
# ============================================================

AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID

AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY

# Keep Django's default storage on the PRIVATE bucket.
#
# This is important because member identity documents
# must not automatically become public.
AWS_STORAGE_BUCKET_NAME = R2_PRIVATE_BUCKET_NAME

AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL

AWS_S3_REGION_NAME = "auto"

AWS_S3_SIGNATURE_VERSION = "s3v4"

AWS_DEFAULT_ACL = None

# Keep the private/default storage bucket private.
# Django can generate signed URLs when needed.
AWS_QUERYSTRING_AUTH = True

AWS_S3_FILE_OVERWRITE = False

AWS_S3_ADDRESSING_STYLE = "path"


# ============================================================
# MEDIA FILES
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# CORS / CSRF
# ============================================================

CORS_ALLOW_CREDENTIALS = True


CORS_ALLOWED_ORIGINS = list(
    dict.fromkeys(
        config(
            "CORS_ALLOWED_ORIGINS",
            default="",
            cast=Csv(),
        )
        + [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)


CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(
        config(
            "CSRF_TRUSTED_ORIGINS",
            default="",
            cast=Csv(),
        )
        + [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
)


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),

    "DEFAULT_PAGINATION_CLASS":
        "rest_framework.pagination.PageNumberPagination",

    "PAGE_SIZE": 15,

    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],

    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
    },

    "DEFAULT_SCHEMA_CLASS":
        "drf_spectacular.openapi.AutoSchema",
}


# ============================================================
# JWT
# ============================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=15
    ),

    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=7
    ),

    "ROTATE_REFRESH_TOKENS": True,

    "BLACKLIST_AFTER_ROTATION": True,

    "UPDATE_LAST_LOGIN": True,

    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),

    "USER_ID_FIELD": "id",

    "USER_ID_CLAIM": "user_id",
}


# ============================================================
# API DOCUMENTATION
# ============================================================

SPECTACULAR_SETTINGS = {
    "TITLE":
        "War of Justice API",

    "DESCRIPTION":
        "REST API powering the War of Justice Next.js website and future Flutter app.",

    "VERSION":
        "1.0.0",

    "SERVE_INCLUDE_SCHEMA":
        False,
}


# ============================================================
# BUNNY STREAM
# ============================================================

BUNNY_STREAM_LIBRARY_ID = config(
    "BUNNY_STREAM_LIBRARY_ID",
    default="",
)

BUNNY_STREAM_API_KEY = config(
    "BUNNY_STREAM_API_KEY",
    default="",
)

BUNNY_STREAM_CDN_HOSTNAME = config(
    "BUNNY_STREAM_CDN_HOSTNAME",
    default="",
)

BUNNY_WEBHOOK_SECRET = config(
    "BUNNY_WEBHOOK_SECRET",
    default="",
)


# ============================================================
# FRONTEND
# ============================================================

FRONTEND_URL = config(
    "FRONTEND_URL",
    default="http://localhost:3000",
)


# ============================================================
# EMAIL
# ============================================================

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST = config(
    "EMAIL_HOST",
    default="",
)

EMAIL_PORT = config(
    "EMAIL_PORT",
    default=587,
    cast=int,
)

EMAIL_HOST_USER = config(
    "EMAIL_HOST_USER",
    default="",
)

EMAIL_HOST_PASSWORD = config(
    "EMAIL_HOST_PASSWORD",
    default="",
)

EMAIL_USE_TLS = config(
    "EMAIL_USE_TLS",
    default=True,
    cast=bool,
)

DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default="War of Justice <no-reply@warofjustice.com>",
)


# ============================================================
# PRODUCTION SECURITY
# ============================================================

if not DEBUG:

    SECURE_SSL_REDIRECT = config(
        "SECURE_SSL_REDIRECT",
        default=True,
        cast=bool,
    )

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = config(
        "SECURE_HSTS_SECONDS",
        default=31536000,
        cast=int,
    )

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True

    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )