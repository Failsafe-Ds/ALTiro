# Verificación del saneamiento final — Sprint 1

- Fecha: 2026-09-28
- Preparado por: agente `qa`
- Código verificado: rama `main`, commit `e776b70`, más la prueba nueva `backend/tests/test_qa_saneamiento_s1.py` (sin commit).
- Commits del saneamiento revisados: `8d54f3c` (bitácora de alcance, OBS-01), `ff323ad` (DEF-QA-004), `6a10c27` (DEF-QA-001, 002, 003 y hallazgo UX M-1) y `e776b70` (señal de rechazo CSRF). DEF-QA-005 se corrigió antes, en `b6dea6d`.
- Fuentes: `CLAUDE.md`; `docs/testing/cierre-sprint-1.md`; `docs/alcance/bitacora-de-alcance.md`; ADR-003 (Enmienda E-1), ADR-006 (E-1), ADR-010 y ADR-011 (E-1), todas Aceptadas; `docs/testing/plan-identidad-sprint-1.md`.

**Veredicto: saneamiento completo con observaciones.** Los defectos DEF-QA-001 a DEF-QA-005 y OBS-01 están corregidos y verificados. La señal CSRF funciona como exigen las enmiendas. La suite pasa completa y no hay regresiones. Quedan abiertos DEF-QA-006, que sigue siendo bajo, y el defecto nuevo DEF-QA-007, de severidad media: un `IntegrityError` no traducido escribe en los registros de `app` el hash y los datos personales. También siguen pendientes RNF-23 en un equipo limpio y los hallazgos de UX en backlog. Ninguno es crítico ni alto. Se recomienda corregir DEF-QA-007 antes de que el S2 agregue restricciones nuevas.

---

## 1. Alcance

| Punto | Qué se verifica | Requisitos |
|---|---|---|
| A | Base local recreada: no queda la fila accidental de bitácora ni filas de `sistema`, y las migraciones aplican desde cero | RNF-11, ADR-010, OBS-01 |
| B | DEF-QA-001: mensajes accionables con sesión iniciada | HU-01, HU-11, RNF-15 (revisión anticipada), ADR-013 E-2 |
| C | DEF-QA-002: la sesión expira en "Mi cuenta" | RF-02, RNF-09, RNF-15 |
| D | DEF-QA-003: cerrar sesión sin conexión | RF-02 |
| E | DEF-QA-004: registros de PostgreSQL sin datos personales | CLAUDE.md §8, RNF-05, ADR-003 E-1 |
| F | 403: el rechazo CSRF se reintenta una vez; la falta de rol no se reintenta y deja una sola fila | RNF-07, HU-25, ADR-006 E-1, ADR-011 E-1 |
| G | Regresión del S1 | RF-01 a RF-03, RNF-05 a RNF-12, RNF-24 |

Fuera de esta verificación: RNF-23 en un equipo limpio (DA-11) y los RNF de sprints posteriores.

## 2. Entorno

| Dato | Valor |
|---|---|
| Equipo | Equipo de desarrollo, Windows 11 Pro 10.0.26200 |
| Docker | Engine 29.8.0, Compose v5.5.1 |
| Pila | `docker compose up -d --build --wait`: `db` (postgres 16.15), `app`, `proxy` (nginx 1.30.5) sanos; `init` terminado |
| Base principal | Volumen `altiro_datos_db` creado el 2026-09-28 a las 14:50:15 UTC. Tiene cuentas ficticias `@example.com` creadas por las verificaciones de los agentes (21 al final de esta QA) |
| Base de pruebas | `test_altiro`, recreada con `pytest --create-db` |
| Navegador | Chromium de `mcr.microsoft.com/playwright/python:v1.55.0-noble` en la red `altiro_frontal`, en 390 x 844 con `is_mobile` |
| Scripts | Del agente frontend: `flujo.py`, `defectos.py`, `perfil_otra_pestana.py` y `csrf_m1.py`. De QA: `qa/s1s/carrera.sh` y `qa/s1s/qa_saneamiento.py`, todos en la carpeta scratchpad de la sesión |

## 3. Pruebas ejecutadas

| # | Prueba | Resultado |
|---|---|---|
| 1 | `docker compose exec -T app pytest -q --create-db` (imagen actual, antes de la prueba nueva) | 504 aprobadas |
| 2 | `docker compose run --rm -v backend:/app --entrypoint pytest app -q` (código montado, antes de la prueba nueva) | 504 aprobadas |
| 3 | La misma suite, con `test_qa_saneamiento_s1.py` | **505 aprobadas y 1 xfail** (DEF-QA-007) |
| 4 | Subconjunto F/G: `test_senal_csrf` (15), `test_autorizacion`, `test_acceso_denegado`, `test_api_privado_por_defecto`, `test_registros_base_datos` y `test_configuracion` | 78 aprobadas |
| 5 | SQL sobre la base principal: `bitacora`, `acceso_denegado`, triggers y `django_migrations`; `showmigrations`; `migrate --check --plan` | Ver A |
| 6 | Carrera real: 6 `POST /api/clientes` simultáneos con el mismo correo por HTTPS, seguidos de `docker compose logs db` | Ver E |
| 7 | FATAL de autenticación desde `app` y `TRUNCATE bitacora` en una transacción revertida de `test_altiro` | Ver E |
| 8 | Navegador: `csrf_m1.py`, `defectos.py`, `perfil_otra_pestana.py`, `flujo.py` y `qa_saneamiento.py` | 0 fallos |
| 9 | curl: 307, certificado, HSTS, 401, 403 CSRF en vivo, 404 y páginas del proxy | Ver G |

## 4. Resultados

| Punto | Verificación | Método y evidencia | Resultado |
|---|---|---|---|
| A.1 | No existe la fila accidental (`id = 1`, autor `sistema`, acción `verificacion`) | SQL: `count(*) from bitacora` = 0; `where id=1` = 0 | **PASS** |
| A.2 | No hay filas con `autor_tipo = 'sistema'` | SQL = 0. `acceso_denegado` = 0 al inicio y al final | **PASS** |
| A.3 | Los triggers de solo inserción están activos | `pg_trigger`: `bitacora_sin_cambios`, `bitacora_sin_truncate`, `acceso_denegado_sin_cambios` y `acceso_denegado_sin_truncate` con `tgenabled = O` | **PASS** |
| A.4 | Las migraciones aplican desde cero | `pytest --create-db` recreó `test_altiro` desde cero (504 aprobadas). En la base principal, las 8 migraciones se aplicaron entre las 14:50:22,23 y las 14:50:22,34 UTC, 7 s después de crear el volumen. `showmigrations` las muestra todas `[X]` y `migrate --check --plan` informa "No planned migration operations" | **PASS** |
| B.1 | Con sesión, registro y postulación no ofrecen el formulario de visitante y lo explican | `defectos.py`: "Tu cuenta ya puede pedir trabajos. No necesitas crear otra." y "…escribe tu RUT en «Mi cuenta»", con enlace a `cuenta.html`, sin scroll horizontal y con objetivos de al menos 44 px | **PASS** |
| B.2 | La sesión iniciada en otra pestaña durante el llenado no muestra el mensaje genérico | `defectos.py`, casos "carrera" (deriva a la cuenta, borra la contraseña del DOM y no la guarda) y "respaldo" sin `/api/cuenta` ("Parece que se inició una sesión… Recarga la página…") | **PASS** |
| B.3 | Nunca aparece "Este dato no corresponde aquí" en los flujos con sesión | `qa_saneamiento.py`: texto de `main` en registro, postulación y "Mi cuenta" con RUT inválido y con RUT de otra cuenta ("Ese RUT ya tiene una postulación…"); 0 apariciones. `perfil_otra_pestana.py`: "Tu cuenta ya tiene el perfil de cliente." | **PASS** |
| C.1 | La sesión expirada no se convierte en un registro de visitante | `qa_saneamiento.py`: la sesión se cerró en el servidor (DELETE 204 desde otra pestaña) y se repuso la cookie vieja. Al "Postular", el único POST fue `/api/maestros/postulaciones` con la clave `rut`. SQL: 0 perfiles de maestro con ese RUT | **PASS** |
| C.2 | Aviso claro | "Tu sesión terminó. Vuelve a ingresar para continuar. Lo que escribiste seguirá aquí…", con el botón "Ingresar de nuevo" y el foco en el aviso (`defectos.py`) | **PASS** |
| C.3 | No pide nombre ni contraseña | Sin "Ingresa tu nombre" ni "Ingresa una contraseña" y sin campos de contraseña visibles | **PASS** |
| C.4 | Nada se guarda con contraseña | `sessionStorage` y `localStorage` no contienen la contraseña ni la clave `contrasena`. Lo pendiente se devuelve solo a la misma cuenta (huella SHA-256) y otra cuenta no lo ve (`defectos.py`). Se guarda el RUT sin vencimiento: es M-4 (backlog) | **PASS** |
| D.1 | Sin conexión informa el fallo y no finge éxito | `qa_saneamiento.py` y `defectos.py`: la pantalla sigue en `cuenta.html` con "No pudimos cerrar tu sesión porque no hay conexión: tu sesión sigue abierta en este teléfono…", y el botón queda habilitado | **PASS** |
| D.2 | La sesión del servidor sigue activa | Al volver la conexión, antes de reintentar, `GET /api/cuenta` = 200 | **PASS** |
| D.3 | El reintento con conexión cierra la sesión | DELETE 204, `index.html` con "Cerraste tu sesión…", `/api/cuenta` = 401; la cookie anterior en un contexto nuevo = 401. Un 500 simulado también informa el fallo; un 401 se trata como sesión cerrada | **PASS** |
| E.1 | Colisión real de unicidad | `carrera.sh`: 6 registros simultáneos, 1 con 201 y 5 con 400 "Este correo ya está registrado…". Uno de ellos llegó a la UNIQUE | **PASS** |
| E.2 | El log de `db` no tiene `STATEMENT:`, `DETAIL:` ni datos ficticios | `docker compose logs db` completo (241 líneas): 0 `STATEMENT:`, 0 `DETAIL:`, 0 `HINT/CONTEXT/QUERY`, 0 `example.com`, `argon2`, teléfonos o nombres. `SHOW`: `log_min_error_statement = panic`, `log_error_verbosity = terse`, `log_min_messages = warning`, `log_statement = none` | **PASS** |
| E.3 | Queda la línea ERROR con el nombre de la restricción | `16:28:55.351 UTC ERROR: duplicate key value violates unique constraint "usuario_correo_unico"`. El cliente sigue recibiendo el error por campo | **PASS** |
| E.4 | Los errores relevantes siguen registrándose | `FATAL: password authentication failed for user "altiro_app"` (conexión con clave errónea desde `app`) y `ERROR: La bitácora no admite TRUNCATE (RNF-11)` (transacción revertida en `test_altiro`) | **PASS** |
| F.1 | CSRF inválido: se renueva y se reintenta como máximo una vez | pytest `test_secuencia_rechazo_csrf_…` y `test_registro_tras_rechazo_csrf_y_reintento_crea_exactamente_una_cuenta`. `csrf_m1.py` (b): POST, GET csrf, POST, 201; (c): dos 403 CSRF dan exactamente 2 POST y devuelven 403; (e) de extremo a extremo con la cookie inválida: 403 `csrf`, luego 204 y 201. En vivo: `DELETE /api/sesion` sin token responde 403 con `AlTiro-Rechazo: csrf` | **PASS** |
| F.2 | La falta de rol NO se reintenta | `csrf_m1.py` (a): un 403 sin la cabecera da 1 POST y 0 GET csrf. `api.js` reintenta solo si `metodo !== "GET" && resultado.rechazoCsrf`, y `rechazoCsrf` exige 403 y `AlTiro-Rechazo === "csrf"`. La señal no sale del módulo. pytest `test_ninguna_otra_respuesta_lleva_la_senal` (400, 401, 403 sin rol, 404, 405 y 429) | **PASS** |
| F.3 | La falta de rol deja exactamente una fila en `acceso_denegado` y la respuesta final es 403 | pytest `test_falta_de_rol_con_csrf_valido_…_deja_una_fila` y la secuencia CSRF + reintento: 0 filas tras el rechazo CSRF y 1 tras el 403 por rol. `test_csrf_se_verifica_antes_que_la_autorizacion` | **PASS** |
| F.4 | Alcance de la verificación en navegador | En el S1 ninguna ruta de producción usa `@requiere_rol`: en el navegador, la falta de rol se probó con un 403 simulado sin cabecera, y la fila, con la ruta de prueba de pytest | Nota (no es un resultado) |
| G.1 | Suite completa | 505 aprobadas y 1 xfail (DEF-QA-007); 504 antes de agregar la prueba nueva | **PASS** |
| G.2 | HTTPS | `http://127.0.0.1/cuenta.html`: 307 a `https://127.0.0.1:443/cuenta.html`. Certificado autofirmado "AlTiro demo local", SAN `DNS:localhost` e `IP:127.0.0.1`, vigente del 2026-09-28 al 2027-09-28. Sin `Strict-Transport-Security` en `/` ni en `/api/health/` (ADR-008). `/api/health/` responde `{"estado": "ok", "base_datos": "ok"}` | **PASS** |
| G.3 | Inicio de sesión, registro de cliente, postulación de maestro, segundo perfil y cierre de sesión | `flujo.py`: registro por pasos con progreso conservado al recargar, 401 genérico, cuenta, RUT inválido, perfil de maestro agregado ("Cliente, Maestro"), cierre de sesión, maestro sin correo y objetivos de al menos 44 px. `defectos.py`: perfil de cliente agregado a una cuenta de maestro. `perfil_otra_pestana.py` | **PASS** |
| G.4 | Autorización | `GET /api/cuenta` sin sesión = 401 en vivo. pytest `test_toda_ruta_privada_responde_401_sin_sesion`, `test_recurso_ajeno_responde_el_mismo_404_que_uno_inexistente_y_se_registra`, `test_un_uuid_inexistente_no_se_registra` y `test_tener_el_rol_curatoria_no_da_acceso…`. En vivo, el 404 de la API es JSON y el mismo cuerpo para dos rutas inexistentes. El S1 no tiene rutas de producción con identificador, así que el 404 de un recurso ajeno se verifica solo con la ruta de prueba (DA-03) | **PASS** |
| G.5 | Registros de `app` | `docker compose logs app` (69 líneas): 0 `Traceback`, 0 `Failing row`, 0 `argon2`, `csrftoken`, `sessionid` o `@example.com` | **PASS** |

No hay resultados **FAIL** en A a G. El defecto nuevo DEF-QA-007 está fuera de los puntos A a G y se trata en la sección 5.

## 5. Defectos nuevos

### DEF-QA-007 — Un `IntegrityError` no traducido escribe el hash y datos personales en los registros de `app`
- **Afecta:** CLAUDE.md §8 ("No escribir secretos, contraseñas, tokens, documentos ni datos personales innecesarios en logs"); RNF-05 (el hash es material de ataque fuera de línea); la minimización que motivó ADR-003 E-1, esta vez del lado de la aplicación; R-03.
- **Severidad:** media. Solo ocurre ante un error de programación, porque el servicio normaliza antes de guardar. Pero afecta a todo `IntegrityError` que `_guardar` relance (`raise`), y desde el S2 aparecen restricciones sobre documentos, direcciones y tickets.
- **Precondición:** una violación de restricción que el servicio no traduce, por ejemplo `usuario_telefono_formato`.
- **Pasos para reproducir** (en proceso, datos ficticios, sin tocar código de producción): `backend/tests/test_qa_saneamiento_s1.py`. Se hace que `servicios.normalizar_telefono` devuelva `+00910000077` (12 caracteres, no cumple el CHECK) y se envía `POST /api/clientes` con `Client(raise_request_exception=False)`, capturando los registros con `caplog`.
- **Esperado:** 500 genérico hacia el cliente. El registro anota el error y el nombre de la restricción, sin valores de la fila.
- **Observado:** el cliente recibe un 500 genérico, sin datos ni nombre de la restricción (`test_integrity_error_no_traducido_responde_500_generico`, PASS). Pero el logger `django.request` escribe `ERROR django.request Internal Server Error: /api/clientes` con la traza completa, que incluye `DETAIL:  Failing row contains (<id>, argon2$argon2id$v=19$m=65536,t=3,p=1$…, null, <nombre>, <teléfono>, <correo>)`. El DETAIL lo arma el servidor PostgreSQL y viaja a libpq aunque `log_error_verbosity = terse` lo quite del log de `db`. Este informe no reproduce valores.
- **Evidencia:** `test_integrity_error_no_traducido_no_escribe_datos_personales_en_los_registros`, marcada `xfail(strict=True)`: con `--runxfail` falla en `assert "Failing row contains" not in texto`. En los registros actuales de `app` no hay trazas (0 `Traceback`): el defecto es latente.
- **Posible área responsable:** backend (configuración de `LOGGING` o tratamiento de `IntegrityError` no traducido: filtro de `django.request`, formateador que omita el mensaje de la excepción de BD, o traducir la excepción a un error sin DETAIL antes de propagarla). Si cambia la política de registros técnicos, la revisa `architect`. **No se corrigió.** Al corregirlo, la prueba dará XPASS y hará fallar la suite a propósito: hay que quitar el marcador `xfail`.

No se encontraron otros defectos nuevos.

## 6. Estado de los defectos del cierre (DEF-QA-001 a 006)

| Defecto | Severidad | Estado | Commit | Evidencia |
|---|---|---|---|---|
| DEF-QA-001 | media | **Corregido y verificado** | `6a10c27` | B.1 a B.3 |
| DEF-QA-002 | media | **Corregido y verificado** | `6a10c27` | C.1 a C.4 |
| DEF-QA-003 | baja | **Corregido y verificado** | `6a10c27` | D.1 a D.3 |
| DEF-QA-004 | baja | **Corregido y verificado** | `ff323ad` (ADR-003 E-1) | E.1 a E.4 |
| DEF-QA-005 | baja | **Corregido** | `b6dea6d` | El README solo deja pendiente la reautenticación de RNF-09. La línea de estado de la propuesta lista la bitácora y `acceso_denegado` como implementados |
| DEF-QA-006 | baja | **Abierto** | — | Se mantiene: `/no-existe.html` muestra "404 Not Found / nginx" y un Host no permitido devuelve HTML de Django en inglés (`<html lang="en">`) |
| OBS-01 | — | Resuelta | `8d54f3c` y volumen recreado | A.1 y A.2 |
| Riesgo 2 del cierre (reintento de cualquier 403) | — | Resuelto | `e776b70` (ADR-006 E-1, ADR-011 E-1) | F.1 a F.3 |

## 7. Pendientes reales antes del Sprint 2

1. **DEF-QA-007** (media): corregirlo antes de agregar las restricciones del S2 (backend, y `architect` si cambia la política de registros). Después, quitar el `xfail`.
2. **DEF-QA-006** (baja): páginas de error del proxy y 400 por Host no permitido, en español y sin texto técnico, antes de que RNF-15 entre formalmente en el S2.
3. **RNF-23** (DA-11): medir en un equipo limpio con el procedimiento de la sección 7 de `cierre-sprint-1.md`, antes de la revisión del S1.
4. **Hallazgos de UX en backlog**, que no están registrados en el repositorio. Conviene incorporarlos al Product Backlog con su descripción completa del informe `ux`:
   - **M-2:** "Volver" del navegador tras cerrar sesión puede mostrar datos desde la caché. En esta QA, en Chromium, volver tras el cierre llevó a `ingresar.html?aviso=sesion` y no mostró el nombre. No se reprodujo en ese escenario; no se probaron otros navegadores ni el bfcache con pestañas en segundo plano. Sigue en backlog.
   - **M-3:** en backlog (descripción en la revisión `ux`; QA no la verificó).
   - **M-4:** lo escrito se guarda en `sessionStorage` sin vencimiento. Confirmado en C.4: `altiro.cuenta.pendiente` guarda el RUT hasta que la misma cuenta vuelve a "Mi cuenta", se cierra sesión desde "Mi cuenta" o se cierra la pestaña. No contiene la contraseña. En un teléfono compartido, otra cuenta no lo ve en pantalla, pero sigue en el almacenamiento de la pestaña.
   - **M-5, M-6 y M-7:** en backlog (descripción en la revisión `ux`; QA no las verificó).
   - **O-1 a O-7:** observaciones de UX en backlog (descripción en la revisión `ux`; QA no las verificó).
5. **Validaciones pendientes con el representante del producto:** CA-25.3 (DA-04), "vista privada" (ADR-002) y el alcance nacional del catálogo (ADR-012).
6. **Hacer commit de `backend/tests/test_qa_saneamiento_s1.py`.**

## 8. Evidencia y acciones con efecto

- Se crearon cuentas ficticias `@example.com` en la base principal: 1 por la carrera de E.1, 3 en `qa_saneamiento.py` y las de los scripts del agente frontend (`csrf…`, `defa…`, `defm…`, `pa…`/`pb…`). Es esperado.
- Se generaron líneas ERROR y FATAL en el log de `db` a propósito (E.3 y E.4), y una línea ERROR por una consulta SQL de QA con una columna errónea (`date_joined`).
- `test_altiro` se recreó con `--create-db`. El TRUNCATE de E.4 se ejecutó dentro de `BEGIN … ROLLBACK`.
- No se modificó código de producción. No se borraron volúmenes, imágenes ni bases, y no se hizo commit ni push.

## Anexo — Hallazgos de la revisión `ux` (2026-09-28), pendientes para el Product Backlog

La revisión `ux` de DEF-QA-001/002/003 no encontró bloqueantes. M-1 se corrigió en `6a10c27` porque era una regresión introducida por la corrección de DEF-QA-001. Los demás quedan pendientes, sin implementar:

| ID | Tipo | Hallazgo | Propuesta |
|---|---|---|---|
| M-2 | Menor (antes del S2) | Tras cerrar sesión, "Volver" podría mostrar desde la caché del navegador los datos de "Mi cuenta" (`cuenta.js` usa `location.assign`). QA no lo reprodujo en Chromium | `location.replace` y, en `pageshow` con `persisted`, volver a consultar `/api/cuenta`. Verificar en Chrome Android |
| M-3 | Menor | Tras detectar que la sesión terminó, la tarjeta "Mis datos" sigue mostrando nombre, teléfono, correo y RUT | Vaciar u ocultar `#dato-*` al detectar la sesión terminada |
| M-4 | Menor | `altiro.cuenta.pendiente` guarda RUT, correo o teléfono en sessionStorage sin vencimiento si la persona no vuelve a "Mi cuenta" | Guardar la hora y descartar después de un plazo corto; borrar las claves `altiro.*` al cerrar sesión con éxito |
| M-5 | Menor | Palabras técnicas: "en esta pestaña", "se inició una sesión en este navegador" | "Lo que escribiste seguirá aquí cuando vuelvas a ingresar."; "Parece que alguien ingresó a una cuenta en este teléfono…" |
| M-6 | Menor | "Recuperamos lo que habías escrito" aparece aunque no se haya guardado nada | Mostrar el texto solo si hay al menos un valor guardado |
| M-7 | Menor | "Si esta no es tu cuenta…" no dice cómo comprobar cuál está abierta | "Si la sesión abierta no es la tuya, entra a «Mi cuenta», revisa el nombre y pulsa «Cerrar sesión». Después podrás crear tu cuenta." |
| O-1 | Observación | Si la segunda consulta a `/api/cuenta` falla por conexión (estado 0), `cuenta.js` muestra los errores de visitante | Tratar el estado 0 con el aviso de "sin conexión" |
| O-2 | Observación | Avisos con `role="alert"` que además reciben el foco pueden leerse dos veces en lectores de pantalla | Usar uno solo de los dos mecanismos |
| O-3 | Observación | "Perfil ya agregado" se muestra como éxito (✓) | Aceptable: el objetivo de la persona quedó cumplido |
| O-4 | Observación | La huella de la cuenta es un SHA-256 sin sal de nombre, correo y teléfono; sin `crypto.subtle` (HTTP en la red local) no se guarda nada | Riesgo bajo; probar siempre por HTTPS |
| O-5 | Observación | El contorno de foco `#ffbf47` sobre blanco tiene contraste bajo (unos 1,6:1). Ya existía | Revisar en S2 (RNF-16) |
| O-6 | Observación | El título "Crear mi cuenta" o "Postular como maestro" se mantiene cuando el aviso dice que no hace falta | Aceptable: el subtítulo aclara |
| O-7 | Observación | Con sesión, la postulación solo pide el RUT (y el teléfono si falta) | Correcto: no pide datos de más |

Decisiones de la revisión `ux` sobre puntos abiertos:
- **(a) No** borrar la contraseña tras cualquier error de validación en el registro: obliga a reescribirla sin beneficio de seguridad. Como mejora menor, se sugiere borrarla en `pagehide`.
- **(b)** Consultar `GET /api/cuenta` al cargar las páginas de registro es aceptable.
