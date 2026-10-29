import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
LOCAL_DEMO = os.getenv("LOCAL_DEMO", "0") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not LOCAL_DEMO:
        raise ImproperlyConfigured("Configura DJANGO_SECRET_KEY o LOCAL_DEMO=1 para desarrollo.")
    SECRET_KEY = "local-development-only-resive-not-for-production-2026"
if LOCAL_DEMO and not DEBUG:
    raise ImproperlyConfigured("LOCAL_DEMO solo puede usarse con DJANGO_DEBUG=1.")
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
CSRF_TRUSTED_ORIGINS = [s for s in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if s]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "apps.core",
    "apps.accounts",
    "apps.locations",
    "apps.listings",
    "apps.inquiries",
    "apps.notifications",
    "apps.moderation",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.PrivacyMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ]
        },
    }
]
database_url = os.getenv("DATABASE_URL")
if os.getenv("RESIVE_MIGRATE") == "1":
    database_url = os.getenv("MIGRATION_DATABASE_URL", database_url)
if database_url:
    DATABASES = {"default": dj_database_url.parse(database_url, conn_max_age=60, conn_health_checks=True)}
    if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL debe apuntar a PostgreSQL.")
    if os.getenv("DATABASE_SCHEMA", "resive") != "public":
        DATABASES["default"].setdefault("OPTIONS", {})["options"] = "-c search_path=resive,public"
    if not DEBUG:
        DATABASES["default"].setdefault("OPTIONS", {}).setdefault("sslmode", "verify-full")
elif LOCAL_DEMO:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "demo.sqlite3"}}
else:
    raise ImproperlyConfigured("Configura DATABASE_URL de Supabase.")
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{name}"}
    for name in [
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    ]
]
LANGUAGE_CODE = "es-ve"
TIME_ZONE = "America/Caracas"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/panel/publicaciones/"
LOGOUT_REDIRECT_URL = "/"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/local-media/"
STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
if LOCAL_DEMO:
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
else:
    for key in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]:
        if not os.getenv(key):
            raise ImproperlyConfigured(f"Falta {key} para R2.")
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["R2_BUCKET_NAME"],
            "access_key": os.environ["R2_ACCESS_KEY_ID"],
            "secret_key": os.environ["R2_SECRET_ACCESS_KEY"],
            "endpoint_url": f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            "region_name": "auto",
            "signature_version": "s3v4",
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": 300,
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "private, max-age=0, no-store"},
        },
    }
FILE_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 9 * 1024 * 1024
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if LOCAL_DEMO
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "ResiVe <noreply@example.com>")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
TRUST_PROXY_SSL = os.getenv("TRUST_PROXY_SSL") == "1"
if TRUST_PROXY_SSL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Tests explicitly isolate external storage and email; DATABASE_URL must be disposable.
if "test" in sys.argv:
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.InMemoryStorage"}
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    SECURE_SSL_REDIRECT = False
