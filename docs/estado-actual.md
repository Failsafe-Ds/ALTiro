# Estado actual del proyecto (hoja corta para agentes)

> Leer esto **en lugar de** recorrer todos los ADR, propuestas y cierres. Abrir un ADR o una propuesta solo si el encargo lo cita o si una regla de abajo no alcanza. Si hay contradicción, prevalecen el informe y el ADR (CLAUDE.md §2).
> Actualizar esta hoja al cerrar cada incremento: una línea por cambio, sin narrativa.

Última actualización: 2026-09-30 (S5 en curso: incrementos 0 a 7 cerrados; siguiente: incremento 8, volumen y mediciones).

## Sprints
| Sprint | Estado | Etiqueta / cierre |
|---|---|---|
| S1 Identidad, roles y acceso | Cerrado | `sprint-1`, `docs/testing/cierre-sprint-1.md` |
| S2 Expediente y curatoría | Cerrado | `sprint-2`, `cierre-sprint-2.md` |
| S3 Catálogo, cobertura y agenda | Cerrado con observaciones | `sprint-3`, `cierre-sprint-3.md` |
| S4 Búsqueda y ticket | Cerrado con observaciones | `sprint-4`, `cierre-sprint-4.md` |
| S5 Mensajería, evaluación, bitácora e indicadores | En curso | propuesta `sprint-5-propuesta-arquitectura.md`, ADR-026 |

## Stack y cómo correr
- Docker Compose: `init`, `db` (PostgreSQL 16), `app` (Django 5.2 + gunicorn), `proxy` (Nginx, TLS autofirmado, gzip), `planificador` (cada 300 s) y `respaldo` (postgres:16, diario).
- Frontend estático en HTML, CSS y JS, sin framework y con CSP estricta (sin inline).
- **Suite completa** (Git Bash, desde la raíz): `MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd -W)/backend:/app" --entrypoint pytest app -q`. Tarda unos 9 min y hoy pasan 1882.
- **Durante el desarrollo**, solo pruebas dirigidas: el mismo comando con `tests/test_x.py -k nombre`.
- Migrar: `docker compose exec app python manage.py migrate`. Tras cambiar la plantilla del proxy: `docker compose up -d --force-recreate proxy`.

## Apps del backend (`backend/`)
`identidad` (usuario propio, sesión, Argon2id) · `autorizacion` (políticas, `obtener_autorizado`, enlaces firmados) · `bitacora` (solo inserción) · `territorio` · `catalogo` · `expediente` (documentos cifrados, curatoría, planificador) · `perfil` (servicios, cobertura, agenda, foto, publicación, ocurrencias, ocupación) · `busqueda` · `tickets` · `mensajeria` (conversación) · `evaluaciones` (evaluación, calificación, denuncia y moderación) · `gestion` (indicadores y exportación, sin modelos) · `comun` (API, middleware, errores).

## Invariantes transversales (resumen de ADR)
- **Rutas privadas por defecto:** `@publica` para abrir una ruta. Verificar siempre identidad, rol, propiedad y estado en el servidor.
- **Acceso a recursos ajenos (ADR-011):**
  - recurso ajeno → **404 idéntico** y registro en `acceso_denegado`;
  - rol o parte equivocada → 403 registrado;
  - las URL usan `ref` UUID, nunca `id`.
  - Toda ruta nueva con `<uuid:ref>` necesita prueba de terceros. La prueba de control de rutas no admite exenciones nuevas.
- **Errores (ADR-013):** formato `{mensaje, errores}`. Una clave desconocida da 400 general; un campo no permitido da 400 en ese campo. Sin códigos internos.
- **Bitácora, `ticket_evento` y `acceso_denegado`:** solo inserción, con triggers y `managed=False`, sin FK de autor (ADR-010).
- **Sesión (ADR-005):** 1800 s deslizantes; las consultas automáticas no la renuevan. CSRF: reintento único ante `AlTiro-Rechazo: csrf`.
- **Documentos (ADR-015):** AES-256-GCM, sin EXIF y máximo 8 MB. Enlace firmado de 600 s. El volumen de documentos va montado en `app` y `planificador`, y **de solo lectura en `respaldo`** (enmienda de ADR-026, E-7.2). La clave nunca se monta en `respaldo`.
- **Publicación (ADR-019):** la visibilidad se calcula en cada lectura con `perfil/publicacion.py` y nunca se guarda una marca. Elegible = aprobado + comuna base + foto.
- **Agenda (ADR-020):**
  - minutos múltiplos de 30, sin cruzar la medianoche;
  - `perfil/ocurrencias.py` resuelve el horario de verano (America/Santiago);
  - los plazos se miden en tiempo real.
- **Búsqueda (ADR-022):**
  - filtros excluyentes;
  - puntaje `6·D + 4·C`, nunca expuesto;
  - desempate con `sha256(ref+fecha)`;
  - sugerencias en una sección aparte;
  - horizonte de 14 días.
- **Ticket (ADR-023):**
  - un solo registro para ticket y orden;
  - estados `pendiente`, `aceptado`, `finalizado` y `cerrado`, con 5 motivos de cierre;
  - `vence_en = LEAST(enviado + 24 h, inicio − 4 h)`;
  - se bloquea primero el expediente del maestro y después los tickets;
  - mientras está pendiente, el maestro no recibe dirección, teléfono ni nombre del cliente;
  - contacto mutuo solo tras aceptar.
  - transiciones en `tickets/transiciones.py`: aceptar y rechazar (maestro), cancelar (cliente); repetir da 200, lo demás 409 accionable;
  - la parte equivocada recibe 403 registrado con `ParteEquivocada` (middleware de `autorizacion`);
  - cierre por vencimiento: tarea `cerrar_vencidos` del planificador (`skip_locked`) y protección al actuar (cierra, guarda y responde 409), con autor Sistema;
  - `ticket_cerrado` va a ambas partes; con `bloque_tomado`, el aviso del cliente trae `enlace` a `buscar.html` (CA-23.5).
  - bandejas: `GET /api/{clientes,maestros}/tickets?estado=` (un valor de los 4 estados; otro → 400 en `estado`). Pantallas `pedir-trabajo`, `mis-pedidos` (cliente) y `mis-trabajos` (maestro); borrador de pedido por clave `altiro.pedir-trabajo.<m>.<b>.<f>.<s>`.
- **Precio final (ADR-026, E-1 y E-5; S5 inc. 1-2):**
  - vigente en `ticket` (`monto_final`, `monto_final_en`, `monto_final_autor_id`, `precio_aceptado_en`); historial en `precio_final_evento` (solo inserción, triggers, `managed=False`);
  - CHECK: `finalizado` exige `monto_final` y (por trabajo con monto igual al publicado o `precio_aceptado_en`); monto, fecha y autor van juntos; sin precio fuera de `aceptado`/`finalizado`;
  - `POST /api/tickets/<ref>/precio-final {monto}` (maestro, con `ahora ≥ inicio_en`), `…/aceptacion {monto}` y `…/objecion` (cliente); `transiciones.registrar_precio/aceptar_precio/objetar_precio`; repetir → 200; aceptar un monto distinto del vigente → 409; finalizado no cambia de precio (409);
  - la otra parte → `ParteEquivocada` (403 registrado); tercero → 404 registrado;
  - avisos `precio_registrado` (al cliente), `precio_objetado` (al maestro), `orden_finalizada` (a la parte que no actuó); se reactivan si ya existían;
  - bandejas: sin `estado` → historial completo; cada ticket trae `precio` (`por_aceptar`/`acordado`) y `motivo_cierre_texto`; el maestro, además, `precio_registrable`. Pestaña «Historial» en `mis-pedidos` y `mis-trabajos`.
- **Operación (ADR-026, E-7 a E-9; S5 inc. 3):**
  - respaldo: `scripts/respaldo.sh` (dump, conteos, tar, sumas; 7 días) hacia `ALTIRO_RESPALDO_DIR` (`../altiro-respaldos`). `scripts/restaurar.sh` se niega si existe algún volumen del proyecto destino. El simulacro solo se hace en `-p altiro-restauracion` (`docs/testing/rnf-19-respaldo.md`: 19 s);
  - registro: JSON por línea (`comun/registro.py`: `nivel`, `marca_tiempo`, `usuario`, `operacion`, `estado`, `duracion_ms`), sin ruta real, cuerpo, parámetros, cookies ni cabeceras. `django.request` solo desde ERROR. `/api/health/` va en DEBUG;
  - retención: `expediente/retencion.py` en el planificador. Plazos `RETENCION_DIAS_<TIPO>` vacíos (pendiente V-04/P-07, `docs/alcance/plazos-retencion.md`): sin plazo no borra nada. Aplica a expedientes rechazados o suspendidos. Marca `eliminado_en`/`motivo_eliminacion` y escribe la bitácora `documento_eliminado_retencion` (Sistema). El documento eliminado no cuenta para aprobar; su enlace da 409 y curatoría no lo revisa (409).
- **Conversación (ADR-026, E-2; S5 inc. 4):**
  - tabla `mensaje` (solo inserción, triggers, `managed=False`, sin FK; CHECK `mensaje_texto_valido`, único `mensaje_envio_unico` (ticket, autor, clave_envio));
  - `GET|POST /api/tickets/<ref>/mensajes` (`mensajeria/vistas.py`, reglas en `mensajeria/conversacion.py`): `PoliticaTicket` (tercero y administrativos → 404 registrado); escribir solo en `aceptado` (otro → 409); leer en `aceptado`/`finalizado`; `cerrado` → lista vacía y `aviso` "No hubo conversación"; `pendiente` → 409; misma `clave_envio` → 200 con el mismo mensaje; `autor` = `tu`/`cliente`/`maestro`;
  - **ningún GET de mensajes renueva la sesión**: `identidad.middleware.SesionMiddleware` (reemplaza al `SessionMiddleware` de Django) respeta `request.sin_renovar_sesion`; abrir el pedido (`GET /api/tickets/<ref>`) y enviar sí renuevan;
  - aviso `mensaje_nuevo` a la otra parte con `enlace` a `conversacion.html`, reactivado con `tickets.avisos.emitir` (también lo usan los avisos de precio);
  - pantalla `conversacion.html?ticket=<ref>` (sondeo de 20 s solo visible, borrador `altiro.conversacion.<ref>`); "Ver conversación" en `mis-pedidos` y `mis-trabajos` (aceptado/finalizado). Reglas A-09 a A-15.
- **Evaluación y moderación (ADR-026, E-3 y E-4; S5 inc. 5-6):**
  - tablas `evaluacion` (único `(ticket, parte)`, notas 1..5, comentario ≤500, `publicada`/`retirada`, CHECK autor≠evaluado) y `denuncia` (único `(evaluacion, denunciante)`, CHECK de resolución completa);
  - `POST /api/tickets/<ref>/evaluacion` (solo `finalizado`; repetir → 409), `GET …/evaluaciones` → `{mia, recibida, puede_evaluar, aviso}`, `POST …/evaluacion-recibida/denuncia` (solo la parte evaluada, una vez); `PoliticaTicket`;
  - calificación en lectura (`evaluaciones/calificacion.py`): publicadas del cliente, redondeo mitad hacia arriba a 1 decimal; ficha pública con dimensiones y 10 comentarios sin autor; tarjeta de búsqueda en lote (`ordenar` la deja en `Candidato.calificacion`); desempate con el valor redondeado y la cantidad, antes del sorteo;
  - `/api/moderacion/denuncias[?estado=]`, `/<ref>`, `/<ref>/conversacion`, `/<ref>/resolucion`: `requiere_rol("moderacion")` + `PoliticaDenuncia` (moderador parte → `ConflictoDeInteres` 403 registrado, con `Politica.mensaje_conflicto`); conversación solo con denuncia `abierta` (si no, 404 registrado), bitácora `conversacion_consultada` y aviso `conversacion_revisada` a ambas partes; resolución → bitácora `denuncia_resuelta` (entidad `evaluacion`, estado anterior y nuevo);
  - pantallas `evaluar.html?ticket=`, `moderacion.html`; calificación en `perfil-maestro` y `buscar`; `ingresar.js` vuelve a `conversacion`/`evaluar` (con `ticket`) y `moderacion`. Reglas P-12 a P-14, C-16, C-17, A-16 a A-24.
- **Indicadores y exportación (ADR-026, E-6; S5 inc. 7):**
  - `GET /api/gestion/indicadores?desde=&hasta=` y `GET /api/gestion/exportacion?desde=&hasta=`: `requiere_rol("control_gestion")`; período de 31 a 366 días con ambas fechas incluidas (zona Santiago); fecha ausente o inválida → 400 en el campo; fuera de rango → 400 en `hasta`; otra clave → 400 general;
  - `gestion/indicadores.py`: concreción y primera respuesta con agregaciones en la base (`PERCENTILE_CONT`); primera respuesta solo cuenta eventos del maestro del ticket (`aceptado` o `rechazado_maestro`); vigencia documental a hoy, en lote, con las reglas puras de `expediente/vigencia.py`;
  - `gestion/exportacion.py`: CSV (UTF-8 con BOM) con `COLUMNAS` cerradas, supresión k=5 (maestros y clientes distintos), neutralización de `= + - @`, tabulador y retorno; bitácora `exportacion_agregada` (entidad `exportacion`, `valor_nuevo` = período, filas y suprimidas);
  - pantalla `indicadores.html` (enlace en `cuenta.html` para `control_gestion`; `ingresar.js` vuelve a `indicadores`). Reglas A-25, I-01 a I-04 y N-01 a N-05 (grupos `indicadores` y `anonimizacion` activos).
- **Avisos de tickets (ADR-024):** tabla `aviso_ticket`, sin datos personales. En pantalla se dice "pedido" y "horario".
- **Pruebas:** reglas críticas con `@pytest.mark.regla`, catalogadas en `tests/reglas_rnf21.py`, al menos 60 % por grupo (activos: filtros, puntaje, acceso, cierre, operación, indicadores y anonimización; precio final: C-09 a C-15, A-06 a A-08; operación: O-01 a O-04; conversación: A-09 a A-15). Fechas con time-machine; al saltar más de 30 min hay que volver a iniciar sesión (ver `tests/test_precio_final.py`, `_a`).
- **Datos:** solo ficticios. Nunca datos personales, contraseñas ni tokens en registros.

## Decisiones provisionales abiertas
ADR-016 E-1, ADR-018 a ADR-024 y ADR-026 están en "Aceptada — PROVISIONAL" y se revisan en la revisión del sprint. Las preguntas al representante P-01 a P-33 (`docs/alcance/preguntas-representante-s2.md`) siguen sin respuesta.

## Pendientes y riesgos vigentes
- **Pasan al S5 (DA-22 a DA-26):** RF-28 completo (precio acordado), evidencia de RF-11/CA-03.3 y calificación de RF-13/RF-14/CA-05.1, conversación de CA-15.2, RNF-03 con 5.000 mensajes (y nueva medición de RNF-01).
- **Para el representante (S4):** horarios alternativos del 409 (CA-06.2) como texto sin enlace; "Ingresar" desde `pedir-trabajo` sin retorno; sugerencias limitadas a 5.
- **Plazos:** `calcular_vence_en` y la proximidad se calculan en UTC (DEF-QA-005); toda aritmética de horas sobre fechas con zona Santiago debe pasar por UTC.
- **RNF-13** sin ejecutar (DA-26: antes de la revisión del S5; requiere personas). Riesgo más alto pendiente del equipo.
- **RNF-18:** falta el pase manual en navegadores de marca y en Android.
- **Observaciones del S3:** OBS-S3-02 (precios de referencia sin pantalla pública), OBS-S3-04 (scripts de Playwright sin el campo `bloques`) y OBS-S3-05 (contrastes del S3).

## Consumo de agentes (tokens informados al terminar)
| Fecha | Tarea | Agente / modelo | Tokens |
|---|---|---|---|
| 2026-09-29 | QA de cierre del S3 | qa (principal) | ~338 mil |
| 2026-09-29 | S4 incremento 4 (tickets) | backend (principal) | ~341 mil |
| 2026-09-30 | S4 incrementos 5 y 6 (transiciones y cierre) | backend (principal) | ~177 mil (69 pasos; dos incrementos juntos) |
| 2026-09-30 | QA de cierre del S4 (incremento 9) | qa (Sonnet) | ~195 mil (83 pasos) |
| 2026-09-30 | S4 incremento 7: QA y re-verificación (el código venía hecho; correcciones del coordinador) | qa (Sonnet) | ~331 mil (159 mil + 172 mil) |
| 2026-09-30 | Propuesta S5 y ADR-026 | architect (principal) | ~109 mil (36 pasos) |
| 2026-09-30 | S5 incrementos 1 y 2 (precio final, historial y pantallas) | backend (principal) | ~206 mil (69 pasos; dos incrementos juntos) |
| 2026-09-30 | S5 incremento 3 (respaldo, registro JSON y retención) | backend (principal) | ~197 mil (107 pasos) |
| 2026-09-30 | S5 incremento 4 (mensajería) | backend (principal) | ~177 mil (67 pasos) |
| 2026-09-30 | S5 incrementos 5 y 6 (evaluaciones, calificación y moderación) | backend (principal) | ~219 mil (64 pasos; se cortó por límite y se retomó) |
| 2026-09-30 | S5 incremento 7 (indicadores y exportación) | backend (principal) | ~162 mil (61 pasos) |
