#!/bin/sh
# Crea o actualiza los roles de la base con privilegios mínimos.
#
# Se ejecuta en DOS contextos, siempre con el superusuario de la imagen
# (POSTGRES_USER) y de forma idempotente:
# - initdb: la imagen oficial de postgres lo corre desde
#   /docker-entrypoint-initdb.d SOLO cuando el volumen de datos está vacío
#   (por el socket local);
# - servicio "roles_db" de docker-compose.yml: en CADA arranque, por TCP
#   (PGHOST=db, PGPASSWORD con la contraseña del rol administrativo). Así un
#   volumen EXISTENTE también queda con el reparto de dueños de ADR-030 (B8).
#
# Diseño (ADR-009; ADR-030, B8):
# - POSTGRES_USER (superusuario de la imagen) solo inicializa; la app no lo usa.
# - Rol migrador (ALTIRO_DB_MIGRADOR_USER): DUEÑO de las tablas, secuencias y
#   funciones del esquema public; solo lo usa el servicio "migrador" para
#   "manage.py migrate". NOSUPERUSER, NOCREATEDB, NOCREATEROLE.
# - Rol de la app (ALTIRO_DB_APP_USER): solo DML (SELECT, INSERT, UPDATE,
#   DELETE) y uso de secuencias. NO es dueño de nada en la base de AlTiro: no
#   puede desactivar los triggers de solo inserción (bitacora, ticket_evento,
#   acceso_denegado, mensaje, precio_final_evento) ni alterar ni borrar tablas
#   ni reemplazar las funciones de esos triggers. Sin CREATE en public.
#   Conserva CREATEDB solo para que pytest-django cree y borre SU base de
#   pruebas (de la que sí es dueño).
# - Los objetos del esquema public que todavía sean de la app (volumen creado
#   antes de ADR-030) se reasignan al migrador objeto por objeto. No se usa
#   REASSIGN OWNED: también movería la base de pruebas de la app.
# - Se quita CONNECT a PUBLIC en postgres, template1 y la base de AlTiro.
# Nunca imprime contraseñas.
set -e

: "${POSTGRES_USER:?Falta POSTGRES_USER}"
: "${POSTGRES_DB:?Falta POSTGRES_DB}"
: "${ALTIRO_DB_APP_USER:?Falta ALTIRO_DB_APP_USER}"
: "${ALTIRO_DB_APP_PASSWORD_FILE:?Falta ALTIRO_DB_APP_PASSWORD_FILE}"
: "${ALTIRO_DB_MIGRADOR_USER:?Falta ALTIRO_DB_MIGRADOR_USER}"
: "${ALTIRO_DB_MIGRADOR_PASSWORD_FILE:?Falta ALTIRO_DB_MIGRADOR_PASSWORD_FILE}"

for rol in "$ALTIRO_DB_APP_USER" "$ALTIRO_DB_MIGRADOR_USER"; do
    if [ "$rol" = "$POSTGRES_USER" ]; then
        echo "Los roles de la app y del migrador deben ser distintos de POSTGRES_USER." >&2
        false
    fi
done
if [ "$ALTIRO_DB_APP_USER" = "$ALTIRO_DB_MIGRADOR_USER" ]; then
    echo "ALTIRO_DB_APP_USER y ALTIRO_DB_MIGRADOR_USER deben ser distintos." >&2
    false
fi

# leer_clave <archivo> <variable>: sin fines de línea, igual que Django.
leer_clave() {
    valor="$(tr -d '\r\n' < "$1")"
    if [ -z "$valor" ]; then
        echo "El archivo de contraseña $(basename "$1") está vacío." >&2
        false
    fi
    export "$2=$valor"
}
# Servicio roles_db: conexión por TCP con la contraseña del superusuario.
if [ -n "${ALTIRO_DB_ADMIN_PASSWORD_FILE:-}" ]; then
    leer_clave "$ALTIRO_DB_ADMIN_PASSWORD_FILE" PGPASSWORD
fi
leer_clave "$ALTIRO_DB_APP_PASSWORD_FILE" ALTIRO_DB_APP_PASSWORD
leer_clave "$ALTIRO_DB_MIGRADOR_PASSWORD_FILE" ALTIRO_DB_MIGRADOR_PASSWORD
unset valor

psql -v ON_ERROR_STOP=1 --no-psqlrc --quiet \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=app_user="$ALTIRO_DB_APP_USER" \
    --set=migrador_user="$ALTIRO_DB_MIGRADOR_USER" \
    --set=db_name="$POSTGRES_DB" <<'SQL'
\getenv app_password ALTIRO_DB_APP_PASSWORD
\getenv migrador_password ALTIRO_DB_MIGRADOR_PASSWORD

SELECT format('CREATE ROLE %I LOGIN', :'app_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'migrador_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'migrador_user') \gexec

ALTER ROLE :"app_user" WITH LOGIN NOSUPERUSER NOCREATEROLE CREATEDB
    NOREPLICATION NOBYPASSRLS INHERIT PASSWORD :'app_password';
ALTER ROLE :"migrador_user" WITH LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB
    NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD :'migrador_password';

REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE template1 FROM PUBLIC;

GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO :"app_user";
GRANT CONNECT, TEMPORARY ON DATABASE :"db_name" TO :"migrador_user";

-- Esquema: el migrador crea objetos; la app solo los usa.
GRANT USAGE, CREATE ON SCHEMA public TO :"migrador_user";
REVOKE CREATE ON SCHEMA public FROM :"app_user";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_user";

-- Volumen existente: reasignar al migrador lo que todavía sea de la app.
-- Primero tablas y vistas (sus secuencias propias, de identidad o serial,
-- cambian de dueño con ellas), luego secuencias sueltas y funciones.
SELECT format('ALTER %s public.%I OWNER TO %I',
              CASE c.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                             WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END,
              c.relname, :'migrador_user')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = :'app_user')
ORDER BY c.relname \gexec
SELECT format('ALTER SEQUENCE public.%I OWNER TO %I', c.relname, :'migrador_user')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'S'
  AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = :'app_user')
ORDER BY c.relname \gexec
SELECT format('ALTER ROUTINE %s OWNER TO %I', p.oid::regprocedure, :'migrador_user')
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proowner = (SELECT oid FROM pg_roles WHERE rolname = :'app_user')
ORDER BY 1 \gexec

-- DML para la app sobre lo existente y lo que cree el migrador en adelante.
-- Sin TRUNCATE, REFERENCES ni TRIGGER.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migrador_user" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migrador_user" IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"app_user";
SQL

unset ALTIRO_DB_APP_PASSWORD ALTIRO_DB_MIGRADOR_PASSWORD PGPASSWORD
echo "Roles listos: app $ALTIRO_DB_APP_USER (solo DML) y migrador $ALTIRO_DB_MIGRADOR_USER (dueño del esquema)."
