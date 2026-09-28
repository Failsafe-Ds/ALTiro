#!/bin/sh
# Arranque del backend. Si falta un secreto, la carga de settings falla y el
# contenedor no arranca (ADR-009).
set -eu

python manage.py migrate --noinput

# --no-control-socket: el usuario sin privilegios no tiene home (/nonexistent)
# y la interfaz de control de gunicorn no se usa.
exec gunicorn altiro.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 30 \
    --no-control-socket
