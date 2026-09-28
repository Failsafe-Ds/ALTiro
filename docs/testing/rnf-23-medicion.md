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
