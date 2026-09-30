# RNF-03 — Capacidad con el volumen de prueba (S5, incremento 8)

- **Requisito (informe §4.2.2):** "El sistema debe sostener el volumen de prueba sin degradar RNF-01". Umbral: 100 maestros, 1.000 tickets y 5.000 mensajes (CLAUDE.md §3 agrega 300 servicios publicados).
- **Preparado por:** agente `qa`, 2026-09-30. Datos solo ficticios (cuentas con contraseña inutilizable).

## Conteos medidos en la base (pila `altiro-volumen`)

| Tabla | Filas | Exigido |
|---|---|---|
| `perfil_maestro` | 100 | 100 |
| `servicio_maestro` (activos) | 300 | 300 |
| `ticket` | 1.000 (423 finalizados, 100 aceptados, 198 pendientes, 279 cerrados) | 1.000 |
| `mensaje` | 5.000 (50 por maestro; 9,6 por ticket en promedio, máximo 23) | 5.000 |
| `evaluacion` | 417 (parte de los 423 finalizados) | sin cifra |
| `ticket_evento` | 2.225 | — |

Tamaño de la base: 13 MB. Los 198 pendientes vs. 200 del S4 se deben a que el planificador cerró dos por vencimiento.

## Resultado

- RNF-01 con el volumen completo: 100 % de 400 búsquedas en 2 s o menos, p95 0,214 a 0,216 s (dos corridas). Detalle en `rnf-01-medicion.md`, sección S5.
- Lecturas de conversación (p95 0,079 s) y de ficha pública (p95 0,198 s) sin problemas.
- Recursos (RNF-04, límite de 2 GB): suma de picos ≈ 222 MiB.
- **Veredicto RNF-03: cumple** con el volumen de prueba, en el equipo indicado y con 10 usuarios simultáneos.

## Cómo reproducir

1. Pila aparte (nunca la de la demostración):
   `ALTIRO_HTTP_PORT=8080 ALTIRO_HTTPS_PORT=8443 DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost:8443,https://127.0.0.1:8443 docker compose -p altiro-volumen up -d --build`
2. `docker compose -p altiro-volumen exec app python manage.py generar_volumen_prueba --semilla 42 --confirmo-datos-ficticios`. Es idempotente por partes: maestros por RUT, tickets si los clientes de la semilla no tienen, mensajes y evaluaciones si esos tickets no tienen. Sobre una pila con los 1.000 tickets del S4 solo agrega mensajes y evaluaciones.
3. Búsqueda: `scripts/medir_rnf01.py` (comando en `rnf-01-medicion.md`). Lecturas: `scripts/medir_rnf03_lecturas.py` con una sesión ficticia creada con `SessionStore` (`_usuario_id` y `_usuario_hash`).
4. Prueba automática del comando: `tests/test_generar_volumen.py` (incluye mensajes y evaluaciones válidos e idempotencia).

## Observaciones

- El GET de mensajes no pagina: aceptable con este volumen; revisar si las conversaciones reales crecen.
- DEF-QA-005 (generación de tickets con el cambio de horario) no se reprodujo porque los tickets ya existían; sigue pendiente de confirmar en una pila vacía.
