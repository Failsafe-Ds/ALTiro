# Estado actual del proyecto (hoja corta para agentes)

> Leer esto **en lugar de** recorrer todos los ADR, propuestas y cierres. Abrir un ADR o una propuesta solo si el encargo lo cita o si una regla de abajo no alcanza. Si hay contradicción, prevalecen el informe y el ADR (CLAUDE.md §2).
> Actualizar esta hoja al cerrar cada incremento: una línea por cambio, sin narrativa.

Última actualización: 2026-10-12 (v0.6.8: contenido centrado en todas las páginas y ficha del maestro en dos columnas con panel «Pide un horario», E-4.3; antes: v0.6.7: carrusel sin botones, solo puntos, E-4.2 — sin botón de pausa, riesgo WCAG 2.2.2 PROVISIONAL; antes: v0.6.6: carrusel de oficios en abanico dinámico y encabezado rojo con botones blancos, ADR-002 E-4.1; antes: v0.6.5: Bootstrap 5.3.8 alojado y React permitido, ADR-002 E-4; carrusel de oficios con Bootstrap, «Tu cuenta» en una fila, contenido centrado; antes: pulido post-S5 en v0.6.4: ronda 2 — dos flujos, carrusel, «Sobre mí» DA-30, «Otros servicios» DA-31, cédula con vencimiento ADR-017 E-4 — y auditoría 2 del código `docs/testing/auditoria-codigo-ponytail-2.md` corregida; suite 2129 con `frontend/` montado; antes: v0.6.2: rediseño ADR-002 E-3, validaciones mínimas, auditoría del backend corregida, precio en resultados DA-29/ADR-022 E-2, QA `docs/testing/qa-pulido-post-s5.md` con DEF-QA-016 a 020 corregidos; suite 2091; antes: validaciones mínimas de formularios en CLAUDE.md §8-§9 y en los agentes; antes: 2026-10-04, ADR-032: copia de desarrollo `altiro-dev` separada de la de demostración; antes: 2026-09-30, S5 cerrado, etiqueta `sprint-5`; ADR-027 después del S5; suite 1920; siguiente: revisión del S5 y defensa; material en `docs/defensa/guion-defensa.md`).

## Sprints
| Sprint | Estado | Etiqueta / cierre |
|---|---|---|
| S1 Identidad, roles y acceso | Cerrado | `sprint-1`, `docs/testing/cierre-sprint-1.md` |
| S2 Expediente y curatoría | Cerrado | `sprint-2`, `cierre-sprint-2.md` |
| S3 Catálogo, cobertura y agenda | Cerrado con observaciones | `sprint-3`, `cierre-sprint-3.md` |
| S4 Búsqueda y ticket | Cerrado con observaciones | `sprint-4`, `cierre-sprint-4.md` |
| S5 Mensajería, evaluación, bitácora e indicadores | Cerrado con observaciones | `sprint-5`, `cierre-sprint-5.md` |

## Stack y cómo correr
- Docker Compose: `init`, `db` (PostgreSQL 16), `roles_db` y `migrador` (únicos, ADR-030), `app` (Django 5.2 + gunicorn), `proxy` (Nginx, TLS autofirmado, gzip), `planificador` (cada 300 s), `respaldo` (postgres:16, diario) y `pruebas` (perfil, no se levanta con `up`).
- Frontend estático en HTML, CSS y JS, sin framework y con CSP estricta (sin inline). Todas las páginas: `header` con menú por sesión y rol (`js/menu.js`, solo presentación), `main` y pie (ADR-002 E-2).
- **Suite completa** (Git Bash, desde la raíz): `MSYS_NO_PATHCONV=1 docker compose run --rm -v "$(pwd -W)/backend:/app" -v "$(pwd -W)/frontend:/frontend:ro" pruebas -q` (servicio `pruebas`, imagen con pytest; la imagen `app` ya no lo tiene, ADR-030 B7; tras cambiar `requirements-pruebas.txt`: `docker compose build pruebas`) (el montaje de `frontend/` lo usa `test_frontend_pie_volver.py`; sin él esa prueba se omite). Tarda unos 10 min y hoy pasan 2044.
- **Durante el desarrollo**, solo pruebas dirigidas: el mismo comando con `tests/test_x.py -k nombre`.
- Migrar: `docker compose up -d` (o `docker compose run --rm migrador`): migra el rol dueño `altiro_migrador`; `altiro_app` solo tiene DML y `exec app … migrate` ya no sirve para DDL (ADR-030 B8). Si `app` se recrea, el proxy no necesita reinicio (resuelve `app` en cada petición, `altiro-api.inc`). Tras cambiar la plantilla del proxy: `docker compose up -d --force-recreate proxy`.
- **Dos copias en el equipo (ADR-032):** esta carpeta es la de desarrollo, con `.env` local → proyecto `altiro-dev`, imágenes `altiro-dev-*:local`, `https://localhost:8443`. Una copia clonada de GitHub para mostrar va sin `.env` → `altiro`, `https://localhost`. Los comandos `docker compose …` de esta hoja, ejecutados aquí, actúan sobre `altiro-dev`.

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
  - sugerencias en una sección aparte, de toda la región con la misma provincia primero (E-1, 2026-10-04);
  - la tarjeta muestra "Atiende en: …" (hasta 3 comunas y cuántas más), sin marcar la base (E-1);
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
  - respaldo: `scripts/respaldo.sh` (dump, conteos, tar, sumas; 7 días) hacia `ALTIRO_RESPALDO_DIR` (`../altiro-respaldos`), **cifrado con gpg AES-256 y `secretos/respaldo_clave`** (ADR-030 B6; sin la clave no se restaura). `scripts/restaurar.sh` se niega si existe algún volumen del proyecto destino. El simulacro solo se hace en `-p altiro-restauracion` (`docs/testing/rnf-19-respaldo.md`: 19 s);
  - registro: JSON por línea (`comun/registro.py`: `nivel`, `marca_tiempo`, `usuario`, `operacion`, `estado`, `duracion_ms`), sin ruta real, cuerpo, parámetros, cookies ni cabeceras. Dentro de una petición, `usuario` es el de la petición (o `anonimo`); `sistema` solo fuera de peticiones (DEF-QA-015). `django.request` solo desde ERROR. `/api/health/` va en DEBUG;
  - retención: `expediente/retencion.py` en el planificador. Plazos `RETENCION_DIAS_<TIPO>` vacíos (pendiente V-04/P-07, `docs/alcance/plazos-retencion.md`): sin plazo no borra nada. Aplica a expedientes rechazados o suspendidos. Marca `eliminado_en`/`motivo_eliminacion` y escribe la bitácora `documento_eliminado_retencion` (Sistema). Un archivo que no se puede descifrar da 409 accionable (volver a cargarlo), nunca 500. El documento eliminado no cuenta para aprobar; su enlace da 409 y curatoría no lo revisa (409).
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
  - `gestion/exportacion.py`: CSV (UTF-8 con BOM) con `COLUMNAS` cerradas, supresión k=5 (maestros y clientes distintos); mediana vacía si hay menos de 5 finalizadas o menos de 5 maestros o clientes distintos entre ellas (E-6.5, DEF-QA-014); neutralización de `= + - @`, tabulador y retorno; bitácora `exportacion_agregada` (entidad `exportacion`, `valor_nuevo` = período, filas y suprimidas);
  - **E-6.6 (2026-10-01, M2):** período en meses cerrados `AAAA-MM` (1 a 12, `hasta` anterior al mes en curso; reemplaza los 31 a 366 días); CSV vacía `ordenes_finalizadas` de 1 a 4 con supresión complementaria por mes; indicadores con un conteo de 1 a 4 (mes a mes) salen `suprimido`; `umbral` en la respuesta; reglas I-05, N-07, N-08;
  - pantalla `indicadores.html` (enlace en `cuenta.html` para `control_gestion`; `ingresar.js` vuelve a `indicadores`). Reglas A-25, I-01 a I-04 y N-01 a N-05 (grupos `indicadores` y `anonimizacion` activos).
- **Credenciales y recuperación (ADR-027, DA-27; después del S5):**
  - `POST /api/cuenta/contrasena {contrasena, contrasena_nueva}` y `POST /api/cuenta/correo {contrasena, correo}`: reautenticación con la contraseña actual (RNF-09) y limitador con clave `cuenta:<id>` (RNF-10, 429). Cambiar la contraseña invalida las demás sesiones (hash de sesión) y renueva la propia. `cambiar_correo` también agrega el primer correo de un maestro;
  - `POST /api/recuperacion {identificador}` (pública): siempre 202 con el mismo mensaje; 5 por origen en 15 min → 429; 3 enlaces por cuenta y hora. `POST /api/recuperacion/contrasena {token, contrasena_nueva}` (pública): un solo uso, 30 min, no inicia sesión. Tabla `solicitud_recuperacion` (solo el SHA-256 del token; borra lo de más de 24 h);
  - enlace `…/nueva-contrasena.html#t=<token>` (fragmento: no llega al proxy); correos en el volumen `buzon` (backend de archivos, solo en `app`); recuperación asistida con `manage.py crear_enlace_recuperacion --cuenta`. Sin bitácora (M-03), evento de aplicación sin token. Reglas A-26 a A-30;
  - pantallas `recuperar.html`, `nueva-contrasena.html` y «Seguridad de mi cuenta» en `cuenta.html`.
- **Frecuencia (ADR-007 E-1 y ADR-027 E-1, 2026-10-01; ratificación pendiente):** `identidad/frecuencia.py` + tabla `evento_frecuencia`; registro sin sesión 20/h por origen; mensajes 5/10 s y 60/h por parte y ticket (cuenta desde `mensaje`); denegaciones 20/10 min por usuario → 429 en lugar de 404/403, sin fila en `acceso_denegado`; recuperación con bloqueo por origen y fila de usuario, correo en hilo aparte (`ALTIRO_CORREO_EN_SEGUNDO_PLANO=False` en pruebas). Pruebas en `tests/test_frecuencia.py`.
- **Datos de demostración (ADR-028, Borrador, 2026-10-01):** `cargar_datos_demo --con-cuentas [--restablecer-contrasenas]` crea 10 maestros publicados (RUT 49.990.001+), 2 clientes y 4 tickets; contraseña aleatoria impresa una vez; reglas compartidas en `busqueda/ficticios.py` (también las usa `generar_volumen_prueba`); `limpiar_oficios_de_prueba [--confirmo]` para los oficios que dejó QA del S3 (no ejecutado). Pruebas en `tests/test_cuentas_demo.py`.
- **ADR-028 E-1 (2026-10-01):** `cargar_datos_demo --maestros-por-comuna [N] [--region R]` (1-10, por defecto 3) garantiza N maestros demo publicados con base en cada comuna (RUT 48.000.000 + comuna·100 + puesto, sin ingreso; oficios rotados, regulados con licencia SEC sintética cifrada vía `cargar_documento`; algunos bloques ocupados y evaluaciones; 20 clientes `cliente.volumen.demo.NN`); `--con-cuentas` crea además `<rol>.demo@example.com` por rol administrativo. Código en `busqueda/maestros_por_comuna.py`; pruebas en `tests/test_maestros_por_comuna.py`.
- **ADR-028 E-2 (2026-10-04):** hasta 99 por comuna, `--comuna C` (repetible) y zona densa (desde el puesto 40, cubre de 3 a 6 comunas de la provincia, primero las de `--comuna`). Carga recomendada en el README: ~3.500 maestros, 51 a 69 por oficio en el Gran Concepción y el Gran Santiago.
- **Ayudas compartidas (revisión de redundancias, 2026-09-30):** `frontend/js/dom.js` (`dom.elemento`, `dom.opcion`) en lugar de las copias por página; `comun.api.respuesta_json` (JSON con `no-store`); `perfil.ocurrencias.iso_local`; `identidad.autenticacion.buscar_usuario`; `TextChoices.values` en los CHECK de los modelos.
- **Limitación en el proxy (ADR-029, Borrador, 2026-10-01):** 100/s ráfaga 200 por IP en todo el sitio; 20/min ráfaga 30 en POST de sesión, registro y recuperación; 50 en curso por IP; 429 en JSON `{mensaje, errores}` con `Retry-After` (páginas: `errores/429.html`). Capa extra: ADR-007 sigue igual. Cabeceras en `infra/proxy/templates/altiro-cabeceras.inc.template`; verificación con `python infra/proxy/verificar_proxy.py`.
- **Endurecimiento operativo (ADR-030, Propuesta, 2026-10-01):** planificador purga sesiones expiradas y correos del buzón con más de 30 min + 24 h; respaldo cifrado; imagen `app` sin pytest (servicio `pruebas`); `altiro_migrador` dueño del esquema y `altiro_app` solo DML (no puede desactivar triggers); B4 (IP del gateway con Docker Desktop) documentado en README. Pruebas: `tests/test_planificador_purgas.py`, `tests/test_roles_base_datos.py`.
- **Rediseño visual (ADR-002 E-3, 2026-10-11, pendiente de implementar):** referencia Fiverr (foto arriba e información debajo, sin tarjeta), tonos rojos, menú lateral en páginas de opciones, encabezado sin sesión solo con la marca, sin botones «Volver» (la marca vuelve al inicio), inicio por rol (cliente → categorías; maestro → `mis-trabajos`; curatoría → `curatoria`). Hasta implementarlo, el frontend actual sigue como está.
- **Pulido post-S5 (2026-10-11, v0.6.1, fuera de sprint):** auditoría `ponytail-audit` del backend (`docs/testing/auditoria-backend-ponytail.md`) con los 8 hallazgos corregidos; ayudante único de texto `comun/texto.py` (`limpiar_texto`, `recortar`: recorta, nulo y control → 400, solo espacios = vacío; la contraseña nunca pasa por ahí), `perfil.servicios.validar_monto` pública; scripts de QA del S5 sin contraseña fija (`QA_S5_CONTRASENA`). Frontend: `formulario.js` con `ocupado`, `terminado` y `resultado`, resumen de errores y recorte; `opciones.js` (menú lateral); `categorias.html`; `iconos.js`; fuente en `frontend/fuentes/`. Inventario en `docs/testing/validaciones-minimas-pantalla.md`. Suite: 2088.
- **Auditoría 2, frontend (2026-10-11, v0.6.4):** `js/bandeja.js` (común a `mis-pedidos` y `mis-trabajos`); `dom.sesionTerminada`/`dom.enlaceIngresar`; `formulario.formatearRut`, `guardarTexto`/`recuperarTexto` (borradores de conversación y evaluación en `localStorage`, vencen a las 2 h); pegado seguro en `email`; error de campo se limpia al corregir; `api.js` con tiempo límite 20 s (JSON) y 120 s (fotos); comunas de la última región; menú borra borradores al salir. Prueba de navegador `scripts/qa-pulido/formulario_pegado_y_salir.py`.
- **Bootstrap y React (2026-10-12, v0.6.5, ADR-002 E-4):** Bootstrap 5.3.8 en `frontend/vendor/bootstrap-5.3.8/` (sin CDN, archivos sin editar, SHA-256 en el ADR); su CSS en todas las páginas **antes** de `css/base.css`, que le pasa los colores de MASTER (`--bs-*`); su JS solo donde hay un componente con JS (hoy `categorias.html`). Clases propias siguen; se migra pantalla por pantalla. React permitido solo con paso de compilación (sin CDN ni Babel en el navegador; CSP intacta) y enmienda E-5 antes de la primera pantalla. Carrusel de oficios: en abanico, código propio, avanza solo con pausa (E-4.1); hoy ninguna página carga el JS de Bootstrap. Encabezado rojo, marca blanca, botones blancos con contorno negro y foco blanco (E-4.1).
- **Validación en pantalla (ADR-031, Propuesta, 2026-10-03):** `frontend/js/formulario.js` (`revisar`, `errorRut`, `errorCorreo`, `errorIdentificador`) con `data-validar="rut|correo|identificador"`; replica exactamente `normalizar_rut` e `interpretar_identificador` con los mismos textos; el servidor sigue siendo la validación que vale.
- **Validaciones mínimas (CLAUDE.md §8-§9, 2026-10-11):** largo máximo, espacios sobrantes (salvo contraseña), indicador de carga, mensajes claros, no borrar el formulario, limpiar tras el éxito y mensaje de resultado; sin credenciales en el código; volver a ingresar tras cerrar la ventana. Verificadas en el QA del pulido (`docs/testing/qa-pulido-post-s5.md`; inventario en `docs/testing/validaciones-minimas-pantalla.md`).
- **Rediseño parte 2 (ADR-002 E-3.1, PROVISIONAL, 2026-10-11, v0.6.1):** `js/opciones.js` (menú lateral de páginas de opciones con `<main data-opciones>`; `cuenta.html#datos|#seguridad|#perfiles`); `menu.js` comparte `window.altiroCuenta`; «← Paso anterior» solo en los 5 formularios por pasos; `formulario.js` recorta espacios (no contraseñas), resume errores y enfoca el primero, `terminado`/`resultado`; inventario en `docs/testing/validaciones-minimas-pantalla.md`.
- **Avisos de tickets (ADR-024):** tabla `aviso_ticket`, sin datos personales. En pantalla se dice "pedido" y "horario".
- **Pruebas:** reglas críticas con `@pytest.mark.regla`, catalogadas en `tests/reglas_rnf21.py`, al menos 60 % por grupo (activos: filtros, puntaje, acceso, cierre, operación, indicadores y anonimización; precio final: C-09 a C-15, A-06 a A-08; operación: O-01 a O-04; conversación: A-09 a A-15). Fechas con time-machine; al saltar más de 30 min hay que volver a iniciar sesión (ver `tests/test_precio_final.py`, `_a`).
- **Datos:** solo ficticios. Nunca datos personales, contraseñas ni tokens en registros.
- **Sobre mí, cédula y oficio «Otros servicios» (2026-10-11, pulido post-S5):** `perfil_publico.descripcion` (DA-30), opcional, hasta 500, `PUT /api/maestros/perfil` y ficha pública, fuera de búsqueda y puntaje; la **cédula exige `fecha_vencimiento`** en cargas nuevas (ADR-017 E-4); noveno oficio `otros` «Otros servicios», no regulado (DA-31, CSV + `catalogo/0008`).

## Decisiones provisionales abiertas
ADR-016 E-1, ADR-018 a ADR-024 y ADR-026 están en "Aceptada — PROVISIONAL" y se revisan en la revisión del sprint. Las preguntas al representante P-01 a P-33 (`docs/alcance/preguntas-representante-s2.md`) siguen sin respuesta.

## Pendientes y riesgos vigentes
- **Cerrados en el S5:** DA-22 a DA-25 (precio acordado, calificación y desempate, conversación, RNF-03 con 5.000 mensajes y RNF-01). DEF-QA-013 a 015 corregidos y verificados.
- **Pendientes del equipo tras el S5:** revisar el primer respaldo automático (2026-10-01 03:00) y definir dónde se guarda la copia de la clave de cifrado (ADR-026 E-7.2); plazos de retención RNF-26 (P-30, V-04); P-24 a P-33. OBS-S5-06 corregida (el visor muestra el mensaje del 409).
- **Antes (S4) pasaban al S5 (DA-22 a DA-26):** RF-28 completo (precio acordado), evidencia de RF-11/CA-03.3 y calificación de RF-13/RF-14/CA-05.1, conversación de CA-15.2, RNF-03 con 5.000 mensajes (y nueva medición de RNF-01).
- **Para el representante (S4):** horarios alternativos del 409 (CA-06.2) como texto sin enlace; "Ingresar" desde `pedir-trabajo` sin retorno; sugerencias limitadas a 5.
- **Plazos:** `calcular_vence_en` y la proximidad se calculan en UTC (DEF-QA-005); toda aritmética de horas sobre fechas con zona Santiago debe pasar por UTC.
- **RNF-09** cerrado el 2026-09-30 con ADR-027 (DA-09 cerrado por DA-27; P-11 respondida por el equipo).
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
| 2026-09-30 | S5 incremento 8 (volumen de 5.000 mensajes y mediciones RNF-01/RNF-03) | qa (Sonnet) | ~98 mil (31 pasos) |
| 2026-09-30 | QA de cierre del S5 | qa (Sonnet) | ~223 mil (93 pasos) |
| 2026-09-30 | Revisión UX del S5 | ux (Sonnet) | ~62 mil (19 pasos) |
| 2026-09-30 | Correcciones DEF-QA-014/015 y documento ilegible | backend (principal) | ~100 mil (37 pasos) |
| 2026-09-30 | Correcciones DEF-QA-013 y UX-S5-01 a 13 | frontend (Sonnet) | ~90 mil (21 pasos) |
| 2026-10-11 | Pulido post-S5: auditoría del backend (ponytail-audit) | general-purpose (principal) | ~215 mil (74 pasos) |
| 2026-10-11 | Pulido post-S5: rediseño parte 1 (base, encabezado, sin «Volver», inicio por rol, categorías, búsqueda) | frontend (principal) | ~215 mil (105 pasos) |
| 2026-10-11 | Pulido post-S5: correcciones de la auditoría (hallazgos 1 a 8, `comun/texto.py`) | backend (principal) | ~155 mil (81 pasos) |
| 2026-10-11 | Pulido post-S5: rediseño parte 2 (menú lateral, resto de pantallas) y validaciones mínimas en pantalla | frontend (principal) | ~213 mil (82 pasos) |
| 2026-10-11 | Pulido post-S5: precio en resultados de búsqueda (DA-29, ADR-022 E-2) | backend (principal) | ~94 mil (30 pasos) |
| 2026-10-11 | Pulido post-S5: QA final con sesión en todos los roles (DEF-QA-016 a 020) | qa (Sonnet) | ~227 mil (83 pasos) |
| 2026-10-11 | Pulido post-S5: corrección DEF-QA-016 a 020 y precio verificado en pantalla (v0.6.2) | frontend (Sonnet) | ~89 mil (21 pasos) |
| 2026-10-11 | Pulido post-S5 ronda 2: flujos, ingresar, cuenta, postulación y documentos (v0.6.3) | frontend (principal) | ~201 mil (83 pasos) |
| 2026-10-11 | Pulido post-S5 ronda 2: carrusel, centrado y encabezado (E-3.3) | frontend (principal) | ~27 mil adicionales (23 pasos; continuación del mismo agente) |
| 2026-10-11 | Pulido post-S5 ronda 2: descripción del maestro (DA-30), cédula con vencimiento (ADR-017 E-4), oficio «Otros servicios» (DA-31) | backend (principal) | ~164 mil (98 pasos) |
| 2026-10-11 | Pulido post-S5 ronda 2: «Sobre mí» en mi-perfil y ficha pública (DA-30) | frontend (principal) | ~28 mil adicionales (20 pasos; continuación) |
| 2026-10-11 | Pulido post-S5 ronda 2: servicio demo de «Otros servicios», rotación de oficios y maestros demo nuevos | backend (principal) | ~19 mil adicionales (continuación) |
| 2026-10-11 | Pulido post-S5: auditoría 2 del código (frontend completo + backend nuevo), 11 hallazgos | general-purpose (principal) | ~218 mil (se cortó por límite y se retomó) |
| 2026-10-11 | Pulido post-S5: QA ronda 2 (41 verificaciones, DEF-QA-021) | qa (Sonnet) | ~198 mil en la parte retomada (se cortó por límite) |
| 2026-10-11 | Pulido post-S5: auditoría 2 backend (H7, H11) y dos ajustes del QA | backend (principal) | ~92 mil (40 pasos) |
| 2026-10-11 | Pulido post-S5: auditoría 2 frontend (H1-H6, H8-H10), DEF-QA-021 (v0.6.4) | frontend (principal) | ~194 mil (77 pasos) |
| 2026-10-12 | Bootstrap 5.3.8 y React permitido (ADR-002 E-4): carrusel, «Tu cuenta», centrado (v0.6.5) | coordinador (sin agentes) | sin medición por agente; hecho directo para no relanzar contexto |
| 2026-10-12 | Carrusel en abanico y encabezado rojo (ADR-002 E-4.1, v0.6.6) | coordinador (sin agentes) | sin medición por agente |
| 2026-10-12 | Carrusel sin botones (ADR-002 E-4.2, v0.6.7) | coordinador (sin agentes) | sin medición por agente |
| 2026-10-12 | Contenido centrado y ficha del maestro más corta (ADR-002 E-4.3, v0.6.8) | coordinador (sin agentes) | sin medición por agente |
