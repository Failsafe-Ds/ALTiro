#!/usr/bin/env bash
# Respaldo diario de AlTiro (RNF-19; ADR-026, E-7; R-04).
#
# Corre dentro del servicio "respaldo" (imagen postgres:16, sin imágenes nuevas):
#   altiro-respaldo.sh --bucle    # servicio: espera la hora ALTIRO_RESPALDO_HORA cada día
#   altiro-respaldo.sh --una-vez  # un respaldo ahora (operación manual o simulacro):
#       docker compose exec respaldo bash /usr/local/bin/altiro-respaldo.sh --una-vez
#
# Cada respaldo es un directorio  $DESTINO/altiro-AAAAMMDDTHHMMSSZ/  con:
#   base.dump.gpg        pg_dump -Fc de la base, cifrado
#   conteos.tsv          filas por tabla justo después del volcado (sin datos
#                        personales: nombre de tabla y número; para el simulacro)
#   fotos.tar.gz.gpg     volumen "fotos", cifrado
#   documentos.tar.gpg   volumen "documentos" (ya cifrado con AES-256-GCM, ADR-015;
#                        se vuelve a cifrar para que nada del respaldo quede legible)
#   CIFRADO              formato del cifrado (sin secretos)
#   SHA256SUMS           sumas de verificación
#
# Cifrado (ADR-030, B6): GnuPG simétrico, AES-256 con MDC (detecta cualquier
# alteración al descifrar), con la clave aleatoria de 256 bits
# secretos/respaldo_clave que genera "init". La clave NUNCA se escribe en
# $DESTINO: sin ella el respaldo no se puede restaurar (ver README.md). Los
# datos se cifran en tubería: el texto en claro nunca toca el disco del host.
# Se escribe en un directorio temporal y se renombra al terminar: un respaldo
# a medias nunca parece completo. Se eliminan los de más de
# ALTIRO_RESPALDO_RETENCION_DIAS días (7 por defecto).
#
# Seguridad (ADR-026, E-7.2, enmienda a ADR-015):
# - "documentos" y "fotos" se montan de solo lectura; este contenedor solo ve
#   texto cifrado. La clave de cifrado NO se monta aquí: se respalda aparte.
# - Solo se monta la contraseña del rol administrativo (un archivo del volumen
#   de secretos). Nunca se imprime.
set -euo pipefail

DESTINO="${ALTIRO_RESPALDO_DESTINO:-/respaldos}"
HORA="${ALTIRO_RESPALDO_HORA:-03:00}"
RETENCION_DIAS="${ALTIRO_RESPALDO_RETENCION_DIAS:-7}"
ARCHIVO_CLAVE_BD="${ALTIRO_RESPALDO_DB_PASSWORD_FILE:-/run/secretos/db_admin_password}"
ARCHIVO_CLAVE_CIFRADO="${ALTIRO_RESPALDO_CLAVE_FILE:-/run/secretos/respaldo_clave}"
DIR_FOTOS=/volumenes/fotos
DIR_DOCUMENTOS=/volumenes/documentos

registrar() {
    # Una línea JSON, como el registro de la aplicación (RNF-22). Sin rutas ni secretos.
    printf '{"nivel": "%s", "marca_tiempo": "%s", "usuario": "sistema", "operacion": "respaldo", "mensaje": "%s"}\n' \
        "$1" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$2"
}

conteos() {
    # Filas exactas por tabla del esquema public, en el mismo orden siempre.
    psql -X -At -F "$(printf '\t')" -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
        SELECT table_name,
               (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name),
                                                     false, true, '')))[1]::text
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name"
}

cifrar() {
    # Lee la entrada estándar y escribe $1 cifrado. Sin compresión propia: la
    # base ya va comprimida (-Fc) y las fotos en .tar.gz.
    gpg --batch --quiet --no-tty --homedir "$GNUPGHOME" --pinentry-mode loopback \
        --passphrase-file "$ARCHIVO_CLAVE_CIFRADO" --symmetric \
        --cipher-algo AES256 --s2k-digest-algo SHA512 --compress-algo none \
        --output "$1"
}

hacer_respaldo() {
    if [ ! -s "$ARCHIVO_CLAVE_CIFRADO" ]; then
        registrar ERROR "Falta la clave de cifrado de respaldos (secretos/respaldo_clave); ejecute docker compose up -d para que init la genere."
        exit 1
    fi
    GNUPGHOME="$(mktemp -d)"
    export GNUPGHOME
    trap 'rm -rf "$GNUPGHOME"' EXIT
    inicio=$(date +%s)
    marca=$(date -u +%Y%m%dT%H%M%SZ)
    temporal="$DESTINO/.en-curso-$marca"
    final="$DESTINO/altiro-$marca"
    mkdir -p "$temporal"
    PGPASSWORD="$(tr -d '\r\n' < "$ARCHIVO_CLAVE_BD")"
    export PGPASSWORD
    pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc | cifrar "$temporal/base.dump.gpg"
    conteos > "$temporal/conteos.tsv"
    unset PGPASSWORD
    tar --numeric-owner -C "$DIR_FOTOS" -czf - . | cifrar "$temporal/fotos.tar.gz.gpg"
    tar --numeric-owner -C "$DIR_DOCUMENTOS" -cf - . | cifrar "$temporal/documentos.tar.gpg"
    printf 'gpg-simetrico AES256 MDC; clave: volumen de secretos, archivo respaldo_clave (ADR-030, B6)\n' \
        > "$temporal/CIFRADO"
    (cd "$temporal" && sha256sum base.dump.gpg conteos.tsv fotos.tar.gz.gpg documentos.tar.gpg CIFRADO > SHA256SUMS)
    mv "$temporal" "$final"
    registrar INFO "Respaldo terminado: altiro-$marca en $(( $(date +%s) - inicio )) s."
    purgar
}

purgar() {
    # Retención de 7 días (RNF-19): -mtime +N = modificado hace más de N+1 días completos.
    viejos=$((RETENCION_DIAS - 1))
    borrados=$(find "$DESTINO" -mindepth 1 -maxdepth 1 -type d -name 'altiro-*' -mtime "+$viejos" -print \
        -exec rm -rf {} + | wc -l)
    # Restos de un respaldo interrumpido hace más de un día.
    find "$DESTINO" -mindepth 1 -maxdepth 1 -type d -name '.en-curso-*' -mtime +0 -exec rm -rf {} +
    [ "$borrados" -eq 0 ] || registrar INFO "Respaldos con más de $RETENCION_DIAS días eliminados: $borrados."
}

segundos_hasta_la_hora() {
    ahora=$(date +%s)
    objetivo=$(date -d "today $HORA" +%s)
    [ "$objetivo" -gt "$ahora" ] || objetivo=$(date -d "tomorrow $HORA" +%s)
    echo $((objetivo - ahora))
}

bucle() {
    trap 'registrar INFO "Servicio de respaldo detenido."; exit 0' TERM INT
    registrar INFO "Servicio de respaldo iniciado: todos los días a las $HORA (${TZ:-UTC})."
    while true; do
        sleep "$(segundos_hasta_la_hora)" &
        wait $!
        # Proceso aparte: dentro de "||" el shell ignora "set -e" y un pg_dump
        # fallido no detendría el respaldo (con pipefail, tampoco uno en tubería).
        bash "$0" --una-vez || registrar ERROR "El respaldo falló; se reintenta mañana a la misma hora."
    done
}

case "${1:---una-vez}" in
    --bucle) bucle ;;
    --una-vez) hacer_respaldo ;;
    *) echo "Uso: $0 [--bucle | --una-vez]" >&2; exit 2 ;;
esac
