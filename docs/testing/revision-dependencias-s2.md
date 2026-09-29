# Revisión de avisos de seguridad de dependencias — inicio del Sprint 2

- Fecha: 2026-09-28 (ejecución 18:02 UTC).
- Requisito: RNF-27 (dependencias controladas y versionadas); propuesta del S2, §7, paso 0; ADR-015, punto 4.
- Commit revisado: `0e18ec5` (`backend/requirements.txt` y `backend/requirements-pruebas.txt`).
- Ejecutó: agente `backend`.

## Herramienta

- `pip-audit` **2.10.1**, instalado solo en un contenedor efímero (`python:3.13.15-slim-bookworm`, la misma base de la imagen de la aplicación). **No se agregó al proyecto.**
- Fuentes de avisos: servicio de vulnerabilidades de PyPI (por defecto) y, como contraste, la base OSV (`-s osv`).

## Comandos

Desde la raíz del repositorio (Git Bash):

```sh
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)/backend:/b:ro" python:3.13.15-slim-bookworm \
  sh -c "pip install -q pip-audit && pip-audit -r /b/requirements.txt -r /b/requirements-pruebas.txt"
```

Candidatas de ADR-015 (en el mismo contenedor efímero):

```sh
printf 'pillow==12.3.0\ncryptography==50.0.1\n' > /tmp/n.txt
pip-audit -r /b/requirements.txt -r /b/requirements-pruebas.txt -r /tmp/n.txt          # PyPI
pip-audit -s osv -r /b/requirements.txt -r /b/requirements-pruebas.txt -r /tmp/n.txt   # OSV
pip-audit -f json ...                                                                  # detalle por paquete
```

Además se instalaron las candidatas junto con los requisitos actuales para obtener sus dependencias transitivas (`pip install ... && pip check && pip freeze`).

## Resultado por paquete

| Paquete | Versión | Archivo | Avisos (PyPI) | Avisos (OSV) |
|---|---|---|---|---|
| Django | 5.2.17 | requirements.txt | 0 | 0 |
| asgiref | 3.12.1 | requirements.txt | 0 | 0 |
| sqlparse | 0.6.0 | requirements.txt | 0 | 0 |
| psycopg | 3.3.6 | requirements.txt | 0 | 0 |
| psycopg-binary | 3.3.6 | requirements.txt | 0 | 0 |
| gunicorn | 26.2.0 | requirements.txt | 0 | 0 |
| argon2-cffi | 25.1.0 | requirements.txt | 0 | 0 |
| argon2-cffi-bindings | 26.1.0 | requirements.txt | 0 | 0 |
| cffi | 2.1.1 | requirements.txt | 0 | 0 |
| pycparser | 3.0 | requirements.txt | 0 | 0 |
| pytest | 9.1.1 | requirements-pruebas.txt | 0 | 0 |
| pytest-django | 4.14.0 | requirements-pruebas.txt | 0 | 0 |
| time-machine | 3.5.1 | requirements-pruebas.txt | 0 | 0 |
| iniconfig | 2.3.0 | requirements-pruebas.txt | 0 | 0 |
| packaging | 26.3 | requirements-pruebas.txt | 0 (\*) | 0 (\*) |
| pluggy | 1.6.0 | requirements-pruebas.txt | 0 | 0 |
| pygments | 2.21.0 | requirements-pruebas.txt | 0 | 0 |
| **Pillow** (candidata) | **12.3.0** | — (incremento 2) | 0 | 0 |
| **cryptography** (candidata) | **50.0.1** | — (incremento 2) | 0 | 0 |

(\*) `pip-audit` no incluye `packaging` en el informe conjunto porque también es dependencia de su propio entorno de resolución; se auditó por separado (`pip-audit -r` con `packaging==26.3`): sin avisos.

## Versiones elegidas para ADR-015 (no agregadas todavía)

- **Pillow 12.3.0**: última versión publicada en PyPI a la fecha. Sin dependencias obligatorias.
- **cryptography 50.0.1**: última versión publicada en PyPI a la fecha. Su única dependencia en CPython 3.13 es `cffi` (y, a través de ella, `pycparser`), **ya fijadas** en `requirements.txt` (`cffi==2.1.1`, `pycparser==3.0`) por argon2. `pip check` sin conflictos con el conjunto actual.
- No aparecen dependencias transitivas nuevas: `pip freeze` tras instalarlas solo agrega `pillow==12.3.0` y `cryptography==50.0.1`.
- Se agregarán a `backend/requirements.txt` en el incremento 2 (subida segura), con versión exacta.

## Zona horaria (ADR-016, punto 3)

- La imagen base `python:3.13.15-slim-bookworm` trae la base de zonas horarias del sistema (`/usr/share/zoneinfo/America/Santiago`); `zoneinfo.ZoneInfo("America/Santiago")` funciona sin el paquete `tzdata` de PyPI. **No se agrega `tzdata`.**
- Riesgo menor: las reglas de horario de verano dependen del paquete del sistema de la imagen base; se actualizan al actualizar la imagen fijada.

## Avisos encontrados y acción

- **Ningún aviso** conocido en las dependencias actuales ni en las candidatas, con ambas fuentes.
- Acción: ninguna. Repetir esta revisión al agregar Pillow y cryptography (incremento 2) y al cierre del S2.

---

## Re-auditoría al cierre del Sprint 2

- **Fecha:** 2026-09-29 (ejecución 07:25 UTC; 04:25 hora de Chile). Ejecutó: agente `qa` (`docs/testing/cierre-sprint-2.md`).
- **Commit revisado:** `709e7ba` (requisitos idénticos a `fd6449b`). `backend/requirements.txt` ya incluye **Pillow 12.3.0** y **cryptography 50.0.1** con versión exacta.
- **Herramienta:** `pip-audit` 2.10.1 en un contenedor efímero `python:3.13.15-slim-bookworm` (no se agregó al proyecto).

```sh
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)/backend:/b:ro" python:3.13.15-slim-bookworm sh -c \
  "pip install -q pip-audit; pip-audit -r /b/requirements.txt -r /b/requirements-pruebas.txt; \
   pip-audit -s osv -r /b/requirements.txt -r /b/requirements-pruebas.txt; \
   printf 'packaging==26.3\n' > /tmp/p.txt; pip-audit -r /tmp/p.txt"
```

| Fuente | Alcance | Resultado |
|---|---|---|
| PyPI (por defecto) | `requirements.txt` (12 paquetes, con Pillow y cryptography) y `requirements-pruebas.txt` (7) | `No known vulnerabilities found` |
| OSV (`-s osv`) | Ídem | `No known vulnerabilities found` |
| PyPI | `packaging==26.3` por separado (ver nota (\*)) | `No known vulnerabilities found` |

- Todas las librerías siguen con versión exacta (`==`) en ambos archivos (RNF-27, "Cada librería queda declarada con versión exacta").
- **Acción:** ninguna. Próxima revisión: inicio del Sprint 3 (RNF-27: "una revisión de avisos registrada al inicio de cada sprint").
