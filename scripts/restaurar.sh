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
#   ALTIRO_RESTAURAR_SECRETOS_VOLUMEN  volumen Docker con los secretos (contraseñas,
#       clave de documentos y clave de respaldos) respaldados APARTE (E-7.2).
#       Obligatoria: sin respaldo_clave (ADR-030, B6) el respaldo cifrado no se
#       puede descifrar, y sin documentos_clave los documentos no se pueden leer.
#
# Formatos aceptados:
#   - cifrado (ADR-030, B6): base.dump.gpg, fotos.tar.gz.gpg, documentos.tar.gpg;
#     se descifran en tubería con la clave del volumen de secretos;
#   - en claro (respaldos anteriores a ADR-030): base.dump, fotos.tar.gz,
#     documentos.tar. Se restauran igual, con un aviso.
#
# Protección (CLAUDE.md §14): se niega a continuar si CUALQUIER volumen del
# proyecto destino ya existe. Nunca borra ni sobrescribe volúmenes ni bases:
# solo restaura en un proyecto vacío (el simulacro usa -p altiro-restauracion;
# tras un desastre real, el proyecto principal ya no tiene volúmenes).
#
# Pasos: verifica sumas → (cifrado) comprueba la clave → crea los volúmenes
# vacíos → copia los secretos → descifra y extrae fotos y documentos → levanta
# db → descifra y pg_restore → levanta app y espera "healthy" (antes corren
# roles_db, que reparte dueños, y migrador, que aplica migraciones pendientes;
# ADR-030, B8). Imprime los tiempos.
set -euo pipefail

RESPALDO="${1:?Uso: scripts/restaurar.sh <directorio-del-respaldo> [proyecto]}"
PROYECTO="${2:-altiro-restauracion}"
SECRETOS="${ALTIRO_RESTAURAR_SECRETOS_VOLUMEN:?Falta ALTIRO_RESTAURAR_SECRETOS_VOLUMEN (volumen con los secretos respaldados aparte)}"
IMAGEN=postgres:16.15-bookworm
VOLUMENES=(datos_db secretos certificados documentos fotos buzon)
export MSYS_NO_PATHCONV=1

# Ruta para montar en Docker (en Git Bash, con letra de unidad) y ruta local del volcado.
RESPALDO_ABS="$(cd "$RESPALDO" && (pwd -W 2>/dev/null || pwd))"
if [ -f "$RESPALDO/base.dump.gpg" ]; then
    CIFRADO=si
    SUFIJO=.gpg
elif [ -f "$RESPALDO/base.dump" ]; then
    CIFRADO=no
    SUFIJO=
    echo "Aviso: respaldo EN CLARO (anterior a ADR-030, B6). Trátelo como dato personal y bórrelo cuando deje de servir." >&2
else
    echo "El directorio no contiene base.dump.gpg ni base.dump: no es un respaldo de AlTiro." >&2
    exit 1
fi
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

# Descifrado (ADR-030, B6): siempre dentro de un contenedor desechable que
# monta el volumen de secretos de solo lectura; la clave nunca sale de ese
# volumen ni se imprime. gpg falla si el MDC no cuadra (archivo alterado).
DESCIFRAR='gpg --batch --quiet --no-tty --homedir "$(mktemp -d)" --pinentry-mode loopback --passphrase-file /secretos/respaldo_clave --decrypt'
if [ "$CIFRADO" = si ]; then
    if ! docker run --rm -v "$SECRETOS:/secretos:ro" "$IMAGEN" test -s /secretos/respaldo_clave; then
        echo "El volumen $SECRETOS no tiene respaldo_clave: sin esa clave este respaldo cifrado NO se puede restaurar (README, Respaldo)." >&2
        exit 1
    fi
    marca "Comprobando que la clave descifra los tres archivos completos (integridad MDC)."
    docker run --rm -v "$RESPALDO_ABS:/respaldo:ro" -v "$SECRETOS:/secretos:ro" "$IMAGEN" \
        bash -c "for f in base.dump.gpg fotos.tar.gz.gpg documentos.tar.gpg; do $DESCIFRAR /respaldo/\$f >/dev/null || exit 1; done"
fi
extraer() {  # extraer <archivo> <volumen destino> <opciones de tar>
    local origen="cat /respaldo/$1"
    [ "$CIFRADO" = si ] && origen="$DESCIFRAR /respaldo/$1"
    docker run --rm -v "$RESPALDO_ABS:/respaldo:ro" -v "$SECRETOS:/secretos:ro" -v "$2:/destino" "$IMAGEN" \
        bash -c "set -o pipefail; $origen | tar --numeric-owner $3 -f - -C /destino"
}

marca "Creando volúmenes vacíos del proyecto $PROYECTO."
for volumen in secretos documentos fotos; do
    docker volume create --label "com.docker.compose.project=$PROYECTO"         --label "com.docker.compose.volume=$volumen" "${PROYECTO}_${volumen}" >/dev/null
done

marca "Copiando secretos (respaldados aparte) y extrayendo fotos y documentos."
docker run --rm -v "$SECRETOS:/origen:ro" -v "${PROYECTO}_secretos:/destino" "$IMAGEN" cp -a /origen/. /destino/
extraer "fotos.tar.gz$SUFIJO" "${PROYECTO}_fotos" -xpz
extraer "documentos.tar$SUFIJO" "${PROYECTO}_documentos" -xp

marca "Levantando db."
dc up -d --no-build --wait db

marca "Restaurando la base (pg_restore)."
if [ "$CIFRADO" = si ]; then
    docker run --rm -v "$RESPALDO_ABS:/respaldo:ro" -v "$SECRETOS:/secretos:ro" "$IMAGEN" \
        bash -c "$DESCIFRAR /respaldo/base.dump.gpg" \
        | dc exec -T db sh -c 'pg_restore --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
else
    dc exec -T db sh -c 'pg_restore --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$RESPALDO/base.dump"
fi

marca "Levantando app y esperando health."
dc up -d --no-build --wait app
marca "Restauración completa: app sana en el proyecto $PROYECTO."
