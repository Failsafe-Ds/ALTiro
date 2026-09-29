# Propuesta de arquitectura — Sprint 4: búsqueda, ordenamiento y ticket

- Estado: **Borrador — decisiones D-1 a D-22 aplicadas como PROVISIONALES el 2026-09-29**, con la opción recomendada, según `docs/Reanudar.md`. Están en ADR-022 a ADR-024 y en las enmiendas ADR-013 E-9, ADR-016 E-1, ADR-019 E-1 y ADR-020 E-1. D-9 se aplica en su variante sin `EXCLUDE` (ver ADR-023). Las preguntas P-19 a P-23 van al representante.
- Preparado por: agente `architect`, sobre `e5ce0c4`.
- Alcance (informe §5.3.5): "Búsqueda, ordenamiento y ticket, con RF-09 a RF-24, RNF-01 a RNF-04 y RNF-21". Incremento esperado: "Flujo principal operativo desde la búsqueda hasta el cierre".
- Compromisos que llegan: DA-02 (RNF-08), DA-05 (CA-25.1), DA-13 (CA-24.4), DA-14 (búsqueda), DA-20 (RF-06 en resultados, CA-13.2, CA-14.3), DA-03 y la pregunta abierta de ADR-013 sobre el auto-envío.

**Hallazgos que condicionan el plan:**
1. RF-26, RF-27 y RF-28 son del **S5**. En S4 solo se prepara el modelo (§3.7).
2. RF-12 está **condicionado a capacidad** (§2.9.3).
3. La respuesta de la búsqueda no puede incluir el puntaje ni sus componentes: la cercanía (100 o 60) revelaría la comuna base (ADR-019, D-14).

---

## 1. Alcance

| ID | Criterio de verificación (informe) | S4 |
|---|---|---|
| RF-09 | "Ningún resultado incumple alguno de los filtros aplicados" | Completo |
| RF-10 | "El puntaje corresponde a 0,6 × disponibilidad + 0,4 × cercanía según la escala definida" | Completo |
| RF-11 | Desempate por calificación promedio y luego por cantidad de evaluaciones | Mecanismo listo; se demuestra en S5 (no hay evaluaciones) |
| RF-12 | Sugerencias rotuladas que indican qué criterio incumplen | Condicionado; el mensaje de CA-04.1 sí se hace |
| RF-13 | Tarjeta con foto, nombre, calificación promedio y oficio | La calificación dice "Todavía no tiene evaluaciones" |
| RF-14 | "La ficha distingue visualmente bloques libres de ocupados" | Bloques libres y ocupados; calificaciones en S5 |
| RF-15 | Falla si falta descripción, dirección o materiales; copia modalidad y monto | Completo |
| RF-16 | "Esos bloques no se ofrecen en el formulario" (4 horas o menos) | Completo (V-03) |
| RF-17 | "La respuesta del servidor no contiene esos campos en estado pendiente" | Completo; cierra DA-02 |
| RF-18 | Aviso al crear el ticket | Completo, dentro de la app |
| RF-19 | Aceptar ocupa el bloque, cierra los demás pendientes y revela el contacto | Completo |
| RF-20 | Rechazar deja el bloque libre | Completo |
| RF-21 | Cierre a las 24 horas desde el envío | Completo |
| RF-22 | Cierre 4 horas antes del inicio; a las 28 horas exactas se registra proximidad | Completo |
| RF-23 | Cierre por el cliente; no se puede aceptar después | Completo |
| RF-24 | "Los cinco motivos de cierre en estado pendiente se registran de forma distinguible" | Completo |

- **RNF:**
  - RNF-01: "Al menos 19 de cada 20 búsquedas responden en 2 segundos o menos, con 100 maestros, 1.000 tickets y 10 personas usando el sistema a la vez".
  - RNF-02: 3 segundos o menos a 4 Mbps, con la primera pantalla de 1,5 MB o menos.
  - RNF-03: el volumen de prueba.
  - RNF-04: 2 GB o menos.
  - RNF-21: "Al menos el 60% de las reglas de filtros, puntaje, cierre de tickets y control de acceso cubiertas por pruebas automáticas".
  - También aplican RNF-07, RNF-08, RNF-25 (búsqueda), RNF-14 a RNF-18 y RNF-20.
- **No entran:** mensajería, evaluaciones, precio final y su aceptación, RF-28 completo, RF-37 completo e indicadores (todo S5); pagos (fuera de alcance); una vía de urgencias (V-03).

## 2. Búsqueda (ADR-022)
- **Filtros excluyentes, calculados en el servidor:**
  - el maestro está publicado según la regla única (ADR-019);
  - tiene un servicio **visible** del oficio;
  - la comuna pedida está en su cobertura;
  - tiene una ocurrencia ofrecible que **contiene** el bloque pedido: está libre, no se cruza con un ticket aceptado o finalizado y empieza en más de 4 horas.

  La decisión final pasa por la función pura de la regla única. Una prueba de propiedad compara la búsqueda con esa regla aplicada maestro por maestro.
- **Puntaje:** `6·D + 4·C` en enteros, es decir, 10 veces `0,6·D + 0,4·C`.
  - Disponibilidad (D):
    - 100: libre en el bloque exacto;
    - 60: libre hoy;
    - 30: libre entre hoy+1 y hoy+3;
    - 0: nada.
  - Cercanía (C): 100 si es su comuna base, 60 si está en su cobertura.
  - CA-03.2 se prueba literal: 60 frente a 58.
  - Desempate: calificación, luego cantidad de evaluaciones (valen `None` y 0 hasta el S5), y al final un sorteo diario `sha256(ref pública + fecha)`.
  - El puntaje no se expone; se explica en una página de ayuda.
- **Rendimiento:**
  - `motivos_no_visible_de(servicio_maestro, ctx, hoy)` es la versión pura, cargada en lote (ADR-019 E-1);
  - número de consultas constante, verificado con `django_assert_max_num_queries`;
  - índices nuevos;
  - `no-store`;
  - páginas de 20.
- **Datos de volumen:** comando `generar_volumen_prueba --semilla 42 --confirmo-datos-ficticios`, pensado para una pila aparte. Los 5.000 mensajes esperan al S5.
- **Ficha:** `bloques` de los próximos 14 días, cada uno libre u ocupado. Se omiten los que empiezan en 4 horas o menos. Un bloque ocupado no lleva ningún dato del ticket.
- **Sugerencias:** solo si no hay resultados. Se relaja el bloque y después la comuna (misma provincia). Nunca se relaja el oficio ni la publicación. Máximo 5.

## 3. Ticket (ADR-023)
- **App `tickets`:**
  - `ticket` es el mismo registro lógico del ticket y de la orden. El `id` es el número visible, pero nunca va en la URL; la URL usa `ref` UUID.
  - Copias de `modalidad` y `monto_publicado`, y de `fecha`, `inicio_min` y `fin_min`, con `inicio_en` y `fin_en` calculados.
  - `comuna`, `direccion`, `descripcion` y `materiales` (sin valor por defecto).
  - `estado`: pendiente, aceptado, finalizado o cerrado. `motivo_cierre`: `vencido_plazo`, `vencido_proximidad`, `cancelado_cliente`, `rechazado_maestro` o `bloque_tomado`.
  - `vence_en = LEAST(enviado + 24 h, inicio − 4 h)`.
  - CHECK de defensa: incluye `cliente ≠ maestro` (ADR-013 E-9).
- **Historial:** `ticket_evento`, de solo inserción con triggers. No es la bitácora administrativa.
- **Transiciones:** tabla en ADR-023. Incluye la protección al actuar, que cierra en el momento un ticket que ya venció, y la idempotencia.
- **Concurrencia:** primero se bloquea el `expediente` del maestro y después los tickets. La tarea de cierre usa `skip_locked`.
- **Privacidad (RF-17, RNF-08):** la serialización depende de la relación con **ese** ticket. El contacto solo aparece si el ticket fue aceptado.
- **Zona horaria:** `perfil/ocurrencias.py` (ADR-020 E-1).
- **Precio final (S5):** el diseño se adelanta, pero no se construye.

## 4. Avisos y sesión (ADR-024)
- Tabla `aviso_ticket` con los tipos `ticket_nuevo`, `ticket_cerrado` (a ambas partes) y `ticket_aceptado`, sin datos personales.
- Sin consultas periódicas: los avisos se cargan al navegar y con el botón "Actualizar".
- El planificador pasa a correr cada 300 s (ADR-016 E-1).

## 5. Endpoints
- **Públicos:** `GET /api/busqueda` y la ficha pública con `bloques`.
- **Cliente:** `POST /api/tickets` (rol cliente) y `GET /api/clientes/tickets`.
- **Maestro:** `GET /api/maestros/tickets`.
- **Por ticket:**
  - `GET /api/tickets/<uuid:ref>`, con `PoliticaTicket`: solo el cliente o el maestro de ese ticket. Cualquier otro recibe el 404 idéntico con registro, lo que cierra CA-25.1 / DA-05.
  - `POST .../aceptacion`, `.../rechazo` (maestro) y `.../cancelacion` (cliente). Si actúa la parte equivocada, 403 registrado.
- **Avisos:** `GET /api/avisos` y `POST /api/avisos/vistos`.
- **Pruebas de terceros** en todas las rutas con `<uuid:ref>`.

## 6. Frontend
- **Páginas:**
  - `buscar.html` (pública), con el selector propio de 24 h y las sugerencias en una sección aparte;
  - la ficha con bloques;
  - `pedir-trabajo.html` en 4 pasos de 5 campos o menos, con progreso que vence a las 2 horas;
  - `mis-pedidos.html`;
  - `mis-trabajos.html`, con las pestañas Nuevos / Aceptados / Cerrados;
  - `js/estado-pedido.js`.
- **Vocabulario:** en pantalla se dice "pedido" por "ticket".
- **Presupuesto de RNF-02:** JS de 30 KB o menos, fotos de 160 px con carga diferida, 20 tarjetas por página y JSON de 50 KB o menos.

## 7. Pruebas y medición
- **RNF-21:** catálogo de reglas `tests/reglas_rnf21.py`, marca `@pytest.mark.regla` y 60 % **por grupo**, con meta de 100 %.
- **RNF-01:** `scripts/medir_rnf01.py`, con 10 hilos y al menos 200 búsquedas sobre el volumen sintético. Se informan el 95 % y el p95.
- **RNF-02:** Playwright con CDP a 4 Mbps de bajada, 1 Mbps de subida y 150 ms de latencia, más la suma de `transferSize`.
- **RNF-04:** `docker stats` durante la medición de RNF-01.

## 8. Decisiones (provisionales, 2026-09-29)

| ID | Decisión aplicada | Registro |
|---|---|---|
| D-1 | Se prohíbe el auto-envío: CHECK más 400 "No puedes pedirte un trabajo a ti mismo" | ADR-013 E-9 |
| D-2 | Oficio y comuna obligatorios; bloque opcional (fecha, inicio y fin, los tres juntos) | ADR-022 |
| D-3 | "Bloque exacto": una ocurrencia ofrecible que **contiene** el rango pedido | ADR-022 |
| D-4 | "Libre": no ocupado y que empiece en más de 4 horas | ADR-022 |
| D-5 | Horizonte de 14 días para pedir y para la ficha (P-19) | ADR-022 |
| D-6 | Desempate final con sorteo diario `sha256(ref+fecha)` | ADR-022 |
| D-7 | Sugerencias: primero relajar el bloque, después la comuna de la misma provincia (si hay capacidad) | ADR-022 |
| D-8 | Páginas de 20 | ADR-022 |
| D-9 | Bloqueo por maestro más único parcial `(maestro, inicio_en)` sobre tickets aceptados o finalizados. **Sin `EXCLUDE gist`:** `btree_gist` es *trusted*, pero `altiro_app` no tiene CREATE sobre la base (verificado) | ADR-023 |
| D-10 | Acciones idempotentes más único parcial de pendiente `(cliente, maestro, inicio_en)` | ADR-023 |
| D-11 | Un servicio que dejó de ser visible no se puede aceptar (409), pero sí rechazar | ADR-023 |
| D-12 | "Mismo bloque" significa que los rangos del mismo maestro se cruzan | ADR-023 |
| D-13 | El maestro no ve el nombre del cliente antes de aceptar (P-20) | ADR-023 |
| D-14 | Tabla nueva `aviso_ticket` | ADR-024 |
| D-15 | Se avisa al cliente cuando le aceptan el pedido | ADR-024 |
| D-16 | Sin consultas periódicas | ADR-024 |
| D-17 | En pantalla se dice "pedido" | ADR-024 |
| D-18 | RNF-21 se mide por reglas, 60 % por grupo | ADR-022 |
| D-19 | Red para RNF-02: 4/1 Mbps y 150 ms | ADR-022 |
| D-20 | Intervalo del planificador de 300 s por defecto, más la protección al actuar | ADR-016 E-1 |
| D-21 | Contacto mutuo al aceptar: el cliente ve el teléfono del maestro (P-20) | ADR-023 |
| D-22 | RF-26 y RF-27 se quedan en el S5 | — |

## 9. Orden de implementación
0. **Inicio:** RNF-27, decisiones, terminar las pantallas del S3 y esqueleto del volumen.
1. `ocurrencias.py` y `motivos_no_visible_de`, sin cambios de comportamiento.
2. Búsqueda en el backend (RF-09 a RF-11) y primera medición de RNF-01. Cierra DA-13 y DA-20 (RF-06), y la parte de búsqueda de DA-14.
3. Búsqueda y ficha en el frontend; medición de RNF-02.
4. Crear ticket (RF-15 a RF-18). Cierra DA-02 y DA-05.
5. Aceptar, rechazar y cancelar (RF-19, RF-20, RF-23). Cierra CA-14.3.
6. Cierre automático (RF-21, RF-22, RF-24).
7. Bandejas, avisos y "mis pedidos".
8. RF-12, si hay capacidad.
9. Cierre: RNF-01 a RNF-04, RNF-21, RNF-14 a RNF-18 y QA.

## 10. Riesgos y bitácora de alcance
- **Riesgos:**
  - 16 RF en el sprint (se recorta primero RF-12);
  - horario de verano y el borde de las 28 horas;
  - carreras al aceptar;
  - RF-11 no demostrable hasta el S5;
  - RNF-03 sin mensajes;
  - envío masivo de pendientes (sin límite en el informe: se registra como riesgo);
  - dirección guardada en sessionStorage;
  - ADR-019 y ADR-020 provisionales.
- **Cierres previstos:** DA-02, DA-05, DA-13, DA-14 (parte S4), DA-20 y avance de DA-03.
- **Registros nuevos:**
  - adelanto parcial de RF-28 (lista de pedidos);
  - pasan al S5 la evidencia de RF-11 y CA-03.3 y la calificación de RF-13 y RF-14;
  - pasa al S5 la conversación de CA-15.2;
  - RNF-03 con mensajes pasa al S5;
  - RF-12 queda como recorte si no se construye.

## 11. Aclaraciones de implementación (incrementos 1 y 2, 2026-09-29, provisionales)
1. Una ocurrencia no se ofrece si su inicio **o** su fin cae en una hora que no existe por el cambio de horario (por ejemplo, 22:00–24:00 el sábado del salto de hora).
2. **Horizonte de 14 días:** va de hoy a hoy+13. Pedir hoy+14 responde 400.
3. Con filtro de bloque, la regla de las 4 horas se aplica al inicio de la ocurrencia completa, no al del rango pedido (ADR-022, lectura literal).
4. **Parámetros:** `oficio` es el código del oficio y `comuna` es el código CUT. Un oficio inactivo o desconocido responde 400 en el campo. Una página fuera de rango devuelve una lista vacía, sin mensaje.
5. **Sugerencias:** se acumulan primero las que no calzan con el bloque y después las de otra comuna, hasta completar 5.
6. **Volumen sintético:** solo usa oficios no regulados, porque fabricar licencias SEC exigiría archivos cifrados. Los RUT sintéticos van desde 50.000.000 y los teléfonos son +56 9 0000 0NNN.
7. La ficha expone la ref del patrón de disponibilidad. Las rutas privadas sobre ese patrón ya están protegidas por la política de dueño.
8. `rangos_ocupados()` y `calificaciones_en_lote()` responden vacío hasta el incremento 4 y el S5, respectivamente.

### Aclaraciones del incremento 4 (crear el ticket, 2026-09-29, provisionales)
9. **El pedido nombra un horario completo de la agenda:** `fecha`, `inicio` y `fin` deben coincidir exactamente con una ocurrencia ofrecible (CA-06.1, "un bloque de su agenda declarada"). Un rango dentro de un horario, como 09:00–11:00 dentro de 08:00–12:00, responde 409. `maestro` es la ref pública del perfil y `servicio` es la ref del catálogo, como las entrega la ficha.
10. **Códigos de respuesta de `POST /api/tickets`:**
    - datos que faltan o no sirven: 400 por campo;
    - un maestro inexistente y uno no publicado reciben el mismo 400 en `maestro`, para no revelar si existe;
    - servicio no visible: 400 en `servicio`; comuna fuera de la cobertura: 400 en `comuna`;
    - horario que no está en la agenda, que empieza en 4 horas o menos, o que está ocupado: 409 con el mensaje de cada caso y con `bloques`, los horarios libres vigentes (CA-06.2). `bloques` es la única clave que se agrega al formato `{mensaje, errores}`.
11. **Pendiente repetido (D-10):** si el cliente ya tiene un pendiente con ese maestro y ese inicio, se responde 200 con **ese** ticket, sin cambiarlo y sin nuevo aviso ni evento, aunque la descripción sea otra. Si ese pendiente ya venció y todavía no se cierra, se responde 409 ("inténtalo de nuevo en unos minutos") hasta que el incremento 6 agregue la tarea de cierre y la protección al actuar.
12. **Límites de texto:** la dirección tiene 200 caracteres o menos, en una línea. La descripción tiene 1.000 caracteres o menos. `materiales` debe ser un booleano JSON (`true` o `false`); `"true"`, `1` o `null` responden 400.
13. **Modelo:**
    - `ticket` guarda la FK a `servicio_maestro`, la fila publicada que eligió el cliente. D-11 (incremento 5) evalúa la visibilidad de esa misma fila;
    - `ticket_evento` no tiene FK hacia `ticket` ni hacia `usuario`, igual que `bitacora`, porque una FK impediría el vaciado de las pruebas `transaction=True`;
    - los CHECK de plazos usan intervalos en horas (`'24 hours'`), no `'1 day'`, porque los plazos se miden en tiempo real (ADR-020 E-1);
    - coherencia de fechas: `aceptado_en` debe estar entre `enviado_en` y antes de `vence_en`; `cerrado` implica que no hubo aceptación (solo se llega desde `pendiente`); `finalizado_en` debe ser igual o posterior a `aceptado_en`.
14. **`aviso_ticket`:** agrega `ref` (UUID, ADR-011) y un único `(ticket, destinatario, tipo)`, así cada aviso se emite una sola vez. `POST /api/avisos/vistos` recibe `{"avisos": [refs]}` (de 1 a 100) y solo marca los del usuario de la sesión: las refs ajenas o inexistentes se ignoran sin decir cuáles.
15. **Lectura:**
    - `numero` (el `id`) sale en las respuestas como número visible, pero nunca se acepta como entrada;
    - `GET /api/tickets/<ref>` no exige un rol: decide `PoliticaTicket`. Un administrador que además es cliente tampoco ve tickets ajenos;
    - el bloque de contacto aparece si el ticket está aceptado **o finalizado**;
    - las listas `GET /api/clientes/tickets` y `GET /api/maestros/tickets` no tienen filtro de estado (llega con las bandejas del incremento 7), van de la más nueva a la más antigua y en páginas de 20. Un parámetro desconocido responde 400 general.
16. **Ocupación:** `rangos_ocupados()` ya consulta `ticket` (aceptados y finalizados), con una consulta por búsqueda. La búsqueda pasa de 13 a 14 consultas, sigue siendo constante, y deja sin efecto la parte de la aclaración 8 que la dejaba vacía.
17. **Volumen sintético:** 10 tickets por maestro (1.000 con 100 maestros) y 2 clientes ficticios por maestro. Por maestro: uno aceptado y dos pendientes en los próximos 14 días, y siete pasados (finalizados o cerrados con motivos coherentes), cada uno con su `ticket_evento`. Sin avisos. En esos eventos sintéticos, el autor de la finalización es el maestro; la regla real es del S5 (RF-26, RF-27).
18. **Compresión (RNF-02):** el proxy comprime con gzip HTML, CSS, JS, JSON y SVG. No comprime las respuestas de `/api/(curatoria/)?documentos/<ref>/enlace`, que llevan el token (BREACH), ni la descarga de documentos. Medido en la pila local: el JS de `buscar.html` baja de 49,6 KB a 17,0 KB transferidos.
19. **Pendiente para el incremento 6:** el enlace a la búsqueda en el aviso `ticket_cerrado` por `bloque_tomado` (CA-23.5).
