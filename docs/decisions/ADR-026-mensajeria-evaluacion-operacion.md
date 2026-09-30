# ADR-026 — Precio final, mensajería, evaluación, moderación, indicadores y operación (S5)

- Estado: **Aceptada — PROVISIONAL** (2026-09-30). Se aplicó la opción recomendada sin respuesta del equipo (`docs/Reanudar.md`). Se revisa en la revisión del Sprint 5.
- Relacionado con: RF-25 a RF-31, RF-37, RF-38, RF-11, RF-13, RF-14, RNF-01, RNF-03, RNF-07, RNF-11, RNF-19, RNF-22, RNF-26, RNF-27, HU-05, HU-07, HU-08, HU-09, HU-16, HU-18, HU-21, HU-22, HU-25, V-04; ADR-005, ADR-010, ADR-011, ADR-015, ADR-019, ADR-022, ADR-023, ADR-024; P-24 a P-33.
- Origen: `docs/decisions/sprint-5-propuesta-arquitectura.md`.

## Contexto
El informe define qué hace cada requisito del S5, pero no fija: dónde se guarda el precio final, cómo se activa la finalización, la escala de evaluación, cómo se calcula el promedio, qué es operativamente una "disputa abierta", el nivel de agregación seguro de la exportación, el mecanismo de respaldo, el formato de registro ni el valor de la retención. Estas decisiones completan ADR-023 (transición `aceptado → finalizado`) y ADR-024 (tipos de aviso), y modifican ADR-015 en un punto (E-7).

## Decisión

### E-1. Precio final y finalización (RF-26, RF-27, CA-16.x)
1. **Dónde se guarda.** El valor vigente va en `ticket`: `monto_final`, `monto_final_en`, `monto_final_autor_id` y `precio_aceptado_en`. El historial va en `precio_final_evento`, de solo inserción con el patrón de ADR-010: `registrado`, `aceptado` y `objetado`, con monto, autor y fecha.
2. **Aceptación del cliente.** Se exige si `modalidad='por_hora'`, o si `modalidad='por_trabajo'` y `monto_final ≠ monto_publicado`.
3. **Finalización.** La orden pasa a `finalizado` automáticamente con la última condición cumplida:
   - si no se exige aceptación, al registrar el maestro;
   - si se exige, cuando el cliente acepta.

   `ticket_evento` registra el autor de ese paso.
4. **Aceptación.** El cliente envía el `monto` que está aceptando. Si no coincide con el vigente → 409. Esto evita aceptar un monto que el maestro cambió entre medio.
5. **Objeción.** El cliente puede objetar: se vacía `monto_final` y se avisa al maestro. Lo coordinan por la conversación.
6. **Condición de tiempo.** Solo se registra con `ahora ≥ inicio_en` (P-27).
7. **Orden finalizada.** No se puede modificar: cualquier intento → 409 (CA-16.3).
8. **CHECK en la base.** `estado='finalizado'` implica `monto_final` y, además, igualdad por trabajo o `precio_aceptado_en`.
9. **Sin cierre automático** de un `aceptado`: el informe no define un motivo para eso (P-28).

### E-2. Mensajería (RF-25, CA-07.x, CA-15.2)
1. **Estructura.** App `mensajeria`. La tabla `mensaje` es de solo inserción (triggers, `managed=False`, sin FK). Los mensajes no se editan ni se borran porque son evidencia en una disputa (M-04).
2. **Estados.** Se escribe solo en `aceptado`. Se lee en `aceptado` y en `finalizado`. En `cerrado`, lista vacía con el texto "no hubo conversación", porque `cerrado` solo llega desde `pendiente`. En `pendiente`, 409 (P-31).
3. **Acceso.** `PoliticaTicket`, sin excepciones: solo las dos partes.
4. **Envío.** Texto de 1 a 1000 caracteres. `clave_envio` UUID generada por el navegador, con único `(ticket, autor, clave_envio)`: un reenvío con conexión irregular no duplica el mensaje.
5. **Actualización.** Consulta incremental cada 20 s con `despues=<ref>`, solo mientras la página está visible. No renueva la sesión (ADR-005). Sin WebSocket ni dependencias nuevas.
6. **Aviso.** El aviso `mensaje_nuevo` **se reactiva** sobre la fila existente (`visto_en=NULL`) y así respeta el único `(ticket, destinatario, tipo)` de ADR-024. Es una excepción acotada a "una sola emisión".
7. **Sin adjuntos**: RF-25 no los pide.

### E-3. Evaluación y calificación (RF-29, RF-30, RF-11, CA-05.x, CA-03.3)
1. **Estructura.** App `evaluaciones`. La tabla `evaluacion` tiene único `(ticket, parte)` y solo se permite sobre `finalizado`.
2. **Contenido.** Escala de enteros de 1 a 5 por dimensión (P-24). Comentario opcional de hasta 500 caracteres. Se publica de inmediato.
3. **Promedio del maestro.**
   - Se calcula sobre las evaluaciones `publicada` con `parte='cliente'`, como la media de `(puntualidad + trabajo + cordialidad) / 3`, redondeada a 1 decimal.
   - También se muestra cada dimensión por separado.
   - Se calcula en cada lectura y no se guarda un valor derivado (patrón de ADR-019).
4. **Desempate de RF-11.** Usa el valor **redondeado que se muestra** y después la cantidad, para que el orden sea coherente con lo que ve la persona (ADR-022).
5. **Comentarios en la ficha.** Últimos 10, con mes y año, sin nombre ni `ref` del autor (minimización).
6. **Evaluación del maestro al cliente (HU-18).** Se guarda y la ven las partes y moderación. No se muestra a otros maestros mientras no se responda P-25.

### E-4. Denuncia y moderación (RF-31, CA-21.x, M-04)
1. **Disputa abierta.** Existe una disputa abierta si y solo si hay una `denuncia` en estado `abierta`.
2. **Quién denuncia.** Solo la parte evaluada, una vez por evaluación (P-26). La ruta pasa por el ticket y la parte se deduce del usuario.
3. **`PoliticaDenuncia`.** Exige el rol `moderacion`.
   - Si el moderador es parte del ticket → `ConflictoDeInteres`.
   - La conversación exige la denuncia `abierta`. En otro caso → `AccesoDenegado`, que da el 404 idéntico con registro.
4. **Cada consulta de la conversación:**
   - escribe en la bitácora `conversacion_consultada`, entidad `ticket`, con motivo "Denuncia <ref>";
   - deja el aviso `conversacion_revisada` a ambas partes (P-33).
5. **Datos del ticket para moderación.** Sin dirección ni teléfono.
6. **Resolución.** `mantener` o `retirar`, con motivo obligatorio. Escribe en la bitácora `denuncia_resuelta` con el estado anterior y el nuevo de la evaluación. `retirar` pone la evaluación en `retirada`: no la borra y la excluye del promedio.

7. **Aclaraciones de implementación (incrementos 5 y 6, provisionales):**
   - el moderador que es parte del ticket no ve esa denuncia en su lista y recibe `ConflictoDeInteres` (403 registrado) en el detalle, la conversación y la resolución;
   - `ConflictoDeInteres` ya existía (expediente); cada política define su mensaje en `Politica.mensaje_conflicto`;
   - la bitácora de la resolución usa entidad `evaluacion` y guarda la `ref` de la denuncia en los valores;
   - no se avisa a las partes cuando se resuelve una denuncia: CA-21.2 y RF-31 solo exigen registrar decisión, autor y motivo;
   - `aviso_ticket.tipo` pasa de 20 a 30 caracteres.

### E-5. `ParteEquivocada` (revisión de la aclaración 20 del S4)
Se mantiene y se extiende a las rutas de precio final. Quien la recibe ya es parte del recurso, así que un 404 no protege nada. El registro sirve de evidencia para CA-25.3. No se crean excepciones nuevas. En las rutas donde la parte se deduce del usuario (mensajes, evaluación, denuncia), la excepción no aplica.

### E-6. Indicadores y exportación (RF-38, CA-22.x, R-08)
1. **Definiciones operativas** (§2.9.2 del informe):
   - concreción = finalizados con `monto_final` / enviados, por `enviado_en`;
   - primera respuesta = mediana entre `enviado_en` y el primer evento del maestro (`aceptado` o `rechazado_maestro`), sin `bloque_tomado` ni cierres del Sistema (P-32);
   - vigencia documental = porcentaje de maestros aprobados con todos sus documentos obligatorios vigentes (reutiliza `expediente/vigencia.py`).
2. **Exportación CSV:**
   - columnas en lista cerrada: `mes, region, comuna, oficio, tickets_enviados, ordenes_finalizadas, mediana_monto_final`;
   - se **suprimen** las filas con menos de 5 maestros distintos o menos de 5 clientes distintos (P-29);
   - sin mínimo, máximo ni totales;
   - sin identificadores ni texto libre;
   - las celdas que empiezan con `= + - @` se neutralizan.
3. **Acceso.** Solo el rol `control_gestion`. El período va de 31 a 366 días.

4. **Aclaraciones de implementación (incremento 7, provisionales):**
   - la vigencia documental se calcula a la fecha de hoy (no a `hasta`), en lote y aplicando en Python las reglas de `expediente/vigencia.py`, para no duplicarlas en SQL;
   - la neutralización también cubre celdas que empiezan con tabulador o retorno de carro (OWASP);
   - el CSV va en UTF-8 con BOM; las medianas se redondean con la mitad hacia arriba;
   - cada exportación escribe la bitácora `exportacion_agregada` (autor, período, filas y filas suprimidas).

### E-7. Respaldo y restauración (RNF-19, R-04)
1. **Servicio `respaldo`.** Usa la misma imagen `postgres:16` y no agrega imágenes. Una vez al día, a la hora configurada (RNF-24), ejecuta:
   - `pg_dump -Fc`;
   - `tar` de los volúmenes `fotos` y `documentos`.

   Guarda el resultado en un directorio local fuera del repositorio (en `.gitignore`) y elimina lo que tenga más de 7 días.
2. **Enmienda a ADR-015.** `documentos` se monta **de solo lectura** en `respaldo`. Ese contenedor solo ve texto cifrado con AES-256-GCM y la clave nunca se monta en él. El equipo respalda la clave por separado, fuera del mismo directorio.
3. **Restauración.** `scripts/restaurar.sh` hace `pg_restore` y extrae los volúmenes. El simulacro cronometrado usa un proyecto Compose aparte (`-p altiro-restauracion`) para no tocar los volúmenes principales (CLAUDE.md §14). La evidencia va en `docs/testing/rnf-19-respaldo.md`.

### E-8. Registro de aplicación (RNF-22)
1. **Formato.** Una línea JSON por evento, a stdout, con la librería estándar `logging` (sin dependencias). Campos: `nivel`, `marca_tiempo` (UTC ISO 8601), `usuario` (id interno o `anonimo`), `operacion` (nombre de la ruta y método), `estado` HTTP y `duracion_ms`.
2. **Qué no se registra.** Ruta con `ref`, cuerpo, parámetros, cookies ni cabeceras.
3. **Silenciar el aviso de Django.** `django.request` solo registra desde nivel ERROR. Así se elimina el "Not Found: <ruta>" de OBS-S3-07.

### E-9. Retención de documentos (RNF-26, V-04, R-09)
1. **Plazos.** Uno por tipo de documento, en la configuración (`RETENCION_DIAS_<TIPO>`), y por escrito en `docs/alcance/plazos-retencion.md`.
2. **A qué expedientes aplica.** A los que están en `rechazado` o `suspendido`, contando desde la fecha de ese estado. Se trata como "deja de estar activo" (V-04, P-07).
3. **Sin plazo configurado no se elimina nada** y se registra una advertencia (P-30).
4. **Tarea del planificador.** Autor Sistema. Borra el archivo cifrado, pone `eliminado_en` y `motivo_eliminacion` en la fila y escribe en la bitácora `documento_eliminado_retencion` con el tipo y el plazo aplicado.

### E-10. Revisión de dependencias (RNF-27)
`pip-audit` se ejecuta en un contenedor efímero al inicio de cada sprint. No se agrega a `requirements*.txt`. El resultado queda en `docs/testing/revision-dependencias-s<N>.md`.

## Alternativas consideradas
- **Tabla `orden` separada:** se descarta porque contradice §2.3 y ADR-023.
- **Precio solo en eventos, sin columnas:** se descarta porque el CHECK de finalización no podría defender la regla.
- **WebSocket o SSE para mensajes:** se descarta por las dependencias, el proxy y la dificultad de defenderlo. El sondeo alcanza para 10 usuarios.
- **Promedio guardado:** se descarta por el riesgo de desincronización. El volumen no lo justifica.
- **Exportar sin supresión, o con ruido diferencial:** la primera falla ante R-08; la segunda es difícil de explicar y de probar. Se elige supresión con k.
- **Respaldo desde `app`:** mezcla responsabilidades y deja la clave de cifrado en el mismo contenedor que el respaldo. Se prefiere el montaje de solo lectura sin clave.

## Consecuencias
- Nuevas tablas de solo inserción, `mensaje` y `precio_final_evento`: la prueba de triggers se amplía.
- Nuevas rutas con `<uuid:ref>`, cada una con prueba de terceros.
- ADR-015 cambia en el montaje de `documentos` y ADR-024 en `mensaje_nuevo`. Hay que actualizar `docs/estado-actual.md`.
- P-24 a P-33 quedan abiertas. Una respuesta distinta cambia E-1.6, E-3, E-4.2, E-6 o E-9 sin tocar el modelo base.
- RNF-26 no queda cumplido mientras no se defina un plazo escrito por tipo.
