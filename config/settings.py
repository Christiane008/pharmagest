"""Paramètres de PharmaGest.

Les secrets sont lus dans les variables d'environnement (cahier des charges, 8.1).
Les valeurs par défaut ne conviennent qu'au développement local.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "PHARMAGEST_SECRET_KEY",
    "dev-uniquement-a-remplacer-en-production-0123456789abcdef",
)
DEBUG = os.environ.get("PHARMAGEST_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("PHARMAGEST_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Applications PharmaGest
    "utilisateurs",
    "medicaments",
    "fournisseurs",
    "clients",
    "stock",
    "achats",
    "ventes",
    "rapports",
]

MIDDLEWARE = [
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "utilisateurs.context_processors.pharmacie",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite en développement ; PostgreSQL recommandé en production (cahier, 7).
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

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Indian/Antananarivo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "tableau_de_bord"
LOGOUT_REDIRECT_URL = "login"

# Réinitialisation du mot de passe : en développement, l'e-mail s'affiche dans le terminal.
EMAIL_BACKEND = os.environ.get(
    "PHARMAGEST_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = "pharmagest@localhost"

# Paramètres métier
PHARMAGEST_TAILLE_MAX_PHOTO = 2 * 1024 * 1024  # 2 Mo
PHARMAGEST_PAGINATION = 15
PHARMAGEST_DOSSIER_SAUVEGARDES = BASE_DIR / "sauvegardes"

# Durcissement en production (DEBUG désactivé)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Tests plus rapides : hachage léger uniquement pendant « manage.py test ».
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    LOGGING = {"version": 1, "disable_existing_loggers": False,
               "loggers": {"django.request": {"level": "ERROR"}}}
