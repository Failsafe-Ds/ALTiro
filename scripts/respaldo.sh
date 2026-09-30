#!/bin/sh
# Respaldo diario de AlTiro (RNF-19; ADR-026, E-7; R-04).
#
# Corre dentro del servicio "respaldo" (imagen postgres:16, sin imágenes nuevas):
#   altiro-respaldo.sh --bucle    # servicio: espera la hora ALTIRO_RESPALDO_HORA cada día
#   altiro-respaldo.sh --una-vez  # un respaldo ahora (operación manual o simulacro):
#       docker compose exec respaldo sh /usr/local/bin/altiro-respaldo.sh --una-vez
#
# Cada respaldo es un directorio  $DESTINO/altiro-AAAAMMDDTHHMMSSZ/  con:
#   base.dump        pg_dump -Fc de la base
#   conteos.tsv      filas por tabla justo después del volcado (para el simulacro)
#   fotos.tar.gz     volumen "fotos"
#   documentos.tar   volumen "documentos" (ya cifrado con AES-256-GCM; ADR-015)
#   SHA256SUMS       sumas de verificación
# Se escribe en un directorio temporal y se renombra al terminar: un respaldo
# a medias nunca parece completo. Se eliminan los de más de
# ALTIRO_RESPALDO_RETENCION_DIAS días (7 por defecto).
#
# Seguridad (ADR-026, E-7.2, enmienda a ADR-015):
# - "documentos" y "fotos" se montan de solo lectura; este contenedor solo ve
#   texto cifrado. La clave de cifrado NO se monta aquí: se respalda aparte.
# - Solo se monta la contraseña del rol administrativo (un archivo del volumen
#   de secretos). Nunca se imprime.
set -eu

DESTINO="${ALTIRO_RESPALDO_DESTINO:-/respaldos}"
HORA="${ALTIRO_RESPALDO_HORA:-03:00}"
RETENCION_DIAS="${ALTIRO_RESPALDO_RETENCION_DIAS:-7}"
ARCHIVO_CLAVE_BD="${ALTIRO_RESPALDO_DB_PASSWORD_FILE:-/run/secretos/db_admin_password}"
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

hacer_respaldo() {
    inicio=$(date +%s)
    marca=$(date -u +%Y%m%dT%H%M%SZ)
    temporal="$DESTINO/.en-curso-$marca"
    final="$DESTINO/altiro-$marca"
    mkdir -p "$temporal"
    PGPASSWORD="$(tr -d '\r\n' < "$ARCHIVO_CLAVE_BD")"
    export PGPASSWORD
    pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$temporal/base.dump"
    conteos > "$temporal/conteos.tsv"
    unset PGPASSWORD
    tar --numeric-owner -C "$DIR_FOTOS" -czf "$temporal/fotos.tar.gz" .
    tar --numeric-owner -C "$DIR_DOCUMENTOS" -cf "$temporal/documentos.tar" .
    (cd "$temporal" && sha256sum base.dump conteos.tsv fotos.tar.gz documentos.tar > SHA256SUMS)
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
        # fallido no detendría el respaldo.
        sh "$0" --una-vez || registrar ERROR "El respaldo falló; se reintenta mañana a la misma hora."
    done
}

case "${1:---una-vez}" in
    --bucle) bucle ;;
    --una-vez) hacer_respaldo ;;
    *) echo "Uso: $0 [--bucle | --una-vez]" >&2; exit 2 ;;
esac
