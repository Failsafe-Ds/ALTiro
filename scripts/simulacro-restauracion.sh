#!/usr/bin/env bash
# Simulacro cronometrado de restauración (RNF-19: restauración completa probada
# en 30 minutos o menos; ADR-026, E-7.3). Evidencia: docs/testing/rnf-19-respaldo.md.
#
# Uso (raíz del repositorio):  scripts/simulacro-restauracion.sh [directorio-de-respaldos]
#
# 1. Toma el respaldo más reciente (altiro-*) del directorio (../altiro-respaldos).
# 2. Lo restaura con scripts/restaurar.sh en el proyecto aparte altiro-restauracion
#    (nunca en el principal, CLAUDE.md §14), con los secretos del volumen
#    ALTIRO_RESTAURAR_SECRETOS_VOLUMEN (por defecto altiro_secretos, solo lectura).
# 3. Compara los conteos de filas con conteos.tsv del respaldo.
# 4. Descifra un documento en la app restaurada (solo imprime tamaño y firma JPEG).
# No baja el proyecto de restauración: se baja a mano, ver la evidencia.
set -euo pipefail
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")/.."
DIRECTORIO="${1:-../altiro-respaldos}"
PROYECTO=altiro-restauracion
export ALTIRO_RESTAURAR_SECRETOS_VOLUMEN="${ALTIRO_RESTAURAR_SECRETOS_VOLUMEN:-altiro_secretos}"

ULTIMO="$(ls -1d "$DIRECTORIO"/altiro-* | sort | tail -n 1)"
echo "Respaldo: $(basename "$ULTIMO")"

inicio=$(date +%s)
scripts/restaurar.sh "$ULTIMO" "$PROYECTO"
fin=$(date +%s)
echo "TIEMPO_RESTAURACION_S=$((fin - inicio))"

RESTAURADOS="$(mktemp)"
CONSULTA="SELECT table_name, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
docker compose -p "$PROYECTO" exec -T db sh -c 'psql -X -At -F "$(printf "\t")" -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    <<< "$CONSULTA" | tr -d '\r' > "$RESTAURADOS"
if diff <(tr -d '\r' < "$ULTIMO/conteos.tsv") "$RESTAURADOS" >/dev/null; then
    echo "CONTEOS_IGUALES=si TABLAS=$(wc -l < "$RESTAURADOS") FILAS=$(awk -F '\t' '{s+=$2} END {print s}' "$RESTAURADOS")"
else
    echo "CONTEOS_IGUALES=no"; diff <(tr -d '\r' < "$ULTIMO/conteos.tsv") "$RESTAURADOS" || true
fi

# Descifra todos los documentos (sin imprimir contenido): cuántos se leen y la
# firma JPEG del primero legible. Un documento cuyo archivo ya faltaba en el
# origen también falta aquí; la evidencia compara con el proyecto principal.
docker compose -p "$PROYECTO" exec -T app python manage.py shell -c "
from expediente import almacenamiento
from expediente.models import Documento
legibles, ilegibles, primero = 0, 0, None
for d in Documento.objects.order_by('pk'):
    try:
        contenido = almacenamiento.leer(d.ref, almacenamiento.ANVERSO, d.archivo)
    except almacenamiento.ArchivoIlegible:
        ilegibles += 1
        continue
    legibles += 1
    primero = primero or (len(contenido), contenido[:3] == bytes([0xFF, 0xD8, 0xFF]))
print('DOCUMENTOS_DESCIFRADOS=%d ILEGIBLES=%d PRIMERO_BYTES=%s PRIMERO_JPEG=%s' % (
    legibles, ilegibles, primero and primero[0], primero and primero[1]))
"
echo "TIEMPO_TOTAL_S=$(( $(date +%s) - inicio ))"
