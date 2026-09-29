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
