# Verificación de cierre — Sprint 5 (mensajería, evaluación, bitácora e indicadores)

- Fecha: **2026-09-30** (17:40 a 18:10, hora de Chile). Preparado por: agente `qa`. Equipo local, Docker 29.8.0, Windows 11.
- Código: `main`, commit `19f2e9c` (árbol limpio al iniciar). QA agregó `scripts/qa-s5/` (sin commit): `preparar_datos.py`, `seguridad.py`, `seguridad2.py`, `ui5.py`, `exportacion_volumen.py`.
- Fuentes: `docs/estado-actual.md`; propuesta del S5 §1, §5, §6; ADR-026 (provisional); informe (HU-05, 07, 08, 09, 16, 18, 21, 22, 25; RF-25 a RF-31, RF-37, RF-38; RNF-19, 22, 26, 27; CA-03.3, 15.2, 25.x). Datos ficticios (`qa.s5.*@example.com`, RUT sintéticos).
- Suite completa: **1883 pasan en 10 min** (`pytest -q`, comando de `estado-actual.md`; la hoja dice 1882, hay una más).

**Veredicto: listo con observaciones.** Todos los CA y RF del S5 se cumplen de extremo a extremo en la pila normal (precio final, conversación, evaluación, denuncia, moderación, indicadores y exportación), con 404 idéntico y registro en `acceso_denegado` en cada ruta nueva. Hay tres defectos (DEF-QA-013 y 014 medios, DEF-QA-015 bajo) y evidencia que solo puede cerrar el equipo (RNF-13, RNF-18 de marca/Android, primer respaldo automático de las 03:00, P-24 a P-33). Ningún defecto es crítico ni alto.

## 1. Trazabilidad CA / RF → evidencia → resultado

Leyenda: T = prueba automática (`backend/tests/…`); H = paso HTTP real contra `https://localhost` (`scripts/qa-s5/seguridad*.py`); N = navegador (`ui5.py`).

| Elemento | Evidencia | Resultado |
|---|---|---|
| CA-16.1, RF-26 (monto con fecha y autor) | T `test_precio_final` (22 pruebas, C-09 a C-15); H: el maestro registra 30.000, queda `registrado_en`, y el historial lo muestra | Cumple |
| CA-16.2, RF-27 | T y H: por trabajo con monto distinto → `por_aceptar`, no finaliza; objetar vacía el precio; aceptar un monto distinto del vigente → 409 "El maestro cambió el monto…"; por hora con el monto igual al publicado → sigue `por_aceptar` hasta aceptar; por trabajo igual → finaliza sin aceptación | Cumple |
| CA-16.3 | H: cambiar el precio o objetar tras finalizar → 409 "ya terminó y su precio no se puede cambiar"; historial de cliente y maestro con el mismo `precio` (idénticos) | Cumple |
| P-27 (precio desde el inicio del bloque) | H: sobre un pedido futuro → 409 accionable | Cumple (provisional) |
| CA-08.1, CA-08.2, RF-28 | H: historial con maestro, servicio, fecha, estado y precio acordado; cerrado distinto de finalizado con `motivo_cierre_texto` ("El maestro no puede tomarlo" / "Lo rechazaste"). N: pestaña «Historial» en `mis-pedidos` y `mis-trabajos`, estado escrito, no solo color | Cumple |
| CA-07.1, RF-25 | H: cliente y maestro envían y leen en un pedido aceptado (201; `autor` = `tu`/`cliente`/`maestro`); N: `conversacion.html` | Cumple |
| CA-07.2 | H: los mensajes vuelven asociados al pedido; `?despues=` devuelve solo los nuevos; reenviar con la misma `clave_envio` → 200 con el mismo mensaje | Cumple |
| CA-07.3, CA-15.2 | H: finalizado → lectura 200 y escribir 409; cerrado → lista vacía con "No hubo conversación…"; pendiente → 409 | Cumple |
| CA-09.1, CA-18.1, RF-29 | H: cliente y maestro evalúan una orden finalizada (201); sobre pendiente o cerrado → 409; notas 0, 6, falta una o comentario de 501 → 400 por campo | Cumple |
| CA-09.2 | H: segunda evaluación de cada parte → 409 "Ya evaluaste este trabajo"; T `test_la_base_impide_dos_evaluaciones_de_la_misma_parte` (único en BD) | Cumple |
| CA-05.1, RF-30, RF-13, RF-14 | H: ficha con `promedio 2,3` = (2+3+2)/3 y `cantidad`, sin autor; N: ficha y tarjeta de `buscar` con calificación 5,0, dimensiones y comentario; T redondeo y promedio sobre publicadas | Cumple |
| CA-05.2 | N: la tarjeta de un maestro sin evaluaciones dice "Todavía no tiene evaluaciones"; tras retirar la única evaluación, la ficha vuelve a ese texto | Cumple |
| CA-03.3, RF-11 | T P-09 `test_ca03_3_desempate_por_promedio_redondeado_y_luego_cantidad` (desempate con el valor redondeado, después la cantidad, antes del sorteo) | Cumple |
| CA-21.1, RF-31 | H: la parte evaluada denuncia una vez (repetir → 409); moderación lista, ve el detalle y abre la conversación con la denuncia abierta (200); con la denuncia resuelta → 404 registrado | Cumple |
| CA-21.2, RF-37, CA-19.3 | H + BD: `denuncia_resuelta` (entidad `evaluacion`, anterior `publicada`, nuevo `retirada`, motivo, autor, fecha); `conversacion_consultada` y aviso `conversacion_revisada` a ambas partes (2 avisos); resolver sin motivo → 400; resolver otra vez → 409. `documento_eliminado_retencion` por T `test_retencion` (9) | Cumple |
| CA-22.1, RF-38 (indicadores) | H: los tres indicadores con definición (concreción 9,1 % = 4/44 en la pila normal; mediana de primera respuesta; vigencia documental). Volumen: concreción 42,3 % = 423/1.000. N: `indicadores.html` | Cumple |
| CA-22.2, RF-38 (exportación) | H: CSV `text/csv` con BOM, 7 columnas cerradas; 0 coincidencias de correo, RUT, teléfono, UUID, nombres ni direcciones en la pila normal (1 fila) y en la de volumen (56 filas); supresión k=5 cumplida sobre pedidos | **Cumple con observación** (DEF-QA-014) |
| CA-25.1, CA-25.3 (rutas nuevas) | §2 | Cumple |
| RNF-07, RNF-08, RNF-25 (rutas nuevas) | §2; regresión de dirección y teléfono con el pedido pendiente | Cumple |
| RNF-11 (bitácora, `mensaje`, `precio_final_evento`) | T triggers de solo inserción (`test_los_triggers_de_*`) y filas reales en `bitacora` sin secretos | Cumple |
| RNF-14 a RNF-17 (pantallas nuevas) | §3 | Cumple con observación (DEF-QA-013) |

## 2. Seguridad por recurso (pila normal, `https://localhost`)

Seis cuentas ficticias más clientes y maestros ajenos; pedidos creados por ORM en estados pendiente, aceptado, finalizado y cerrado. Rutas: `precio-final`, `…/aceptacion`, `…/objecion`, `mensajes` (GET y POST), `evaluacion`, `evaluaciones`, `evaluacion-recibida/denuncia`, `api/moderacion/denuncias[…]`, `api/gestion/*`.

| Caso | Resultado |
|---|---|
| Sin sesión, las 8 rutas de pedido y las de moderación y gestión | 401 |
| Cliente ajeno, maestro ajeno, curatoría y moderación sobre un pedido ajeno (8 rutas) | 404 en las 32 combinaciones; cuerpo idéntico entre sí **y** al de un pedido inexistente (sin la ref) |
| Parte equivocada: cliente registra precio; maestro acepta precio | 403 con mensaje accionable, registrado |
| `moderacion/denuncias`: cliente, maestro, curatoría, gestión | 403; anónimo 401; denuncia inexistente 404 |
| Conversación de una denuncia resuelta | 404 registrado (`entidad = denuncia`) |
| `gestion/*`: cliente, maestro, moderación, curatoría | 403 (indicadores y exportación); anónimo 401 |
| `acceso_denegado` | 467 → 555 filas; toda ruta sondeada aparece con su patrón (`POST api/tickets/<uuid:ref>/precio-final`, etc.), `entidad` = `ticket`, `ruta` o `denuncia`, sin ruta cruda ni cuerpo |
| Privacidad (regresión) | El maestro con pedido pendiente: detalle, bandeja `?estado=pendiente` e historial completo sin dirección, teléfono, nombre ni correo del cliente; el detalle de moderación tampoco los trae. Con el pedido aceptado sí los recibe (contacto mutuo) |
| Registros | `app`, `planificador`, `proxy` y `db` (40 min de sondeos, ~1.700 líneas): 0 coincidencias de contraseña, cookie, token, RUT, dirección ni teléfono |

Bitácora de la prueba: `conversacion_consultada`, `denuncia_resuelta` y `exportacion_agregada` con autor, valores y motivo, sin datos personales.

## 3. Pase de navegador (360 px, red limitada)

Infraestructura existente reutilizada (imagen `mcr.microsoft.com/playwright/python:v1.63.0-noble`, red `altiro_frontal`, desvío de `localhost`). `ui5.py`: Chromium 153 con CDP a 4/1 Mbps y 150 ms (D-19) y Firefox 155 sin red emulada, 360 × 740 táctil, 23 estados (mis-pedidos ×3, mis-trabajos ×4 con el registro del precio, conversación ×5, evaluar ×3, ficha con calificación, buscar con calificación, moderación ×3 con detalle y conversación, indicadores ×3 con período inválido).

| Medida | Resultado |
|---|---|
| Desplazamiento lateral o elemento fuera de pantalla | 0 en los 23 estados, ambos motores |
| Objetivos táctiles menores de 44 × 44 px (RNF-14) | 0 (los radios se miden con su etiqueta) |
| Errores de JavaScript o de CSP en consola (RNF-18) | 0 |
| axe-core 4.10.3, WCAG 2.0/2.1/2.2 AA (incluye contraste, RNF-16) | 0 violaciones, salvo **`listitem` en `conversacion.html`** (2 nodos, ambos motores, ambos roles): DEF-QA-013 |
| Jerga técnica en el texto visible (RNF-17) | 0 (la coincidencia "500" es "hasta 500 caracteres") |
| Carga con red limitada | 0,98 a 1,33 s y 11 a 43 KiB por pantalla (RNF-02 fija 3 s y 1,5 MB para la búsqueda; aquí es referencia) |
| Mensajes de error | accionables: "Elige un período de 31 a 366 días. Se cuentan ambas fechas."; "Ya evaluaste este trabajo"; 409 del precio en palabras del oficio |

No se ejecutó el pase manual en navegadores de marca ni en Android: sigue pendiente del equipo.

## 4. Resultados RNF

| RNF | Método y entorno | Resultado | Umbral | Estado |
|---|---|---|---|---|
| RNF-19 restauración | `scripts/simulacro-restauracion.sh` sobre `-p altiro-restauracion` con un respaldo tomado a las 21:00 UTC; Docker local | 19 s hasta `app` sana (21 s con la verificación); 30 tablas y 5.244 filas idénticas; 240 documentos descifrados, primera foto JPEG de 15.557 bytes; 62 ilegibles (ver §6) | ≤ 30 min | **PASS** |
| RNF-19 retención | `docs/testing/rnf-19-respaldo.md` (8 días se borra, 6 se conserva); no se repitió | borra solo lo de más de 7 días | 7 días | PASS (evidencia del incremento 3) |
| RNF-19 respaldo diario | el servicio `respaldo` arrancó hace 3 h; la primera ejecución programada (03:00 de Santiago) aún no ocurre; hay 3 respaldos manuales | no observable hoy | diario automatizado | **BLOCKED**: infraestructura preparada / evidencia final pendiente (revisar `../altiro-respaldos` el 2026-10-01 y dejarlo anotado) |
| RNF-01 con volumen completo | `docs/testing/rnf-01-medicion.md` (S5): 400 búsquedas, 10 hilos, 100 maestros, 1.000 tickets, 5.000 mensajes; no repetida | 100 % en ≤ 2 s; p95 0,214 a 0,216 s | 95 % en 2 s | PASS (medición del incremento 8) |
| RNF-03 | `rnf-03-volumen.md`; QA confirmó que el comando genera el volumen completo sobre una pila vacía (100 maestros, 1.000 tickets, 5.000 mensajes, 414 evaluaciones, 45 s) | cumple el volumen de prueba | volumen completo | PASS |
| RNF-22 | T `test_registro_json` (3) y revisión de ~470 líneas reales: `nivel`, `marca_tiempo`, `usuario`, `operacion`, `estado`, `duracion_ms`, sin datos personales | cumple los cuatro campos | 4 campos | PASS con DEF-QA-015 |
| RNF-26 | T `test_retencion` (9 pasan): plazo configurable por tipo, sin valor no borra nada, con valor marca y escribe la bitácora de Sistema. Los plazos siguen vacíos (V-04, P-07) | mecanismo listo; **plazo escrito por tipo pendiente** | plazo escrito por tipo | **BLOCKED**: infraestructura preparada / evidencia final pendiente |
| RNF-27 | `revision-dependencias-s5.md` (`pip-audit`, 2026-09-30, sin vulnerabilidades); las 19 dependencias de `requirements*.txt` (12 + 7) con `==` y ninguna sin fijar | registrada al inicio del S5 | versión exacta y revisión por sprint | PASS |
| RNF-21 | Conteo independiente contra `tests/reglas_rnf21.py` y `test_rnf21_cobertura_de_reglas` (en la suite): filtros 14/14, puntaje 14/14, cierre 17/17, acceso 25/25, operación 4/4, indicadores 4/4, anonimización 5/5; 83/83 reglas (100 %); 0 marcas fuera del catálogo | todos los grupos activos en 100 % | ≥ 60 % por grupo | PASS |
| RNF-13 | sin ejecutar (requiere personas) | — | 2 de 3 en ≤ 10 min | **BLOCKED** (pendiente del equipo) |
| RNF-18 | automático en 2 motores (§3) | pase manual en Safari/Chrome/Edge/Android sin hacer | navegadores del RNF | PASS (automático); BLOCKED (manual) |

## 5. Defectos

- **DEF-QA-013 (media). `conversacion.html` rompe la semántica de lista (axe `listitem`).** RNF-16 (accesibilidad WCAG 2.2 AA), HU-07.
  - Precondición: pedido aceptado con mensajes. Pasos: abrir `conversacion.html?ticket=<ref>` y correr axe-core 4.10.3 (2 nodos, Chromium y Firefox, cliente y maestro).
  - Esperado: 0 violaciones. Observado: `<ol id="lista-mensajes" role="log">` (línea 26) sustituye el rol de lista y deja los `<li>` huérfanos; los lectores de pantalla pierden el recuento de mensajes.
  - Evidencia: `scripts/qa-s5/ui5.py`. Área: frontend (quitar `role="log"` del `<ol>` y ponerlo en un `<div>` contenedor, o usar `aria-live` sin cambiar el rol).
- **DEF-QA-014 (media). La exportación publica la mediana de montos de grupos con menos de 5 órdenes finalizadas.** RF-38, CA-22.2, CLAUDE.md §8 ("prevenir reidentificación"), R-08, P-29.
  - Precondición: pila de volumen (100 maestros, 423 finalizados). Pasos: `GET /api/gestion/exportacion?desde=&hasta=` como control de gestión (`scripts/qa-s5/exportacion_volumen.py`).
  - Esperado: ningún valor agregado depende de menos de k órdenes. Observado: 56 filas; 43 tienen `ordenes_finalizadas` < 5 y 6 tienen exactamente 1, por lo que `mediana_monto_final` es el **precio exacto de un trabajo** (p. ej. `2026-09,Biobío,Florida,Pintura,10,1,12000`). La supresión cuenta maestros y clientes distintos entre **todos los pedidos enviados**, no entre los finalizados que alimentan la mediana.
  - Cumple la letra de CA-22.2 (sin RUT, nombre, teléfono ni dirección) y de ADR-026 E-6 tal como está escrito; el riesgo es de divulgación de atributos, sin identificador directo.
  - Área: `architect` (decidir la regla: suprimir o dejar vacía la mediana si hay menos de 5 finalizados, o contar k sobre finalizados) y luego `backend` (`gestion/exportacion.py`).
- **DEF-QA-015 (baja). El registro JSON atribuye a `sistema` el inicio de sesión de una persona.** RNF-22 (campo `usuario`), CLAUDE.md (no atribuir acciones humanas al Sistema).
  - Pasos: iniciar sesión y leer `docker logs altiro-app-1`. Observado: `{"usuario": "sistema", "operacion": "identidad.vistas", "mensaje": "Inicio de sesión correcto del usuario 376."}` (33 líneas en 40 min); el evento ocurre dentro de la petición, que aún es anónima. Esperado: `anonimo` o el id de la persona. No es la bitácora administrativa. Área: backend (`comun/registro.py`).

Numeración: continúa desde DEF-QA-012 (S3), el último que hay en `docs/`.

## 6. Pendientes revisados

- **DEF-QA-005 (S4) — confirmado corregido en pila vacía.** Proyecto `-p altiro-qa` (solo sus volúmenes, eliminado con `down -v`): migraciones sin pendientes, `health` 200 y `generar_volumen_prueba --semilla 42` sin error (1.000 tickets, ventana que cruza el cambio de horario del 6/9). Caso del defecto: sábado 5/9 21:00, bloque del domingo 6/9 03:00 → `vence_en` 02:00 UTC = inicio − 4 h (antes daba 03:00 UTC). Cubre además la regla C-08 de la suite.
- **62 documentos ilegibles: defecto de datos, no de código.** En la base principal, 62 documentos no eliminados no tienen archivo en el volumen (302 filas, 323 archivos); todos se cargaron el 2026-09-28 y 29 (cédula y certificados de maestros ficticios), que es la ventana del DEF-QA-008 del S2 (la suite borraba archivos huérfanos). La cifra es la misma antes y después de la suite de hoy y en la restauración. Recomendación: eliminar o recargar esas filas ficticias. Falta confirmar que hoy su descarga responde un mensaje accionable y no 500 (en el S2 daba 500).
- **Observaciones del S3:** OBS-S3-02 (precios de referencia sin pantalla pública) y OBS-S3-05 (contrastes del S3): el S5 no toca esas pantallas y no se repitieron. OBS-S3-04: la infraestructura de Playwright existe (`scripts/qa-s4/`, `scripts/qa-s5/`); ningún script cubre aún el campo `bloques` de la agenda.
- **Simulacro con un respaldo viejo:** el primero de hoy dio `CONTEOS_IGUALES=no` porque el respaldo del incremento 3 es anterior a las tablas `mensaje`, `evaluacion` y `denuncia` (la app restaurada las creó al migrar). Con un respaldo nuevo da `si`. El script no explica la diferencia; conviene que el simulacro final se haga con un respaldo del día.

## 7. Observaciones

- OBS-S5-01: `GET …/mensajes` no pagina (p95 0,079 s con 9,6 mensajes por pedido y máximo 23); revisar si las conversaciones reales crecen.
- OBS-S5-02: los planes de restauración dependen de la copia aparte de los secretos (ADR-026 E-7.2); el equipo aún no define dónde vive. `base.dump` no va cifrado.
- OBS-S5-03: los datos ficticios de esta verificación quedan en la pila normal (`qa.s5.*@example.com`, 2 maestros, 2 clientes, 3 cuentas administrativas y ~15 pedidos) y en la pila de volumen (`qa.s5.ges.vol@example.com`); alteran los indicadores de la base principal (concreción 9,1 %). No se borraron por la regla de no tocar volúmenes.
- OBS-S5-04: P-25 se cumple (la evaluación del maestro al cliente no sale en la ficha pública); la tarjeta de `buscar` mezcla maestros con y sin evaluaciones y usa el mismo texto de CA-05.2.
- OBS-S5-05: el respaldo se hizo con `--una-vez` dentro de `respaldo` (cuenta como manual). Los respaldos manuales de hoy suman 3 directorios en `../altiro-respaldos`.

## 8. Pendiente del equipo

- **RNF-13** con personas (DA-26, antes de la revisión del S5): riesgo más alto. Protocolo en `rnf-13-protocolo.md`; el flujo del maestro es ahora más largo (precio final, conversación, evaluación).
- **RNF-18** en Safari, Chrome, Edge y Chrome de Android reales.
- **Primer respaldo automático (03:00 del 2026-10-01)** y dónde se guarda la copia de secretos (RNF-19).
- **Plazos de retención por tipo de documento** (V-04, P-07) para cerrar RNF-26.
- **Preguntas al representante P-24 a P-33** (escala de evaluación, quién ve la evaluación del maestro, quién denuncia, cuándo se registra el precio, pedidos aceptados que nunca se finalizan, k de la exportación, plazo de retención, escribir tras finalizar, definición de primera respuesta, aviso a las partes cuando moderación lee la conversación). Hoy todo corre con las opciones provisionales de ADR-026.
- Decidir DEF-QA-014 (regla de la exportación) antes de entregar datos a control de gestión.

## 9. Cómo repetir

`scripts/qa-s5/`: `preparar_datos.py` (en `app`: `manage.py shell < …`), `seguridad.py` y `seguridad2.py` (desde el equipo, usando `127.0.0.1:443` con `Host: localhost`), `ui5.py` (imagen de Playwright, red `altiro_frontal`, `python3 ui5.py proxy datos.json datos3.json chromium|firefox`) y `exportacion_volumen.py` (en `altiro-volumen-app-1`). Los JSON de datos contienen cuentas y refs de la corrida y no se guardaron.
