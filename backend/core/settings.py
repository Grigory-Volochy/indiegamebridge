"""
Django settings for core project.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path
import environ
import os
import sys


BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
environ.Env.read_env(os.path.join(BASE_DIR.parent, ".env"))
env = environ.Env()

# Django security variables
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# Django debug variables
DEBUG = env.bool("DEBUG", default=False)

# Twitch API variables (data-fetch worker)
TWITCH_API_CLIENT_SECRET = env("TWITCH_API_CLIENT_SECRET")
TWITCH_API_CLIENT_ID = env("TWITCH_API_CLIENT_ID")

# Twitch OAuth variables (user login via allauth)
TWITCH_OAUTH_CLIENT_ID = env("TWITCH_OAUTH_CLIENT_ID", default="")
TWITCH_OAUTH_CLIENT_SECRET = env("TWITCH_OAUTH_CLIENT_SECRET", default="")

# Frontend origin (post-login redirect target, CSRF/CORS trusted origin)
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# Next.js sits in front of Django and forwards X-Forwarded-Host with the
# browser's original host (localhost:3000). Trust it so allauth's redirect_uri
# is built against the frontend origin - otherwise Twitch sends the user back
# to localhost:8000 directly and the session/JWT cookies end up on the wrong
# origin.
USE_X_FORWARDED_HOST = True

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.twitch",
    "apps.users",
    "apps.streams",
    "apps.api",
    "apps.fetch",
    "apps.pages",
]

SITE_ID = 1

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ROOT_URLCONF = "core.urls"

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

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DATABASE_NAME"),
        "USER": env("DATABASE_USER"),
        "PASSWORD": env("DATABASE_PASSWORD"),
        "HOST": env("DATABASE_HOST"),
        "PORT": env("DATABASE_PORT"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"


# Auth: DRF reads JWT from an HttpOnly cookie OR Authorization: Bearer header.
# Bearer path future-proofs for a native/mobile client; cookie path is what the
# Next.js SSR frontend uses, since browsers can't attach Authorization headers
# to SSR fetches but cookies forward through Next rewrites automatically.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.users.authentication.JWTCookieAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
}

# JWT lifetimes intentionally short for access, long for refresh, with rotation
# + blacklist on refresh so logout actually revokes. "Stateless verification,
# stateful revocation" - the refresh-token blacklist is the stateful part.
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Cookie names + paths. The refresh cookie is path-scoped so it's only sent on
# the refresh endpoint - keeps it off every other request.
JWT_ACCESS_COOKIE_NAME = "ig_access"
JWT_REFRESH_COOKIE_NAME = "ig_refresh"
JWT_REFRESH_COOKIE_PATH = "/auth/token/refresh/"
JWT_COOKIE_SECURE = not DEBUG  # Secure=True breaks plain-http dev; relax in DEBUG
JWT_COOKIE_SAMESITE = "Lax"

# allauth: skip the intermediate "confirm signup" page on social login. Twitch
# returns enough info to auto-create the user; no email confirmation step.
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*"]
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_PROVIDERS = {
    "twitch": {
        # Configure via Django settings instead of admin SocialApp record.
        "APP": {
            "client_id": TWITCH_OAUTH_CLIENT_ID,
            "secret": TWITCH_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["user:read:email"],
    },
}

# After successful OAuth, allauth redirects here. The finalize view issues JWT
# cookies, flushes the allauth session, and bounces to the frontend.
LOGIN_REDIRECT_URL = "/auth/finalize-login/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/auth/finalize-logout/"

# CSRF: state-changing API endpoints (logout, refresh) use Django's
# double-submit token. Trust the frontend origin so Next-proxied requests
# carry the right Origin/Referer.
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]
CSRF_COOKIE_HTTPONLY = False  # frontend must read it to echo in X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG


# Logging
# https://docs.djangoproject.com/en/6.0/topics/logging/

LOG_DIR = Path(env.str("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# On Windows, TimedRotatingFileHandler holds an exclusive write handle on the
# log file - which blocks `manage.py test` (and prevents deleting the file)
# whenever any other Python process has already opened it (e.g. a runserver in
# another terminal or an IDE worker). Drop file handlers under the test runner;
# console output still surfaces log messages in the test output.
_RUNNING_TESTS = "test" in sys.argv

_log_handlers = {
    "console": {
        "class": "logging.StreamHandler",
        "formatter": "verbose",
    },
}
if not _RUNNING_TESTS:
    _log_handlers["fetch_file"] = {
        "class": "core.logging.SafeTimedRotatingFileHandler",
        "filename": str(LOG_DIR / "fetch.log"),
        "when": "midnight",
        "backupCount": 14,
        "encoding": "utf-8",
        "formatter": "verbose",
    }
    _log_handlers["pages_file"] = {
        "class": "core.logging.SafeTimedRotatingFileHandler",
        "filename": str(LOG_DIR / "pages.log"),
        "when": "midnight",
        "backupCount": 14,
        "encoding": "utf-8",
        "formatter": "verbose",
    }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} - {message}",
            "style": "{",
        },
    },
    "handlers": _log_handlers,
    "loggers": {
        "apps.fetch": {
            "handlers": ["console"] if _RUNNING_TESTS else ["console", "fetch_file"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.pages": {
            "handlers": ["console"] if _RUNNING_TESTS else ["console", "pages_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
