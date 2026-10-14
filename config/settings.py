import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # lokal; Vercel'de dosya yok, sorun değil

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # yoksa açıkça patlasın
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
# Yalnızca LOKAL: DEBUG kapalıyken (DJANGO_DEBUG=0) siteyi http://localhost üzerinde denemek için.
# `Secure` çerezleri kapatır ve DATABASE_URL yoksa SQLite'a izin verir. Vercel'de (VERCEL=1) yok sayılır.
LOCAL_HTTP = os.environ.get("DJANGO_LOCAL_HTTP") == "1" and not os.environ.get("VERCEL")

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".vercel.app"]
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "polls",
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
]

CSRF_FAILURE_VIEW = "config.views.csrf_failure"

ROOT_URLCONF = "config.urls"

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
                "config.context_processors.asset_version",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# Rate limit için DB tabanlı cache (serverless'ta bellek içi cache örnekler arası paylaşılmaz).
# Tablo `polls` migration'ıyla oluşur (createcachetable); elle çalıştırmaya gerek yok.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 20000, "CULL_FREQUENCY": 3},
    }
}

# scope: (en fazla istek, pencere saniye) — IP başına
RATE_LIMITS = {
    "vote": (20, 60),       # dakikada 20 oy
    "poll": (10, 3600),     # saatte 10 anket
    "report": (5, 3600),    # saatte 5 şikâyet
}

LOGIN_URL = "/giris/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# --- Veritabanı (bkz. KARARSIZIM.md Bölüm 9.4; bu ayarları değiştirme) ---
DATABASE_URL = os.environ.get("DATABASE_URL")

if "test" in sys.argv:
    # Testler her zaman lokal SQLite ile çalışır; Supabase'e test DB'si açılmaz.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
elif DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,
            conn_health_checks=False,
            ssl_require=True,
        )
    }
    DATABASES["default"]["OPTIONS"] = {
        **DATABASES["default"].get("OPTIONS", {}),
        "prepare_threshold": None,
    }
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
elif DEBUG or LOCAL_HTTP:
    # Sadece lokal geliştirme için
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Prod'da DATABASE_URL eksikse sessizce SQLite'a düşme. collectstatic DB'ye
    # bağlanmadığı için build bu yüzden çökmez; DB'ye ilk erişimde net hata verir.
    DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = not LOCAL_HTTP
    CSRF_COOKIE_SECURE = not LOCAL_HTTP
    SECURE_CONTENT_TYPE_NOSNIFF = True
