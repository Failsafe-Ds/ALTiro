# RNF-01 — Medición preliminar de la búsqueda (S4, incremento 2)

- **Requisito (informe §4.2.2):** "Al menos 19 de cada 20 búsquedas responden en 2 segundos o menos, con 100 maestros, 1.000 tickets y 10 personas usando el sistema a la vez". Se revisan todos los tiempos, no el promedio (§4.3.2).
- **Estado:** medición **preliminar**. Faltan los 1.000 tickets (llegan con la app `tickets`, S4 incremento 4) y los 5.000 mensajes de RNF-03 (S5). Se repite en el cierre del sprint (propuesta del S4, §9, paso 9).

## Condiciones

| Dato | Valor |
|---|---|
| Fecha | 2026-09-29 |
| Commit | `29fa2c2` más los cambios sin confirmar de los incrementos 1 y 2 del S4 (búsqueda en `backend/busqueda/`) |
| Equipo | AMD Ryzen 7 5700X (8 núcleos, 16 hilos), 31,9 GB de RAM, Windows 11 Pro, Docker Desktop 29.8.0 (16 CPU y 15,56 GiB asignados a Docker) |
| Pila | **Aparte**: `docker compose -p altiro-volumen` con `ALTIRO_HTTP_PORT=8080`, `ALTIRO_HTTPS_PORT=8443` y `DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443`. Gunicorn con 2 workers (valor por defecto) |
| Volumen | `python manage.py generar_volumen_prueba --semilla 42 --confirmo-datos-ficticios`: 100 maestros aprobados y publicados, con foto; 300 servicios publicados (todos visibles según la regla única); cobertura en el Gran Concepción y agenda semanal. **0 tickets** (pendiente) |
| Concurrencia | 10 hilos simultáneos |
| Búsquedas | 400 variadas (oficio no regulado, comuna de la provincia de Concepción, la mitad con bloque horario en los próximos 13 días, 10 % en la página 2), semilla 42, más 10 de calentamiento que no se cuentan |
| Herramienta | `scripts/medir_rnf01.py` (solo biblioteca estándar). Como el equipo no tiene Python, se ejecutó desde la imagen de la app: `docker run --rm -v "<repo>/scripts:/s:ro" --entrypoint python altiro-app:local /s/medir_rnf01.py --base https://host.docker.internal:8443 --cabecera-host localhost --hilos 10 --busquedas 400`. TLS sin verificar solo por el certificado autofirmado local (ADR-008) |

## Resultado

| Indicador | Valor |
|---|---|
| Respuestas distintas de 200 | 0 |
| Proporción en 2 s o menos | **100 %** (400 de 400); exigido: 95 % |
| p95 | **0,168 s** |
| Mediana | 0,152 s |
| Máximo | 0,189 s |
| Duración total | 6,1 s |
| Veredicto preliminar | **Cumple** RNF-01 con el volumen actual (sin tickets) |

Además, la prueba automática `tests/test_busqueda.py::test_paginas_de_veinte_y_consultas_constantes` verifica que una búsqueda hace el mismo número de consultas (13) con 5 y con 50 maestros (`django_assert_max_num_queries`).

## RNF-04 (memoria de la pila) durante la medición

`docker stats --no-stream` cada 2 s sobre los contenedores de `altiro-volumen`. Pico observado:

| Contenedor | Memoria |
|---|---|
| app | 110,6 MiB |
| db | 47,4 MiB |
| planificador | 47,4 MiB |
| proxy | 21,2 MiB |
| **Total** | **≈ 227 MiB** (límite RNF-04: 2 GB) |

## Pendiente

- Repetir con los 1.000 tickets en cuanto exista la app `tickets` (la ocupación de agenda agrega una consulta en lote, `perfil.ocupacion.rangos_ocupados`) y con los 5.000 mensajes en el S5 (RNF-03).
- La pila `altiro-volumen` se detuvo con `docker compose -p altiro-volumen down` **sin** `-v`: sus volúmenes (base con el volumen de prueba) quedan para las mediciones siguientes. Para volver a medir basta el mismo `up -d` con las variables de arriba; el comando de volumen es idempotente por semilla.

## Medición de cierre S4 (con los 1.000 tickets)

Preparado por: agente `qa`, 2026-09-30 (entre las 15:28 y las 15:55, hora de Chile). Reemplaza a la medición preliminar de arriba como evidencia de RNF-01 en el S4.

| Dato | Valor |
|---|---|
| Commit | `f3e4fed` (árbol limpio al iniciar; después solo se agregaron `backend/tests/test_qa_cierre_s4.py` y `scripts/qa-s4/`) |
| Equipo | Igual que arriba (Ryzen 7 5700X, 31,9 GB, Windows 11 Pro, Docker Desktop 29.8.0, 16 CPU y 15,56 GiB para Docker) |
| Pila | `docker compose -p altiro-volumen up -d --build` con los mismos puertos y `DJANGO_CSRF_TRUSTED_ORIGINS`; las migraciones ya estaban aplicadas |
| Volumen | `generar_volumen_prueba --semilla 42 --confirmo-datos-ficticios`: 100 maestros (ya existían), 300 servicios y **1.000 tickets nuevos** (100 aceptados, 277 cerrados, 423 finalizados, 200 pendientes), 200 clientes ficticios. Ver la nota de DEF-QA-005 más abajo |
| Concurrencia y búsquedas | 10 hilos, 400 búsquedas (mismas de arriba, semilla 42) y 10 de calentamiento |
| Herramienta | `scripts/medir_rnf01.py` desde la imagen `altiro-app:local`, igual que arriba |

| Indicador | Valor | Umbral |
|---|---|---|
| Respuestas distintas de 200 | 0 | 0 |
| Proporción en 2 s o menos | **100 %** (400 de 400) | 95 % (19 de cada 20) |
| p95 | **0,179 s** | 2 s |
| Mediana / máximo | 0,163 s / 0,191 s | — |
| Duración total | 6,6 s | — |

**Veredicto RNF-01: cumple** con 100 maestros, 300 servicios, 1.000 tickets y 10 usuarios simultáneos (p95 0,179 s frente a 0,168 s sin tickets: la consulta en lote de ocupación casi no pesa).

**RNF-03:** 100 maestros y 1.000 tickets sostenidos sin degradar RNF-01. Los 5.000 mensajes no existen hasta el S5: `infraestructura preparada / evidencia final pendiente`.

**RNF-04 durante esta medición.** `docker stats --no-stream` cada ~1 s sobre los cuatro contenedores de `altiro-volumen` (25 muestras; la búsqueda duró 6,6 s). Pico por contenedor: app 121,9 MiB, planificador 54,8 MiB, db 36,0 MiB, proxy 22,0 MiB. **Suma de picos ≈ 235 MiB frente a 2 GB: cumple.** (La base creció con 1.000 tickets; la medición es de una pila en reposo más la carga de 10 hilos.)

**Nota de reproducibilidad (DEF-QA-005).** Hoy el comando `generar_volumen_prueba` falla con `ticket_vence_en_formula`: la historia de 30 días cruza el cambio de horario del 6 de septiembre y `calcular_vence_en` usa aritmética de reloj de pared. Para medir, se ejecutó el mismo comando dentro de `manage.py shell` sustituyendo solo `calcular_vence_en` por una versión en UTC (sin tocar el repositorio). El resultado no cambia la medición: la fórmula correcta es la del CHECK de la base.

## Medición S5 (volumen completo, incremento 8, DA-25)

Preparado por: agente `qa`, 2026-09-30 (alrededor de las 17:30, hora de Chile). Es la evidencia vigente de RNF-01: el volumen ya incluye 5.000 mensajes y 417 evaluaciones, y la tarjeta de búsqueda trae la calificación (lote de `evaluaciones/calificacion.py`).

| Dato | Valor |
|---|---|
| Commit | `6757042` más los cambios sin confirmar de este incremento (`generar_volumen_prueba.py`, `tests/test_generar_volumen.py`, `scripts/medir_rnf03_lecturas.py`) |
| Equipo y pila | Igual que arriba (Ryzen 7 5700X, 31,9 GB, Docker Desktop 29.8.0, pila `-p altiro-volumen`, mismos puertos y `DJANGO_CSRF_TRUSTED_ORIGINS`), reconstruida con `up -d --build` |
| Volumen | 100 maestros, 300 servicios, 1.000 tickets (423 finalizados, 100 aceptados, 198 pendientes, 279 cerrados), **5.000 mensajes, 417 evaluaciones** |
| Método | Idéntico al de S4: `scripts/medir_rnf01.py`, 10 hilos, 400 búsquedas (semilla 42) más 10 de calentamiento, desde la imagen `altiro-app:local` |

| Corrida | No 200 | En 2 s o menos | p95 | Mediana | Máximo | Duración |
|---|---|---|---|---|---|---|
| 1 | 0 | **100 %** (400 de 400) | 0,216 s | 0,184 s | 0,251 s | 7,4 s |
| 2 | 0 | **100 %** (400 de 400) | 0,214 s | 0,182 s | 0,269 s | 7,5 s |

Umbral (informe §4.2.2): al menos 19 de cada 20 (95 %) en 2 s o menos. **Veredicto: cumple** con el volumen completo de RNF-03. Frente al cierre del S4 (p95 0,179 s) la búsqueda sube unos 0,035 s por la calificación en la tarjeta; sigue a un décimo del umbral.

Otras lecturas con el mismo volumen (10 hilos, 200 lecturas cada una, `scripts/medir_rnf03_lecturas.py`, sesión ficticia creada en la base de la pila):

| Lectura | p95 | Mediana | Máximo | Respuesta |
|---|---|---|---|---|
| `GET /api/tickets/<ref>/mensajes` de la conversación más larga (23 mensajes; promedio 9,6, máximo 23) | 0,079 s | 0,068 s | 0,091 s | 4.018 bytes |
| Ficha pública del maestro con más evaluaciones (6 del cliente) | 0,198 s | 0,181 s | 0,206 s | 2.867 bytes |

Sin respuestas distintas de 200 y todo en 2 s o menos. **Paginación del GET de mensajes:** con este volumen no importa (máximo 23 mensajes, 4 KB, 0,09 s). El tope de 1.000 caracteres por mensaje acota la respuesta, pero no el número de mensajes: si una conversación real creciera a cientos, conviene paginar. Se deja como observación, no como defecto (el informe no fija umbral para esta lectura).

RNF-04 durante las corridas (`docker stats`, 14 muestras): picos app 113,5 MiB, planificador 49,1 MiB, db 37,4 MiB, proxy 21,6 MiB, respaldo 0,8 MiB; suma ≈ 222 MiB frente a 2 GB: cumple.
