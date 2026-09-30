# Verificación de cierre — Sprint 4 (búsqueda y ticket)

- Fecha: **2026-09-30** (15:20 a 16:10, hora de Chile). Preparado por: agente `qa`.
- Código: `main`, commit `f3e4fed` (árbol limpio al iniciar). QA agregó `backend/tests/test_qa_cierre_s4.py` y `scripts/qa-s4/` (sin commit).
- Fuentes: `docs/estado-actual.md`; propuesta del S4 §1, §7, §9, §10; informe (RF-09 a RF-24, RNF-01 a 04, 14 a 18 y 21, CA-02 a 06, 14.3, 23, 25); ADR-022, 023 y 024 (provisionales). El incremento 7 ya tiene su QA: `qa-s4-incremento-7.md` (se cita, no se repite).
- Suite completa: la corre el coordinador. QA corrió solo `-m regla` (134 pasan) y `test_generar_volumen` (4 pasan).

**Veredicto: listo con observaciones.** El incremento "buscar, pedir, aceptar o rechazar y cierre" funciona de extremo a extremo en la pila normal y cumple los umbrales medidos. Hay dos defectos medios (DEF-QA-005, en producción, en un borde de horario de verano; DEF-QA-006, bitácora de alcance sin los registros del S4) y evidencia pendiente que pasa al S5.

## 1. Mediciones (RNF-01 a RNF-04 y RNF-21)

| RNF | Método y entorno | Resultado | Umbral | Estado |
|---|---|---|---|---|
| RNF-01 | `scripts/medir_rnf01.py`, 10 hilos, 400 búsquedas, pila `altiro-volumen` con 100 maestros, 300 servicios y **1.000 tickets**; detalle en `rnf-01-medicion.md` ("Medición de cierre S4") | 100 % en 2 s o menos; p95 0,179 s; máximo 0,191 s; 0 respuestas distintas de 200 | 95 % en 2 s | **PASS** |
| RNF-02 | Playwright/CDP 4/1 Mbps, 150 ms (D-19), Chromium 153, 5 corridas; `rnf-02-medicion.md` §4 | buscar 0,567 s máx., 35,8 KiB; ficha 0,535 s máx., 17,8 KiB | 3 s y 1,5 MB | **PASS** |
| RNF-03 | Mismo volumen | 100 maestros y 1.000 tickets sin degradar RNF-01; faltan 5.000 mensajes (S5) | volumen completo | **BLOCKED**: infraestructura preparada / evidencia final pendiente (S5) |
| RNF-04 | `docker stats` de la pila aparte durante RNF-01 (25 muestras) | suma de picos ≈ 235 MiB (app 122, planificador 55, db 36, proxy 22) | 2 GB | **PASS** |
| RNF-21 | `backend/tests/reglas_rnf21.py` contra los `@pytest.mark.regla` (cálculo independiente por script) y corrida `-m regla`: 134 pasan | filtros 14/14, puntaje 11/11, cierre 8/8, acceso 5/5 (38/38, 100 %); ningún id marcado fuera del catálogo | 60 % por grupo | **PASS** |

Notas: (a) el generador de volumen falla hoy por DEF-QA-005; se ejecutó con `calcular_vence_en` sustituida en memoria (ver `rnf-01-medicion.md`). (b) RNF-21 mide reglas catalogadas, no líneas; el grupo "acceso" tiene solo 5 reglas (A-01 a A-05), el resto del control de acceso se acumula en RNF-07 (DA-03). (c) Las mediciones son en un solo equipo y Chromium, no en un teléfono.

## 2. Interfaz (RNF-14 a RNF-18) en las pantallas nuevas del S4

Script `scripts/qa-s4/ui.py`: Chromium (153 y 151) y Firefox (155 y 153), a 320 px y 390 px, en 6 estados (buscar inicial, con resultados, sin resultados con sugerencias, sin resultados sin sugerencias, ficha con horarios, ficha inexistente): 24 combinaciones por versión.

| RNF | Evidencia | Estado |
|---|---|---|
| RNF-14 | Sin objetivo táctil menor de 44 × 44 px en los 6 estados (los únicos de 28 × 28 px son los radios de «¿Qué servicio necesitas?» de la ficha, dentro de `label.casilla-grande` de 56 px). `buscar.html`: paso 1 con 3 campos y paso 2 con fecha y dos horas (5 selectores); ficha: servicio y horario | **PASS** |
| RNF-15 | Validación vacía: "Elige el oficio que necesitas." y "Elige la comuna donde necesitas el trabajo." con foco en el primer campo; API de búsqueda con 7 entradas inválidas responde mensajes por campo sin códigos (p. ej. "Elige una hora en punto o y media"). Ficha inexistente: "No encontramos este perfil…" | **PASS** |
| RNF-16 | Contraste calculado en el navegador sobre todos los pares texto/fondo visibles (buscar ×4 estados y ficha): mínimo 5,66:1 (umbral 4,5:1), ningún par bajo el umbral. Estados con texto además de color: "✓ Libre" / "✕ Ocupado" (borde punteado), "⚠ No cumple: …". axe-core 4.10.3 (WCAG 2.0, 2.1 y 2.2 AA): 0 violaciones en buscar (inicial, paso "cuándo", sugerencias) y ficha | **PASS** |
| RNF-17 | Barrido de palabras técnicas (ticket, API, JSON, HTTP, token, código, sesión, bloque, números de estado) sobre el texto visible de los 6 estados: 0 coincidencias. La pantalla dice "horario" y "pedido" (ADR-024) | **PASS** |
| RNF-18 | Sin desplazamiento lateral ni elemento fuera de pantalla, y 0 errores de JavaScript, en los 4 motores a 320 y 390 px. Falta el pase manual en navegadores de marca y en Chrome de Android | **PASS** (automático); **BLOCKED** (pase manual, sin equipo) |

`pedir-trabajo`, `mis-pedidos` y `mis-trabajos`: evidencia de RNF-14 (objetivos de 44 px, pasos de 0 a 2 campos), RNF-17, axe (0 violaciones) y 360 px en `qa-s4-incremento-7.md` (el script de cierre no los repite).

## 3. Recorrido de extremo a extremo (pila normal, `https://localhost`)

Datos ficticios creados en la pila normal: 1 maestro con agenda (jueves a domingo), 2 clientes y 6 tickets (`scripts/qa-s4/e2e_pila_normal.py` por HTTP real con CSRF, más `cierre_simulado.py`). El cierre por tiempo usó `transiciones.cerrar_vencidos(ahora=...)` sin cambiar el reloj del sistema.

| Paso | Resultado |
|---|---|
| Buscar (oficio + comuna) | 200; el maestro de prueba aparece entre 18 resultados |
| Ficha | 200; 10 horarios de los próximos 14 días, estado `libre` |
| Pedir (6 pedidos de 2 clientes) | Creados `pendiente`; repetir el mismo pedido responde 200 sin duplicar (D-10); un horario a menos de 4 horas responde 409 |
| Maestro, pendiente | Bandeja y detalle sin dirección, teléfono, nombre ni correo del cliente (RNF-08, RF-17) |
| Terceros | Cliente B sobre el ticket de A: 404 al leer y al cancelar; ticket inexistente 404; anónimo 401; cliente que intenta aceptar 403. Los de ticket ajeno y parte equivocada quedan en `acceso_denegado` |
| Aceptar T1 | 200 `aceptado`; el maestro ahora ve dirección y teléfono (contacto solo tras aceptar); T2 del mismo horario queda `cerrado` por `bloque_tomado` y su cliente recibe aviso con `enlace` (CA-23.5) |
| Pedir el horario ocupado | 409 "Ese horario ya no está libre…" con 9 horarios libres (CA-06.2) |
| Búsqueda por ese horario | El maestro deja de aparecer (CA-14.3); con el horario del ticket rechazado sigue apareciendo (RF-20) |
| Rechazar / cancelar | T3 `cerrado` por `rechazado_maestro`; T4 `cerrado` por `cancelado_cliente`; aceptar T4 después responde 409 accionable (CA-23.3) |
| Cierre automático | T6 (horario a menos de 28 h): `vencido_proximidad` a `inicio − 4 h`; T5: `vencido_plazo` a `enviado + 24 h`; ambos con evento de autor `sistema` y aviso a las dos partes. La fórmula `vence_en` coincide con el CHECK. El borde de un segundo antes y el de las 28 horas exactas lo cubren las pruebas marcadas C-xx, no este recorrido |

Registros: sin dirección, teléfono, correo, contraseña, cookie ni RUT en los logs de `app`, `proxy`, `planificador` ni de la pila aparte (0 coincidencias en 3 h).

## 4. Resultado por RF, CA y RNF del S4

| Elemento | Estado | Evidencia |
|---|---|---|
| RF-06 (sin comuna base no aparece), CA-13.2 | PASS | F-05, F-06; cierra DA-20 en esa parte |
| RF-09, CA-02.1 a 02.4 | PASS | F-01 a F-04, F-12, F-13; RNF-01 sobre el volumen |
| RF-10, CA-03.1, 03.2, 03.4 | PASS | P-01 a P-11 |
| RF-11, CA-03.3 | BLOCKED | mecanismo listo, sin evaluaciones (S5) |
| RF-12, CA-04.1 a 04.3 | PASS | navegador: sin resultados → "No encontramos maestros con esos criterios…"; sección "Sugerencias: no cumplen todo lo que pediste"; 5 tarjetas con "No cumple: No tiene libre el horario que elegiste."; foco en el título de resultados |
| RF-13, CA-05.2 | PASS | tarjeta y ficha: "Todavía no tiene evaluaciones" |
| RF-13 (calificación), RF-14 (calificaciones), CA-05.1 | BLOCKED | dimensiones y comentarios en S5 |
| RF-14 (horarios libres y ocupados), CA-14.3 | PASS | ficha "✓ Libre / ✕ Ocupado"; ocupado sin botón; la búsqueda lo excluye |
| RF-15, CA-06.1, 06.3, 06.4 | PASS | pruebas de tickets e incremento 7; aviso `ticket_nuevo` al maestro |
| RF-16 (4 horas) | PASS con DEF-QA-005 | el 409 funciona; falla el borde del horario de verano (§5) |
| RF-17 | PASS | sin datos del cliente en bandeja ni detalle mientras está pendiente |
| RF-18 | PASS | aviso dentro de la aplicación |
| RF-19, RF-20, CA-23.4, 23.5 | PASS | §3 |
| RF-21, RF-22, RF-24, CA-23.1, 23.2, 23.6, 23.7 | PASS | §3 y pruebas C-xx; cinco motivos distinguibles: plazo, proximidad, cancelación, rechazo, bloque tomado |
| RF-23, CA-23.3 | PASS | §3 |
| CA-06.2 | PASS | 409 con horarios libres; el enlace directo a cada horario queda como texto (pendiente del representante, incremento 7) |
| CA-25.1 | PASS | 404 idéntico y registro en `acceso_denegado` |
| CA-25.3 | PASS (provisional) | el registro incluye usuario, recurso y fecha; la semántica sigue en DA-04 |
| RNF-07, RNF-08, RNF-25 (búsqueda) | PASS | §3; `test_rnf25_*` (recorre `/api/busqueda`); control de rutas (lo corre el coordinador) |
| RNF-14 a RNF-18 | PASS (pase manual de RNF-18 BLOCKED) | §2 |
| RNF-01, 02, 04, 21 | PASS | §1 |
| RNF-03 | BLOCKED | §1 |
| RNF-13 | BLOCKED | sin ejecutar (requiere personas) |
| Mensajería, evaluación, precio final, indicadores | NOT IN SCOPE | S5 |

## 5. Defectos

- **DEF-QA-005 (media). Un pedido para un horario justo después del cambio de horario de verano da error 500.** RF-15, RF-16, RF-21/22; ADR-023 punto 1; ADR-020 ("los plazos se miden en tiempo real").
  - Precondición: maestro con un bloque entre las 00:00 y las 04:00 del día del cambio (o del cambio de abril), y pedido enviado con menos de 28 horas de anticipación.
  - Pasos: reloj del sábado 5/9/2026 21:00 (Santiago); maestro con bloque del domingo 6/9 03:00 a 05:00; POST `/api/tickets`.
  - Esperado: 201 con `vence_en = LEAST(enviado + 24 h, inicio − 4 h)` en tiempo transcurrido (02:00 UTC).
  - Observado: 500 (`IntegrityError` en `ticket_vence_en_formula`). `calcular_vence_en` resta 4 horas a `inicio_en`, que trae zona America/Santiago, y `datetime` hace aritmética de reloj de pared: da 03:00 UTC, una hora de más.
  - Evidencia: `backend/tests/test_qa_cierre_s4.py::test_def_qa_005_…` (xfail estricta; con `--runxfail` muestra el `IntegrityError`).
  - También hace fallar `generar_volumen_prueba` cuando su ventana de 30 días cruza un cambio de horario (hoy, por el del 6/9): RNF-01 y RNF-03 no se reproducen sin parche.
  - Área: backend (`backend/tickets/servicios.py`, `calcular_vence_en`: convertir ambos instantes a UTC antes de sumar y restar; quitar la marca xfail al corregir). `transiciones.py` línea 79 es correcta porque lee de la base en UTC.
- **DEF-QA-006 (media). La bitácora de alcance no tiene los registros del S4.** CLAUDE.md §11, propuesta del S4 §10. Faltan las entradas con fecha, motivo y autorización para: adelanto parcial de RF-28 (lista de pedidos); paso al S5 de RF-11 y CA-03.3, de la calificación de RF-13 y RF-14, de CA-15.2 y de RNF-03 con mensajes; y el cierre de DA-13, DA-14 (parte S4) y DA-20 (evidencia en §4). DA-03 tampoco tiene avance anotado. Área: coordinador o representante (documentación).
- Sigue abierto el **DEF-QA-012 del S3** (DA-17, RNF-13): el plazo era "antes de la revisión del S4", que es ahora.

## 6. Observaciones

- OBS-S4-01: las sugerencias se limitan a 5 tarjetas; conviene confirmarlo con el representante (ADR-022).
- OBS-S4-02: la medición de RNF-02 es en Chromium; Playwright no emula red en Firefox.
- OBS-S4-03: los datos ficticios del recorrido (maestro "QA Cierre S4 884", 2 clientes, 6 tickets) quedan en la pila normal; no se borraron por la regla de no tocar volúmenes.
- OBS-S4-04: siguen abiertos OBS-S3-02, OBS-S3-04, OBS-S3-05 y las dos preguntas del incremento 7 (horarios alternativos del 409 como enlace; "Ingresar" desde `pedir-trabajo` sin retorno).

## 7. Pasa al S5

RF-11 y CA-03.3 (desempate), calificación de RF-13/RF-14 y CA-05.1, conversación de CA-15.2, RNF-03 con 5.000 mensajes y nueva medición de RNF-01, RNF-13, pase manual de RNF-18 y las entradas de la bitácora de alcance (DEF-QA-006). Corregir DEF-QA-005 antes de la próxima fecha de cambio de horario y antes de volver a generar el volumen de prueba.

## 8. Cómo repetir

`scripts/qa-s4/`: `rnf02.py` y `run02.sh` (RNF-02), `ui.py` y `runui.sh` (RNF-14 y RNF-18, y textos), `ctr.py` (contraste), `flujo.py` (CA-04 y axe), `e2e_pila_normal.py` y `cierre_simulado.py` (recorrido; se ejecutan dentro de `altiro-app-1`). Los de navegador corren en `mcr.microsoft.com/playwright/python:v1.63.0-noble`, en la red `altiro-volumen_frontal`, con `pip install playwright==1.63.0` dentro del contenedor.

## Correcciones posteriores al QA (coordinador, 2026-09-30)
- **DEF-QA-005 — corregido.** `tickets/servicios.py::calcular_vence_en` convierte ambos instantes a UTC antes de sumar y restar; `transiciones.motivo_vencimiento` y `generar_volumen_prueba` comparan la proximidad también en UTC (se mantiene el borde de CA-23.6: a las 28 h exactas gana la proximidad). `test_def_qa_005_*` deja de ser `xfail` y queda como regla C-08.
- **DEF-QA-006 — corregido.** Registros DA-22 a DA-26 en `docs/alcance/bitacora-de-alcance.md` y cierre de DA-13, DA-14 (parte búsqueda) y DA-20.
- **DEF-QA-012 del S3 (RNF-13)** sigue abierto: DA-26 lo pasa a antes de la revisión del S5 (provisional; requiere al equipo).
