#!/usr/bin/env bash
# ADR-031: compara la validación en pantalla de RUT y correo (frontend/js/formulario.js)
# con los validadores reales del servidor. Requiere la pila levantada (servicio app)
# y la imagen node:22-alpine. Sin red para Node. Uso, desde la raíz del repositorio:
#   bash scripts/validacion-pantalla/verificar.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
docker compose cp scripts/validacion-pantalla/vectores.py app:/tmp/vectores.py
docker compose exec -T app python -c \
  "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'altiro.settings'); exec(open('/tmp/vectores.py').read())" \
  > "$tmp/vectores.json"
cp scripts/validacion-pantalla/comparar.js "$tmp/"
raiz="$(pwd)"; command -v cygpath >/dev/null && { tmp_m="$(cygpath -w "$tmp")"; raiz="$(cygpath -w "$raiz")"; } || tmp_m="$tmp"
MSYS_NO_PATHCONV=1 docker run --rm --network none -v "$tmp_m:/w:ro" -v "$raiz/frontend:/front:ro" \
  node:22-alpine node /w/comparar.js
