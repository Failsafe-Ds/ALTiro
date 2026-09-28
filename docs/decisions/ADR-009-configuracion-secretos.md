# ADR-009 — Configuración y secretos

- Estado: **Aceptada** — 2026-09-27, aprobada por el equipo de desarrollo.
- Fecha: 2026-09-27
- Relacionado con: RNF-19, RNF-23, RNF-24, R-06

## Contexto
RNF-24: "Contraseñas, rutas y ajustes guardados fuera del código, de modo que cambiar de servidor no obligue a reprogramar". RNF-23: "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código".

## Decisión propuesta
- Configuración por variables de entorno y archivos `*_FILE` para secretos.
- Un servicio `init` de una sola ejecución genera secretos aleatorios en un volumen si no existen (idempotente).
- En el repositorio solo va `.env.example`; `.env`, secretos y certificados en `.gitignore`.
- `docker-compose.yml` no depende de que exista `.env`.
- `.gitattributes` con `*.sh text eol=lf`: en Windows, los fines de línea CRLF rompen `generar.sh` y `entrypoint.sh` dentro del contenedor.
- La aplicación no arranca si falta un secreto.
- Comando único: `docker compose up -d --build`.

## Supuestos
- El "equipo limpio" de RNF-23 ya tiene Docker instalado.

## Evidencia de RNF-23
Cronometrar en un equipo limpio incluyendo la descarga de imágenes. Anotar fecha, equipo y tiempo.

## Alternativas consideradas
- **`cp .env.example .env` manual**: rompe "un solo comando".
- **Script `levantar.ps1/.sh`**: aceptable, pero requiere dos variantes por sistema operativo.

## Consecuencias
- Los respaldos de RNF-19 (S5) también quedan fuera del repositorio.
