"""Ajustes de Django para AlTiro.

Toda la configuración proviene del entorno (RNF-24, ADR-009); los secretos, de
archivos ``*_FILE``. Si falta un secreto o un ajuste obligatorio, la carga de
este módulo falla y la aplicación no arranca.

``django.contrib.admin`` queda excluido (ADR-001). El modelo de usuario propio
(``identidad.Usuario``) se fija en la primera migración (ADR-001).
``django.contrib.auth`` y ``contenttypes`` no se instalan: ``AbstractBaseUser``
se importa desde ``django.contrib.auth.base_user`` sin instalar la app, y no se
usan grupos ni permisos de Django (los roles viven en ``usuario_rol``). Por eso
el inicio de sesión lo hace ``identidad.sesion`` y no ``django.contrib.auth.login``.
"""
from pathlib import Path

from altiro.configuracion import (
    leer_booleano,
    leer_entero,
    leer_lista,
    leer_secreto,
    leer_variable,
)

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = leer_secreto("DJANGO_SECRET_KEY")
DEBUG = leer_booleano("DJANGO_DEBUG", por_defecto=False)
ALLOWED_HOSTS = leer_lista("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.sessions",  # ADR-005
    "territorio",
    "identidad",
]

# ADR-001: fijado desde la primera migración.
AUTH_USER_MODEL = "identidad.Usuario"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",  # ADR-005
    "django.middleware.common.CommonMiddleware",
    "identidad.middleware.UsuarioDeLaSesionMiddleware",
    # Antes que CSRF: una ruta privada sin sesión responde 401, no 403.
    "comun.middleware.PrivadoPorDefectoMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # ADR-006
]

ROOT_URLCONF = "altiro.urls"
WSGI_APPLICATION = "altiro.wsgi.application"

# Rol de la aplicación, sin superusuario (infra/db/initdb). Nunca POSTGRES_USER.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": leer_variable("ALTIRO_DB_NAME"),
        "USER": leer_variable("ALTIRO_DB_USER"),
        "PASSWORD": leer_secreto("ALTIRO_DB_PASSWORD"),
        "HOST": leer_variable("ALTIRO_DB_HOST"),
        "PORT": leer_variable("ALTIRO_DB_PORT"),
        "OPTIONS": {"connect_timeout": 5},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Contraseñas (RNF-05, ADR-004) ---
# Único hasher: Argon2id con parámetros medidos (identidad.hashers).
PASSWORD_HASHERS = ["identidad.hashers.Argon2idAlTiro"]

# --- Sesiones (RF-02, RNF-09, ADR-005) ---
# Expiración deslizante por inactividad: cada petición renueva el plazo.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = leer_entero("ALTIRO_SESION_INACTIVIDAD_SEGUNDOS", por_defecto=1800)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# --- Limitación de intentos (RNF-10, ADR-007) ---
# Solo se confía en X-Real-IP si la aplicación está detrás del proxy propio.
ALTIRO_CONFIAR_X_REAL_IP = leer_booleano("ALTIRO_CONFIAR_X_REAL_IP", por_defecto=False)

# --- Transporte y cookies (ADR-006, ADR-008) ---
# La aplicación está detrás de Nginx, que termina TLS y fija X-Forwarded-Proto.
if leer_booleano("DJANGO_CONFIAR_PROXY_TLS", por_defecto=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = leer_lista("DJANGO_CSRF_TRUSTED_ORIGINS")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
# El frontend lee la cookie CSRF para enviarla en X-CSRFToken (ADR-006).
CSRF_COOKIE_HTTPONLY = False
CSRF_FAILURE_VIEW = "comun.api.fallo_csrf"
# Sin HSTS en la demostración (ADR-008). Django no lo emite con valor 0.
SECURE_HSTS_SECONDS = 0

# --- Registros ---
# Solo a la consola del contenedor. Nunca registrar contraseñas, tokens,
# cookies ni cuerpos de petición.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["consola"], "level": "INFO"},
}
