#!/usr/bin/env bash
# Restauración de un respaldo de AlTiro (RNF-19; ADR-026, E-7.3).
#
# Uso (desde la raíz del repositorio, Git Bash o Linux):
#   scripts/restaurar.sh <directorio-del-respaldo> [proyecto]
#
#   <directorio-del-respaldo>  un altiro-AAAAMMDDTHHMMSSZ/ de scripts/respaldo.sh
#   [proyecto]                 proyecto Compose destino (por defecto altiro-restauracion)
#
# Variables:
#   ALTIRO_RESTAURAR_SECRETOS_VOLUMEN  volumen Docker con los secretos (contraseñas
#       y clave de documentos) respaldados APARTE (E-7.2). Obligatoria: sin la
#       clave de cifrado los documentos no se pueden leer.
#
# Protección (CLAUDE.md §14): se niega a continuar si CUALQUIER volumen del
# proyecto destino ya existe. Nunca borra ni sobrescribe volúmenes ni bases:
# solo restaura en un proyecto vacío (el simulacro usa -p altiro-restauracion;
# tras un desastre real, el proyecto principal ya no tiene volúmenes).
#
# Pasos: verifica sumas → crea los volúmenes vacíos → copia los secretos →
# extrae fotos y documentos → levanta db → pg_restore → levanta app y espera
# "healthy" (aplica migraciones pendientes al arrancar). Imprime los tiempos.
set -euo pipefail

RESPALDO="${1:?Uso: scripts/restaurar.sh <directorio-del-respaldo> [proyecto]}"
PROYECTO="${2:-altiro-restauracion}"
SECRETOS="${ALTIRO_RESTAURAR_SECRETOS_VOLUMEN:?Falta ALTIRO_RESTAURAR_SECRETOS_VOLUMEN (volumen con los secretos respaldados aparte)}"
IMAGEN=postgres:16.15-bookworm
VOLUMENES=(datos_db secretos certificados documentos fotos)
export MSYS_NO_PATHCONV=1

# Ruta para montar en Docker (en Git Bash, con letra de unidad) y ruta local del volcado.
RESPALDO_ABS="$(cd "$RESPALDO" && (pwd -W 2>/dev/null || pwd))"
VOLCADO="$(cd "$RESPALDO" && pwd)/base.dump"
cd "$(dirname "$0")/.."
dc() { docker compose -p "$PROYECTO" "$@"; }
t0=$(date +%s)
marca() { echo "[$(( $(date +%s) - t0 )) s] $*"; }

for volumen in "${VOLUMENES[@]}"; do
    if docker volume inspect "${PROYECTO}_${volumen}" >/dev/null 2>&1; then
        echo "El volumen ${PROYECTO}_${volumen} ya existe: no se restaura sobre datos existentes." >&2
        exit 1
    fi
done
docker volume inspect "$SECRETOS" >/dev/null

marca "Verificando sumas del respaldo."
docker run --rm -v "$RESPALDO_ABS:/respaldo:ro" -w /respaldo "$IMAGEN" sha256sum -c --quiet SHA256SUMS

marca "Creando volúmenes vacíos del proyecto $PROYECTO."
for volumen in secretos documentos fotos; do
    docker volume create --label "com.docker.compose.project=$PROYECTO"         --label "com.docker.compose.volume=$volumen" "${PROYECTO}_${volumen}" >/dev/null
done

marca "Copiando secretos (respaldados aparte) y extrayendo fotos y documentos."
docker run --rm -v "$SECRETOS:/origen:ro" -v "${PROYECTO}_secretos:/destino" "$IMAGEN" cp -a /origen/. /destino/
docker run --rm -v "$RESPALDO_ABS:/respaldo:ro" -v "${PROYECTO}_fotos:/destino" "$IMAGEN" \
    tar --numeric-owner -xpzf /respaldo/fotos.tar.gz -C /destino
docker run --rm -v "$RESPALDO_ABS:/respaldo:ro" -v "${PROYECTO}_documentos:/destino" "$IMAGEN" \
    tar --numeric-owner -xpf /respaldo/documentos.tar -C /destino

marca "Levantando db."
dc up -d --no-build --wait db

marca "Restaurando la base (pg_restore)."
dc exec -T db sh -c 'pg_restore --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$VOLCADO"

marca "Levantando app y esperando health."
dc up -d --no-build --wait app
marca "Restauración completa: app sana en el proyecto $PROYECTO."
