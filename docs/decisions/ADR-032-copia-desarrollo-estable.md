# ADR-032 — Copia de desarrollo y copia estable en el mismo equipo

- Estado: **Aceptada** — 2026-10-04, decisión del equipo.
- Fecha: 2026-10-04
- Relacionado con: RNF-23 (despliegue con un comando), ADR-008 (proxy y puertos), ADR-009 (configuración por `.env`), ADR-030 (imagen `pruebas`)

## Contexto
- El equipo trabaja con dos copias del repositorio en el mismo equipo:
  - **desarrollo**: la carpeta donde se modifica el código;
  - **estable**: una copia sacada de git, para probar versiones cerradas.
- `docker-compose.yml` fija `name: altiro` y las imágenes construidas (`altiro-init:local`, `altiro-app:local`, `altiro-app-pruebas:local`). Por eso:
  - un `docker compose up` en una carpeta recrea los contenedores de la otra;
  - un `--build` en desarrollo cambia la imagen que la estable usa al recrearse, aunque se use `-p` (también afecta a `altiro-volumen`, `altiro-qa` y `altiro-restauracion`);
  - las dos copias piden los puertos 80 y 443.
- Incidente del 2026-10-04: la copia estable reemplazó los contenedores del proyecto `altiro`. El proxy quedó con la configuración de una versión anterior (con `proxy_pass` fijo) y apuntó a una IP vieja de `app`. Todas las rutas `/api/*` respondieron 502 hasta que se reinició el proxy.

## Decisión
1. El nombre de las imágenes construidas toma el prefijo de `ALTIRO_IMAGEN` (por defecto `altiro`): `${ALTIRO_IMAGEN:-altiro}-app:local`, `-init:local` y `-app-pruebas:local`.
2. La copia **estable** no define nada: sigue siendo el proyecto `altiro`, con las imágenes `altiro-*:local` y los puertos 80/443. No cambia el comando único de RNF-23.
3. La copia de **desarrollo** usa un `.env` local, que no se versiona:
   - `COMPOSE_PROJECT_NAME=altiro-dev` (tiene prioridad sobre `name:`): contenedores y volúmenes `altiro-dev_*`;
   - `ALTIRO_IMAGEN=altiro-dev`;
   - puertos 8080/8443, con `DJANGO_CSRF_TRUSTED_ORIGINS` y `ALTIRO_URL_PUBLICA` en `:8443`;
   - `ALTIRO_RESPALDO_DIR=../altiro-dev-respaldos`, para no mezclar respaldos si las dos carpetas comparten la carpeta padre.
4. Los proyectos de medición (`-p altiro-volumen`, etc.) que se lancen desde desarrollo usan las imágenes `altiro-dev-*`.

## Consecuencias
- Las dos copias pueden estar levantadas al mismo tiempo, cada una con su base y sus documentos.
- `down -v` en una carpeta solo borra los volúmenes de su proyecto. Igual requiere autorización (CLAUDE.md §14).
- La copia de desarrollo parte con una base vacía: hay que volver a cargar los datos demo (`cargar_datos_demo --con-cuentas`).
- `scripts/simulacro-restauracion.sh` lee por defecto los secretos de `altiro_secretos` (copia estable). Para hacer el simulacro con datos de desarrollo, exportar `ALTIRO_RESTAURAR_SECRETOS_VOLUMEN=altiro-dev_secretos`.
- Al reemplazar los archivos de la copia estable, hay que terminar la copia **antes** del `up`, y si hace falta usar `docker compose up -d --force-recreate proxy`. El proxy genera su configuración desde las plantillas montadas solo al arrancar.
