# Medición de RNF-23 — instalación con un solo comando

- **Fecha:** 2026-09-28 (17:39 a 17:41 UTC).
- **Requisito:** RNF-23. Umbral: "Un solo comando deja el sistema andando en 10 minutos o menos, con las instrucciones escritas junto al código".
- **Resultado: PASS, 47 segundos**, medido en un motor Docker limpio aislado (ver «Validez de la medición»).
- **Versión medida:** commit `5517b5d` (rama `main`).

## Método

La medición se hizo en este mismo equipo, sin tocar las imágenes ni los volúmenes del motor Docker del equipo:

1. Se levantó un motor Docker **vacío** dentro de un contenedor, con la imagen oficial `docker:29-dind` (motor 29.8.1, Docker Compose v5.5.1): **0 imágenes y 0 volúmenes** al comenzar. La descarga de `docker:dind` es parte del equipo de prueba y no se cuenta.
2. Se copió el repositorio en el commit medido con `git archive HEAD`, equivalente a un `git clone`: solo archivos versionados, con los fines de línea de `.gitattributes`.
3. Se ejecutó el único comando del README, `docker compose up -d --build`, **sin `.env`**.
4. El cronómetro se detuvo cuando `https://127.0.0.1/api/health/`, a través del proxy Nginx, respondió `{"estado": "ok", "base_datos": "ok"}`.
5. El contenedor de prueba y su volumen anónimo se eliminaron al terminar.

## Resultado

| Dato | Valor |
|---|---|
| Código de salida de `docker compose up -d --build` | 0 |
| Tiempo total, descargas y construcción incluidas | **47 s** (umbral: 600 s) |
| Salud a través de HTTPS | `{"estado": "ok", "base_datos": "ok"}` |
| Estado final | `app`, `db` y `proxy` healthy; `init` terminó correctamente |
| Frontend | `GET https://127.0.0.1/` → 200 |
| Imágenes descargadas o construidas | `postgres:16.15-bookworm` (622 MB), `altiro-app:local` (297 MB), `nginx:1.30.5-alpine` (93,6 MB), `altiro-init:local` (14,2 MB) |

Equipo: Windows 11 Pro 10.0.26200, Docker Desktop (motor 29.8.0 en el equipo), 16 CPU y 15,6 GiB de memoria asignada a Docker. Conexión: la red doméstica del equipo de desarrollo (sin medición de ancho de banda).

## Validez de la medición

- **Qué cumple:** motor sin caché de imágenes ni volúmenes, repositorio tal como se versiona, sin `.env`, un solo comando, e instrucciones en el README (RNF-23, "con las instrucciones escritas junto al código").
- **Qué no cumple:** no es otro equipo físico. Comparte CPU, disco y red con el equipo de desarrollo. El ancho de banda domina el tiempo: con 1,03 GB de imágenes, el umbral de 10 minutos se cumpliría hasta con unos 15 Mbit/s sostenidos (estimación, no medición).
- **Recomendación:** confirmar en un equipo del laboratorio con el procedimiento de `cierre-sprint-1.md` §7 antes de la revisión del sprint, y registrar ahí el resultado. Esta medición cierra DA-11 como evidencia del equipo de desarrollo, no como confirmación en el entorno de la contraparte.

---

## Nueva medición al cierre del Sprint 2 (con el servicio `planificador`)

- **Fecha:** 2026-09-29 (07:29:20 a 07:30:03 UTC; 04:29 hora de Chile). Ejecutó: agente `qa`, cierre del Sprint 2 (`docs/testing/cierre-sprint-2.md`).
- **Motivo:** ADR-016 y DA-16 agregan un contenedor (`planificador`) y dos dependencias (Pillow y cryptography); había que volver a medir.
- **Versión medida:** commit `709e7ba` (rama `main`). Su código es idéntico al de `fd6449b` (cierre de UX del S2): `709e7ba` solo agrega documentos del Sprint 3.
- **Resultado: PASS, 43 segundos** (umbral: 600 s).

### Método
El mismo de la medición anterior:
1. Motor Docker vacío en un contenedor `docker:29-dind` (`qa-rnf23-s2`; motor 29.8.1, Docker Compose 5.5.1), con **0 imágenes y 0 volúmenes** al comenzar.
2. Repositorio copiado con `git archive HEAD` (solo archivos versionados), **sin `.env`**.
3. Un solo comando, `docker compose up -d --build`, cronometrado desde su inicio.
4. El cronómetro se detuvo cuando `https://127.0.0.1/api/health/`, a través de Nginx, respondió `{"estado": "ok", "base_datos": "ok"}`.
5. Al terminar se eliminaron **solo** el contenedor `qa-rnf23-s2` y su volumen anónimo (`/var/lib/docker`, creado a las 07:28:56 UTC, etiqueta `com.docker.volume.anonymous`), comprobando antes que el id del contenedor era el lanzado para la prueba. No se tocó ninguna imagen ni volumen del motor del equipo.

### Resultado

| Dato | Valor |
|---|---|
| Código de salida de `docker compose up -d --build` | 0 |
| Tiempo hasta salud por HTTPS, descargas y construcción incluidas | **43 s** |
| Salud a través de HTTPS | `{"estado": "ok", "base_datos": "ok"}` |
| Estado a los 50 s | `app`, `db`, `proxy` y `planificador` healthy; `init` terminó con código 0 |
| Primera corrida del planificador | `avisos_creados=0 accesos_denegados_purgados=0 archivos_huerfanos_borrados=0 tareas_fallidas=0` |
| Frontend | `GET https://127.0.0.1/` → 200 |
| Imágenes | `postgres:16.15-bookworm` (622 MB), `altiro-app:local` (348 MB, antes 297 MB: Pillow y cryptography), `nginx:1.30.5-alpine` (93,6 MB), `altiro-init:local` (14,2 MB) |

Equipo: el mismo (Windows 11 Pro 10.0.26200, Docker Desktop con motor 29.8.0, 16 CPU, 15,56 GiB para Docker), red doméstica sin medición de ancho de banda.

### Validez
Mismas limitaciones que la medición anterior: no es otro equipo físico y el tiempo depende del ancho de banda (unos 1,08 GB de imágenes). El planificador no alarga el arranque de forma apreciable (usa la misma imagen que `app`). Sigue recomendado confirmar en un equipo del laboratorio.

---

## Nueva medición al cierre del Sprint 3 (catálogo, perfil, fotos y búsqueda)

- **Fecha:** 2026-09-29 (18:04:20 a 18:05:04 UTC; 15:04 hora de Chile). Ejecutó: agente `qa`, cierre del Sprint 3 (`docs/testing/cierre-sprint-3.md`).
- **Motivo:** el S3 agrega el volumen `fotos`, rutas nuevas en el proxy y migraciones de `catalogo` y `perfil`; el commit incluye además la búsqueda del S4 (incrementos 1 y 2), con la migración `perfil.0004_indices_busqueda`. No hay dependencias nuevas.
- **Versión medida:** commit `3c5d357` (rama `main`). En el equipo había cambios sin commit en `frontend/` (trabajo en curso de otro agente); `git archive HEAD` los excluye, así que la medición corresponde exactamente al commit.
- **Resultado: PASS, 44 segundos** (umbral: 600 s).

### Método
El mismo de las mediciones anteriores:
1. Motor Docker vacío en un contenedor `docker:29-dind` (`qa-rnf23-s3`, id `8c2cbbd74cda…`; motor 29.8.1, Docker Compose 5.5.1), con **0 imágenes, 0 volúmenes y 0 contenedores** al comenzar. Dentro del contenedor se instaló `curl` antes de empezar a cronometrar (herramienta de medición, no del sistema).
2. Repositorio copiado con `git archive HEAD` (solo archivos versionados), **sin `.env`** (comprobado).
3. Un solo comando, `docker compose up -d --build`, cronometrado desde su inicio.
4. El cronómetro se detuvo cuando `https://127.0.0.1/api/health/`, a través de Nginx, respondió `{"estado": "ok", "base_datos": "ok"}`.
5. Antes de borrar, la misma pila limpia se usó para repetir las pruebas de interfaz del cierre sobre el código exacto del commit (ver `cierre-sprint-3.md`, §3.3).
6. Al terminar se eliminaron **solo** el contenedor `qa-rnf23-s3` (id comprobado contra el guardado al crearlo) y su volumen anónimo `fda7bcb0864e…` (creado a las 18:03:46 UTC, etiqueta `com.docker.volume.anonymous`). No se tocó ninguna imagen ni volumen del motor del equipo (`altiro_*` y `altiro-volumen_*` siguen presentes).

### Resultado

| Dato | Valor |
|---|---|
| Código de salida de `docker compose up -d --build` | 0 (el comando terminó a los 44 s) |
| Tiempo hasta salud por HTTPS, descargas y construcción incluidas | **44 s** |
| Salud a través de HTTPS | `{"estado": "ok", "base_datos": "ok"}` |
| Estado a los 54 s | `app`, `db`, `proxy` y `planificador` healthy; `init` terminó con código 0 |
| Primera corrida del planificador | `avisos_creados=0 accesos_denegados_purgados=0 archivos_huerfanos_borrados=0 tareas_fallidas=0` |
| Frontend | `GET https://127.0.0.1/` → 200 |
| Catálogo inicial | `GET /api/oficios`: los 8 oficios provisionales (P-01). `GET /api/catalogo`: oficios **sin servicios** (P-17: los servicios los crea comercial; `cargar_datos_demo` los carga para la demostración, 15 servicios) |
| Imágenes | `postgres:16.15-bookworm` (622 MB), `altiro-app:local` (349 MB), `nginx:1.30.5-alpine` (93,6 MB), `altiro-init:local` (14,2 MB) |

Equipo: el mismo (Windows 11 Pro 10.0.26200, Docker Desktop con motor 29.8.0, 16 CPU, 15,56 GiB para Docker), red doméstica sin medición de ancho de banda.

### Validez
Mismas limitaciones que las mediciones anteriores: no es otro equipo físico y el tiempo depende del ancho de banda (unos 1,08 GB de imágenes). Sigue recomendado confirmar en un equipo del laboratorio. Observación: el `README.md` no menciona `cargar_datos_demo`, así que una instalación limpia no tiene servicios en el catálogo hasta que comercial los cree (ver OBS-S3-03 en `cierre-sprint-3.md`).
