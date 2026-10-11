#!/bin/bash
# QA del pulido post-S5 (v0.6.1). Corre dentro de la imagen de Playwright; lee datos.json (no versionado).
# uso: run.sh script.py [args]
SP="$(cygpath -w "$(dirname "$0")")"
MSYS_NO_PATHCONV=1 docker run --rm --network altiro-dev_frontal -v "$SP:/w" -w /w mcr.microsoft.com/playwright/python:v1.63.0-noble bash -c "python3 -c 'import playwright' 2>/dev/null || pip install -q --break-system-packages playwright==1.63.0 2>&1 | tail -1; python3 /w/$1 ${@:2}"
