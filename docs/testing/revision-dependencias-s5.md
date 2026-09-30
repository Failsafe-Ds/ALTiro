# Revisión de dependencias — Sprint 5 (RNF-27)

- Fecha: 2026-09-30 (inicio del S5). Procedimiento: ADR-026 E-10.
- Herramienta: `pip-audit` (última versión en PyPI a la fecha) en un contenedor efímero `python:3.12-slim` (Python 3.12.14). No se agregó a `requirements*.txt`.
- Comando (Git Bash, desde la raíz):
  `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)/backend:/src:ro" python:3.12-slim sh -c "pip install -q pip-audit; pip-audit -r /src/requirements.txt; pip-audit -r /src/requirements-pruebas.txt"`

## Resultado

| Archivo | Resultado |
|---|---|
| `backend/requirements.txt` | No known vulnerabilities found |
| `backend/requirements-pruebas.txt` | No known vulnerabilities found |

Sin acciones. Las versiones siguen fijadas con `==`. La próxima revisión va al inicio del siguiente sprint o antes de la defensa.
