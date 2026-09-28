#!/bin/sh
# Crea o actualiza el rol de la aplicación con privilegios mínimos.
#
# La imagen oficial de postgres ejecuta los scripts de /docker-entrypoint-initdb.d
# SOLO cuando el volumen de datos está vacío. El script es idempotente, así que
# también puede ejecutarse a mano sobre un volumen existente (ver README).
#
# Diseño:
# - POSTGRES_USER (superusuario de la imagen) solo inicializa; la app no lo usa.
# - El rol de la app es NOSUPERUSER, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS.
# - CREATEDB solo para que pytest-django cree y borre la base de pruebas.
# - En la base de AlTiro: CONNECT y TEMPORARY; en el esquema public: USAGE y
#   CREATE (Django crea sus tablas y queda como su dueño).
# - Se quita CONNECT a PUBLIC en postgres, template1 y la base de AlTiro, para
#   que el rol de la app no tenga acceso a otras bases.
# Nunca imprime la contraseña.
set -e

: "${POSTGRES_USER:?Falta POSTGRES_USER}"
: "${POSTGRES_DB:?Falta POSTGRES_DB}"
: "${ALTIRO_DB_APP_USER:?Falta ALTIRO_DB_APP_USER}"
: "${ALTIRO_DB_APP_PASSWORD_FILE:?Falta ALTIRO_DB_APP_PASSWORD_FILE}"

if [ "$ALTIRO_DB_APP_USER" = "$POSTGRES_USER" ]; then
    echo "ALTIRO_DB_APP_USER debe ser distinto de POSTGRES_USER." >&2
    false
fi

# Sin fines de línea, igual que la lectura de secretos en Django.
ALTIRO_DB_APP_PASSWORD="$(tr -d '\r\n' < "$ALTIRO_DB_APP_PASSWORD_FILE")"
if [ -z "$ALTIRO_DB_APP_PASSWORD" ]; then
    echo "El archivo indicado en ALTIRO_DB_APP_PASSWORD_FILE está vacío." >&2
    false
fi
export ALTIRO_DB_APP_PASSWORD

psql -v ON_ERROR_STOP=1 --no-psqlrc \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=app_user="$ALTIRO_DB_APP_USER" \
    --set=db_name="$POSTGRES_DB" <<'SQL'
\getenv app_password ALTIRO_DB_APP_PASSWORD

SELECT format('CREATE ROLE %I LOGIN', :'app_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec

ALTER ROLE :"app_user" WITH LOGIN NOSUPERUSER NOCREATEROLE CREATEDB
    NOREPLICATION NOBYPASSRLS INHERIT PASSWORD :'app_password';

REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE template1 FROM PUBLIC;

GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO :"app_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
SQL

unset ALTIRO_DB_APP_PASSWORD
echo "Rol de la aplicación listo: $ALTIRO_DB_APP_USER (sin superusuario)."
