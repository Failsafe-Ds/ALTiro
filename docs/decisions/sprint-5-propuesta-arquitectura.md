# Propuesta de arquitectura — Sprint 5 (mensajería, evaluación, bitácora e indicadores)

- Estado: propuesta (2026-09-30). Semanas 13 a 15 (§5.3.5, fila S5).
- Base: `docs/estado-actual.md`, ADR-023, ADR-024 y DA-22 a DA-26 (`docs/alcance/bitacora-de-alcance.md`). Las decisiones nuevas están en **ADR-026** (provisional).
- Regla de recorte (§5.3.5, párrafo siguiente a la tabla): RF-26, RF-27 y RF-28 están protegidos. Si falta capacidad, se recortan la mensajería (NTI-08) y la evaluación (NTI-06), que son necesidades condicionadas.

## 1. Alcance

| Requisito | CA | Qué se construye | Compromiso |
|---|---|---|---|
| RF-26, RF-27 (HU-16) | CA-16.1 a CA-16.3 | El maestro registra el monto final. La aceptación del cliente se exige según la modalidad y la orden pasa a `finalizado`. Tiene CHECK de defensa | Comprometido (NTI-04) |
| RF-28 (HU-08), paso de DA-22 | CA-08.1, CA-08.2 | El historial trae el precio acordado, el maestro, el servicio y el motivo de cierre. Ambas partes ven el mismo monto | Comprometido (NTI-03) |
| RF-25 (HU-07), paso de DA-24 | CA-07.1 a CA-07.3, CA-15.2 (conversación) | La conversación privada del ticket se abre al aceptar. En una orden finalizada queda de solo lectura. Un ticket cerrado muestra que no hubo conversación | Condicionado (NTI-08) |
| RF-29 (HU-09, HU-18) | CA-09.1, CA-09.2, CA-18.1 | Una evaluación por parte y por orden `finalizada`, en tres dimensiones | Condicionado (NTI-06) |
| RF-30 (HU-05, HU-09), paso de DA-23 | CA-05.1, CA-05.2, CA-03.3 | Calificación por dimensión y promedio en la ficha y en la tarjeta (RF-13, RF-14). Desempate de RF-11 con datos reales | Condicionado (NTI-06). La evidencia de RF-11/13/14 depende de esta fila |
| RF-31 (HU-21) | CA-21.1, CA-21.2 | Denuncia de una evaluación. Moderación ve la conversación solo con la denuncia abierta y resuelve con motivo | Condicionado (NTI-06, NTI-08) |
| RF-37 (HU-19, HU-25) | CA-19.3 | Nuevos puntos de registro en la bitácora: resolución de denuncias, acceso de moderación a una conversación y eliminación por retención | Comprometido (NTI-12) |
| RF-38 (HU-22) | CA-22.1, CA-22.2 | Los tres indicadores base (§2.9.2): tasa de concreción, tiempo de primera respuesta y vigencia documental. Exportación CSV agregada y protegida | Indicadores comprometidos (NTI-10). Exportación condicionada (NTI-07) |
| RNF-19 | — | Respaldo diario automático, retención de 7 días y restauración cronometrada en 30 min o menos | Comprometido (NTI-03; R-04) |
| RNF-22 | — | Registro de aplicación con nivel, marca de tiempo, usuario y operación | Comprometido (NTI-12) |
| RNF-26 | — | Plazo de retención escrito por tipo de documento, eliminación por Sistema y entrada en la bitácora | Comprometido. El valor del plazo está bloqueado por V-04 y P-07 |
| RNF-27 | — | Revisión de avisos de dependencias al inicio del S5, registrada | Comprometido |
| RNF-03 y RNF-01, paso de DA-25 | — | Volumen de prueba con 5.000 mensajes y evaluaciones, y nueva medición de RNF-01 | Comprometido |
| RNF-13, paso de DA-26 | — | Sesión con personas antes de la revisión del S5. La organiza el equipo; no es trabajo de un agente | Pendiente del equipo |

**Fuera de alcance** (no hay HU, RF ni RNF que lo respalde, o el informe lo excluye):
- adjuntos en mensajes (NTI-08 los nombra, pero RF-25 no);
- editar o borrar mensajes y evaluaciones;
- respuesta pública a una evaluación;
- notificaciones por correo, SMS o push;
- filtros automáticos de contenido;
- tablero de gestión completo (NTI-10);
- venta de datos (NTI-07);
- pagos y facturación;
- API de lectura de la bitácora;
- mostrar a terceros la calificación del cliente (P-25).

## 2. Revisión de la excepción `ParteEquivocada` (propuesta S4, §11, aclaración 20)

**Se mantiene y se extiende a las rutas de precio final.** Motivos:
1. Quien la recibe ya es parte del ticket y conoce el recurso. Un 404 no protegería nada y confundiría a una persona legítima (RNF-13, RNF-17). El 403 con mensaje accionable es correcto (ADR-011).
2. Al quedar registrada en `acceso_denegado`, deja evidencia de CA-25.3 sin que otros módulos escriban esa tabla (M-08).
3. Donde la acción depende de quién la hace (evaluar, conversar, denunciar la evaluación recibida), la parte se **deduce** del usuario en el servidor. Esas rutas no necesitan la excepción, así que no se multiplican rutas por parte.
4. No se crea una excepción nueva. Moderación no pasa por `PoliticaTicket`: usa su propia política sobre la denuncia (§3.3).

## 3. Diseño del servidor

### 3.1 Modelo de datos (migraciones nuevas)

**`ticket` (tickets 0002, columnas nuevas):**
- `monto_final` (entero, nulo, de 1 a `MONTO_MAXIMO`);
- `monto_final_en` y `monto_final_autor_id` (nulos, se exigen juntos);
- `precio_aceptado_en` (nulo).

CHECK nuevos:
- `precio_aceptado_en` exige `monto_final`;
- `estado='finalizado'` exige `monto_final` y, además, `modalidad='por_trabajo' AND monto_final=monto_publicado` **o bien** `precio_aceptado_en IS NOT NULL` (RF-27, CA-16.2);
- `monto_final` solo puede existir en estado `aceptado` o `finalizado`.

**`precio_final_evento`:** solo inserción (triggers, `managed=False`, sin FK; patrón de ADR-010).
- Columnas: `ticket_id`, `accion ∈ {registrado, aceptado, objetado}`, `monto`, `autor_id`, `fecha`.
- Índice `(ticket_id, fecha)`.
- Conserva cada registro y cada objeción antes de finalizar (CA-16.1).

**`mensaje` (app `mensajeria`):** solo inserción, con el mismo patrón.
- Columnas: `id`, `ref` UUID único, `ticket_id`, `autor_id`, `texto` (de 1 a 1000 caracteres, CHECK `\S`), `enviado_en`, `clave_envio` UUID.
- Único `(ticket_id, autor_id, clave_envio)` para que un reenvío no duplique el mensaje.
- Índice `(ticket_id, enviado_en, id)`.

**`evaluacion` (app `evaluaciones`):**
- Columnas: `ref`, `ticket` FK PROTECT, `parte ∈ {cliente, maestro}`, `autor_id`, `evaluado_id`, `puntualidad`, `trabajo` y `cordialidad` (smallint de 1 a 5), `comentario` (0 a 500), `creada_en`, `estado ∈ {publicada, retirada}`.
- **Único `(ticket, parte)`** (RF-29, CA-09.2, CA-18.1). CHECK `autor_id ≠ evaluado_id`.
- Índice `(evaluado_id, parte, estado)`, que sirve para el promedio.
- La API no ofrece forma de modificarla. Solo moderación cambia `estado`, y el cambio queda en la bitácora.

**`denuncia` (app `evaluaciones`):**
- Columnas: `ref`, `evaluacion` FK PROTECT, `denunciante_id`, `motivo` (1 a 500), `estado ∈ {abierta, resuelta}`, `decision ∈ {mantener, retirar}` (nula), `motivo_resolucion`, `resuelta_por_id`, `resuelta_en`.
- Único `(evaluacion, denunciante_id)`.
- CHECK: `resuelta` si y solo si hay decisión, motivo, autor y fecha.
- Índice parcial `(creada_en) WHERE estado='abierta'`.

**`aviso_ticket` (ADR-024):** tipos nuevos `precio_registrado`, `precio_objetado`, `orden_finalizada`, `mensaje_nuevo` y `conversacion_revisada`. El aviso `mensaje_nuevo` **se reactiva**: vuelve a `visto_en=NULL` con otro `creado_en`, en lugar de insertar una fila nueva (ADR-026 E-2).

**`documento` (expediente):** columnas `eliminado_en` y `motivo_eliminacion`, nulas. Se borra el archivo cifrado y la fila se conserva (RNF-26).

### 3.2 Transiciones (se completa la tabla de ADR-023, punto 3)

| De | A | Quién y condiciones |
|---|---|---|
| aceptado | aceptado (precio `por_aceptar`) | El maestro registra un `monto` con `ahora ≥ inicio_en` (P-27) y **se exige aceptación**: modalidad por hora, o por trabajo con un monto distinto del publicado |
| aceptado | finalizado | Hay dos caminos:<br>• el maestro registra un monto que no exige aceptación;<br>• el cliente acepta un monto `por_aceptar`, enviando en el cuerpo el mismo `monto` vigente. Si el monto cambió → 409 "El maestro cambió el monto, revísalo" |
| aceptado (`por_aceptar`) | aceptado (sin precio) | El cliente objeta. Se vacía `monto_final`, se registra `objetado` y se avisa al maestro |
| finalizado | — | Cualquier intento de cambiar el precio → 409 "Este trabajo ya terminó y su precio no se puede cambiar" (CA-16.3) |

Reglas de ejecución:
- Se bloquea la fila del ticket con `select_for_update`.
- `ticket_evento` registra el paso a `finalizado` con su autor. `precio_final_evento` registra cada acción sobre el precio.
- Repetir el mismo monto, o aceptar lo que ya se aceptó, responde 200 idempotente (D-10).

### 3.3 Endpoints

La columna "Política" describe qué recibe el usuario que no está autorizado.

| Método y ruta | Rol o parte | Política | Estado requerido |
|---|---|---|---|
| POST `/api/tickets/<ref>/precio-final` `{monto}` | Maestro del ticket | Tercero: 404 registrado. Cliente: `ParteEquivocada` | `aceptado` y `ahora ≥ inicio_en` |
| POST `…/precio-final/aceptacion` `{monto}` | Cliente del ticket | Ídem. Maestro: `ParteEquivocada` | `aceptado` con precio `por_aceptar` |
| POST `…/precio-final/objecion` (sin cuerpo) | Cliente del ticket | Ídem | `aceptado` con precio `por_aceptar` |
| GET `/api/{clientes,maestros}/tickets` (existente) | Dueño | Existente | Sin `estado`, devuelve el historial completo. Agrega `precio` y `motivo_cierre_texto` |
| GET `/api/tickets/<ref>/mensajes?despues=<ref>` | Cliente o maestro del ticket | `PoliticaTicket` (404 registrado) | `aceptado` o `finalizado`. En `cerrado`, lista vacía y texto "no hubo conversación". En `pendiente`, 409 |
| POST `/api/tickets/<ref>/mensajes` `{texto, clave_envio}` | Cliente o maestro | `PoliticaTicket` | Solo `aceptado`. En otro estado, 409 accionable |
| POST `/api/tickets/<ref>/evaluacion` `{puntualidad, trabajo, cordialidad, comentario?}` | La parte se deduce del usuario | `PoliticaTicket` | `finalizado`. Si ya evaluó, 409 "Ya evaluaste este trabajo" |
| GET `/api/tickets/<ref>/evaluaciones` | Cliente o maestro | `PoliticaTicket` | Devuelve `{mia, recibida}` |
| POST `/api/tickets/<ref>/evaluacion-recibida/denuncia` `{motivo}` | La parte evaluada | `PoliticaTicket`. Sin evaluación recibida: 409 | La evaluación recibida está `publicada` |
| GET `/api/maestros/publicos/<ref>` (existente) | Público | Existente | Agrega calificación por dimensión, promedio, cantidad y los últimos 10 comentarios, sin autor |
| GET `/api/moderacion/denuncias?estado=` | `moderacion` | `requiere_rol` (403) | — |
| GET `/api/moderacion/denuncias/<ref>` | `moderacion` | `PoliticaDenuncia` | Muestra la evaluación y un resumen del ticket (servicio, comuna, fechas, precio), **sin dirección ni teléfono** |
| GET `/api/moderacion/denuncias/<ref>/conversacion` | `moderacion` | `PoliticaDenuncia`: si la denuncia no está `abierta`, 404 registrado. Si el moderador es parte del ticket, `ConflictoDeInteres` | `abierta`. Cada consulta se registra en la bitácora y deja el aviso `conversacion_revisada` a ambas partes (M-04) |
| POST `/api/moderacion/denuncias/<ref>/resolucion` `{decision, motivo}` | `moderacion` | Ídem | `abierta`. Si está resuelta, 409. Se registra en la bitácora con el valor anterior y el nuevo de la evaluación (CA-21.2, RF-37) |
| GET `/api/gestion/indicadores?desde=&hasta=` | `control_gestion` | `requiere_rol` | Período de 31 a 366 días. Fuera de rango, 400 en el campo |
| GET `/api/gestion/exportacion?desde=&hasta=` | `control_gestion` | `requiere_rol` | Archivo `text/csv` (ver §3.5) |

Todas las rutas nuevas con `<uuid:ref>` llevan prueba de terceros (ADR-011).

### 3.4 Reglas en servidor (resumen)
- **Conversación:** solo las dos partes y solo desde `aceptado` (CA-15.2). Moderación entra por la denuncia, nunca por `PoliticaTicket`. La consulta incremental cada 20 s no renueva la sesión (ADR-005, igual que los avisos).
- **Evaluación:**
  - solo sobre una orden `finalizado`;
  - una por parte, garantizada por el único de la base;
  - enteros de 1 a 5 y comentario opcional;
  - se publica de inmediato.
- **Promedio (RF-30):**
  - media de `(p + t + c) / 3` sobre las evaluaciones `publicada` con `parte='cliente'`;
  - se redondea a 1 decimal y se calcula en cada lectura (patrón de ADR-019);
  - el desempate de RF-11 usa el valor redondeado y después la cantidad;
  - sin evaluaciones, se muestra "Todavía no tiene evaluaciones" (CA-05.2).
- **Bitácora:** sigue en solo inserción, sin rutas, con `registrar()` dentro de la misma transacción. No hay acciones nuevas que la editen.

### 3.5 Indicadores y exportación (RF-38, R-08)
- **Tasa de concreción:** tickets `finalizado` con `monto_final` dividido por los tickets enviados en el período (por `enviado_en`).
- **Tiempo de primera respuesta:** mediana y cantidad del tiempo entre `enviado_en` y el primer `ticket_evento` cuyo autor es el maestro con `aceptado` o `rechazado_maestro`. Se excluyen `bloque_tomado` y los cierres del Sistema (P-32).
- **Vigencia documental:** porcentaje de maestros aprobados cuyos documentos obligatorios están vigentes a la fecha de cálculo. Reutiliza `expediente/vigencia.py`.
- **Exportación CSV:**
  - columnas en lista cerrada: `mes, region, comuna, oficio, tickets_enviados, ordenes_finalizadas, mediana_monto_final`;
  - **se suprime** cada fila con menos de k=5 maestros distintos o menos de 5 clientes distintos (P-29);
  - sin mínimos, máximos ni totales, para evitar reconstruir filas por diferencia;
  - sin `ref`, sin identificadores internos y sin texto libre;
  - las celdas que empiezan con `= + - @` se neutralizan;
  - comuna y oficio salen de listas cerradas.

## 4. Pantallas nuevas o modificadas (mobile-first; CSP sin código inline)
- `conversacion.html?ticket=<ref>`: común a ambas partes.
  - Muestra los mensajes con fecha y "Tú / Cliente / Maestro".
  - Si un envío falla, el texto se conserva y se reintenta con la misma `clave_envio`.
  - En una orden finalizada es de solo lectura, con el aviso escrito.
- `mis-trabajos.html`: en un trabajo aceptado, el formulario "Registrar precio final".
  - Tiene un solo campo y muestra la modalidad y el monto publicado.
  - Antes de enviar, explica si el cliente tendrá que aceptar.
  - También ofrece "Ver conversación", "Evaluar al cliente" y la evaluación recibida con "Denunciar".
- `mis-pedidos.html`: tarjeta "Precio por aceptar" con dos botones, "Aceptar" y "No estoy de acuerdo".
  - Pestaña Historial con el precio acordado o el motivo de cierre. El estado se indica con texto y no solo con color (CA-08.2).
  - Enlaces para conversar, evaluar y denunciar.
- `evaluar.html?ticket=<ref>`: tres grupos de botones de 1 a 5 con etiquetas escritas, zonas táctiles de 44 px o más y comentario opcional.
- `perfil-maestro.html` y `buscar.html`: calificación por dimensión, promedio con la cantidad y comentarios.
- `moderacion.html`: lista de denuncias abiertas, detalle, botón "Ver conversación" con advertencia de que el acceso queda registrado, y resolución con motivo obligatorio.
- `indicadores.html`: período, los tres indicadores con su definición y el botón "Exportar CSV".

## 5. Plan de incrementos

| N.º | Contenido | HU/RF/CA | Archivos probables | Pruebas críticas (`@pytest.mark.regla`) |
|---|---|---|---|---|
| 0 | Revisión de avisos de dependencias con `pip-audit` en un contenedor efímero | RNF-27 | `docs/testing/revision-dependencias-s5.md` | — (evidencia documental) |
| 1 | Precio final, finalización e historial en el servidor | HU-16, HU-08; RF-26 a RF-28; CA-16.1 a CA-16.3, CA-08.1, CA-08.2 | `tickets/models.py`, `migrations/0002_precio_final.py`, `transiciones.py`, `vistas.py`, `serializacion.py`, `avisos.py`, `altiro/urls.py`, `tests/test_precio_final.py` | Por trabajo con monto igual finaliza sin aceptación; con monto distinto bloquea hasta aceptar; por hora siempre exige aceptación; aceptar con un monto distinto → 409; finalizado inmodificable; CHECK de finalización en la base; `ParteEquivocada` en las tres rutas; 404 de terceros; ambas partes ven el mismo monto |
| 2 | Pantallas de precio e historial | Ídem | `frontend/mis-trabajos.html`, `frontend/mis-pedidos.html` y sus JS | Playwright: registrar, aceptar y objetar; historial distingue cerrado de finalizado |
| 3 | Operación: respaldo y restauración, registro de aplicación y retención | RNF-19, RNF-22, RNF-26; RF-37 | `docker-compose.yml` (servicio `respaldo`), `scripts/respaldo.sh`, `scripts/restaurar.sh`, `comun/registro.py`, `altiro/settings.py` (LOGGING), `expediente/retencion.py`, comando del planificador, `.env.ejemplo`, `docs/alcance/plazos-retencion.md`, `docs/testing/rnf-19-respaldo.md` | Retención: sin plazo configurado no borra nada; con plazo, borra el archivo, marca la fila y escribe la bitácora con autor Sistema. El formato de registro tiene los 4 campos y no incluye datos personales. Simulacro de restauración cronometrado |
| 4 | Mensajería | HU-07; RF-25; CA-07.1 a CA-07.3, CA-15.2 | App `mensajeria/` (models, migración, vistas, serializacion), `tickets/avisos.py`, `frontend/conversacion.html` y su JS | Enviar en `pendiente` → 409; enviar en `finalizado` o `cerrado` → 409; lectura en `finalizado`; un tercero y un administrativo reciben el 404 registrado; `clave_envio` idempotente; triggers de solo inserción |
| 5 | Evaluaciones y calificación | HU-09, HU-18, HU-05; RF-29, RF-30, RF-11, RF-13, RF-14; CA-09.x, CA-18.1, CA-05.1, CA-05.2, CA-03.3 | App `evaluaciones/`, `busqueda/servicios.py` (`calificaciones_en_lote`), `busqueda/vistas.py`, vista de `perfil_publico`, `frontend/evaluar.html`, `perfil-maestro.html` y `buscar.html` | Solo sobre `finalizado`; la segunda evaluación → 409 y único en la base; el promedio coincide con el cálculo; una evaluación retirada queda excluida; desempate CA-03.3 (grupo puntaje); sin evaluaciones, el texto de CA-05.2 |
| 6 | Denuncias y moderación | HU-21, HU-25; RF-31, RF-37; CA-21.1, CA-21.2, CA-25.3 | `evaluaciones/` (denuncia, `PoliticaDenuncia`, vistas de moderación), `tickets/avisos.py`, `frontend/moderacion.html` | Con denuncia resuelta, la conversación da 404 registrado; un no moderador recibe 403; el moderador que es parte recibe `ConflictoDeInteres`; cada consulta escribe en la bitácora y avisa a ambas partes; la resolución exige motivo y escribe en la bitácora; el detalle no trae dirección ni teléfono |
| 7 | Indicadores y exportación | HU-22; RF-38; CA-22.1, CA-22.2 | App `gestion/` (indicadores, exportacion, vistas), `frontend/indicadores.html` | Las tres fórmulas con datos fijados; el CSV no tiene columnas fuera de la lista ni patrones de RUT, teléfono, correo, nombre o dirección; supresión con k<5; sin totales; neutralización de celdas CSV |
| 8 | Volumen y mediciones | RNF-03, RNF-01 (DA-25) | `busqueda/management/commands/generar_volumen_prueba.py` (5.000 mensajes y evaluaciones en órdenes finalizadas), `docs/testing/rnf-01-medicion.md` | 19 de cada 20 búsquedas en 2 s o menos con 10 usuarios simultáneos y el volumen completo |
| 9 | QA de cierre, RNF-13 (DA-26, lo realiza el equipo) y material de defensa | — | `docs/testing/cierre-sprint-5.md` | Suite completa y catálogo `tests/reglas_rnf21.py` en 60 % o más por grupo |

Orden de prioridad: 0, 1, 2 y 3 están protegidos. Si falta capacidad, se recorta primero el 6, después el 5 y después el 4 (§5.3.5). El incremento 7 conserva los indicadores aunque se recorte la exportación.

## 6. Pruebas y umbrales
- RNF-21: las reglas nuevas se catalogan en sus grupos. Acceso a mensajes, moderación y precio van en **control de acceso**; el desempate con calificación va en **puntaje**; el cierre y la finalización van en **cierre**.
- RNF-19: tiempo total medido desde `restaurar.sh` hasta el `health` en verde. Debe ser de 30 min o menos, con el conteo de filas y la descarga de un documento como verificación.
- RNF-11: la prueba vigente de triggers se amplía a `mensaje` y `precio_final_evento`.
- RNF-22: una prueba sobre el formato del registro.

## 7. Riesgos y dependencias
- Todo depende de S1 a S4 (identidad, `PoliticaTicket`, `ticket_evento` y avisos), que ya existen.
- R-05 (conversaciones ajenas): refs UUID y participación verificada. R-08: supresión con k=5. R-04: RNF-19 en el incremento 3. R-09: RNF-26 bloqueado por V-04 y P-07.
- Una orden `aceptado` que nunca se finaliza queda abierta indefinidamente. No se inventa un motivo de cierre (P-28).
- RNF-13 sigue sin evidencia hasta que el equipo haga la sesión (DA-26).

## 8. Supuestos y preguntas al representante (continúan en `docs/alcance/preguntas-representante-s2.md`)

| Id | Pregunta | Opción provisional |
|---|---|---|
| P-24 | ¿Escala de evaluación? | Enteros de 1 a 5 por dimensión |
| P-25 | La evaluación del maestro al cliente (HU-18), ¿quién la ve? | La guardan las partes y moderación. No se muestra a otros maestros |
| P-26 | ¿Quién puede denunciar una evaluación? | Solo la parte evaluada, una vez por evaluación |
| P-27 | ¿Desde cuándo se puede registrar el precio final? | Desde el inicio del bloque |
| P-28 | ¿Qué pasa con una orden aceptada que nunca se finaliza? | Queda `aceptado`. Sin cierre automático |
| P-29 | ¿Umbral y nivel de agregación de la exportación? | k=5 maestros y 5 clientes, por mes y comuna |
| P-30 | ¿Plazo de retención por tipo de documento? (V-04, P-07) | Configurable. Sin valor, no se elimina nada |
| P-31 | ¿Se puede seguir escribiendo después de finalizar? | No, queda de solo lectura |
| P-32 | Tiempo de primera respuesta: ¿mediana o promedio? ¿Cuenta `bloque_tomado`? | Mediana, sin `bloque_tomado` |
| P-33 | ¿Basta un aviso dentro de la aplicación para informar a las partes que moderación leyó la conversación (M-04)? | Sí, el aviso `conversacion_revisada` |

## 9. Trazabilidad

| Decisión | Requisitos |
|---|---|
| Precio en `ticket`, `precio_final_evento` y CHECK de finalización | RF-26, RF-27, HU-16, CA-16.x, NTI-04 |
| Historial con precio acordado | RF-28, HU-08, CA-08.x, DA-22 |
| `mensaje` de solo inserción, solo desde `aceptado` | RF-25, HU-07, CA-07.x, CA-15.2, RNF-07, R-05 |
| Evaluación única por parte y promedio calculado en lectura | RF-29, RF-30, RF-11, RF-13, RF-14, CA-03.3, CA-05.x, DA-23 |
| Denuncia abierta como disputa y `PoliticaDenuncia` | RF-31, HU-21, CA-21.x, M-04, RNF-07 |
| Nuevos puntos de registro en la bitácora | RF-37, RNF-11, CA-19.3 |
| Indicadores y CSV con supresión | RF-38, HU-22, CA-22.x, NTI-07, NTI-10, R-08 |
| Servicio de respaldo y simulacro | RNF-19, R-04 |
| Formato de registro | RNF-22 |
| Retención configurable | RNF-26, V-04, R-09 |
| `pip-audit` efímero | RNF-27, R-07 |
| Volumen con mensajes | RNF-03, RNF-01, DA-25 |
