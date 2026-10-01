#!/bin/sh
# Arranque del backend. Si falta un secreto, la carga de settings falla y el
# contenedor no arranca (ADR-009).
set -eu

# Las migraciones las aplica el servicio "migrador" con el rol dueño de las
# tablas (ADR-030, B8); este rol solo tiene DML. Si quedan migraciones sin
# aplicar, la app no arranca (en vez de fallar a medias más tarde).
python manage.py migrate --check --noinput >/dev/null     || { echo "Hay migraciones sin aplicar: ejecute docker compose up -d (servicio migrador)." >&2; exit 1; }

# --no-control-socket: el usuario sin privilegios no tiene home (/nonexistent)
# y la interfaz de control de gunicorn no se usa.
exec gunicorn altiro.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 30 \
    --no-control-socket
